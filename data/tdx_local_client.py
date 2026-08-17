#!/usr/bin/env python3
# tdx_local_client.py - 通达信本地数据源客户端（基于docs/tdx.md方案）
"""
TdxLocalClient - 通达信本地数据客户端（mootdx）
=================================================
理论来源: docs/tdx.md（基于 mootdx 的通达信本地数据源集成）

- 使用 mootdx 读取通达信官方数据包（hsjday.zip 解压的 .day 文件）
- 作为主数据源(tdx_local)集成到 MarketDataClient 退避链
- 接口与 BaostockClient/AkshareClient 对齐: login/logout/get_daily_data
- 输出统一中文列名: 日期/代码/开盘价/最高价/最低价/收盘价/成交量/成交额/换手率/涨跌幅
- 仅支持日线（周/月K由上层 KLineResampler 重采样生成）
- 财务数据 mootdx 0.11.7 不支持本地解析，返回空由上层兜底（AKShare/baostock）

数据目录:
  默认 /home/ai/ai_runner/stock/data/tdx_vipdoc（Git仓库外）
  可通过环境变量 TDX_VIPDOC_DIR 覆盖
"""

import glob
import logging
import os

import pandas as pd

try:
    from mootdx.reader import Reader
    MOOTDX_AVAILABLE = True
except ImportError:
    MOOTDX_AVAILABLE = False
    logging.warning("⚠️ mootdx 未安装，通达信本地数据源不可用")

# 统一路径解析（环境变量 > 配置 > 默认，docs/step3.md）
try:
    from path_utils import resolve_path
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', 'utils'))
    from path_utils import resolve_path

logger = logging.getLogger(__name__)

# 标准中文列名（与 AKShare/Baostock 输出一致）
STANDARD_COLS = ["日期", "代码", "开盘价", "最高价", "最低价",
                 "收盘价", "成交量", "成交额", "换手率", "涨跌幅"]


class TdxLocalClient:
    """通达信本地数据客户端（mootdx 读取 .day 文件 + 协议增量补充）"""

    def __init__(self, vipdoc_dir: str = None, enable: bool = True,
                 config: dict = None):
        # 优先级: 环境变量TDX_VIPDOC_DIR > 配置 > 默认绝对路径（仓库外）
        # docs/tdx2.md: 日K用 resolve_vipdoc_for_kline（home/vipdoc > vipdoc_dir），
        # 财务用 resolve_vipdoc_for_fin（仅 VIPDOC，绝不读 TDX_HOME）
        # 用户要求: tdxlocal 内部分优先级——优先 TDX_HOME，失败则 TDX_VIPDOC_DIR
        from tdx_path_resolver import (resolve_kline_dirs,
                                       resolve_vipdoc_for_fin)
        # 始终以 resolve_kline_dirs() 为准（TDX_HOME/vipdoc 优先，含 lday 才启用）；
        # 显式 vipdoc_dir 只作为补充目录追加（不覆盖 TDX_HOME 优先级——用户要求
        # 行情优先从通达信安装目录获取，2026-08-17 更新为 /mnt/new_tdx）
        self.kline_dirs = resolve_kline_dirs()
        if vipdoc_dir is not None and vipdoc_dir not in self.kline_dirs:
            self.kline_dirs.append(vipdoc_dir)
        self.vipdoc_dir = self.kline_dirs[0]
        self.fin_dir = resolve_vipdoc_for_fin()
        self.enable = enable and MOOTDX_AVAILABLE
        self.reader = None
        self.login_success = False
        # 协议客户端（本地无数据时从行情服务器补充，docs/step2.md）
        # 延迟初始化: mootdx Quotes.factory 会尝试连接行情服务器，服务器不可达时
        # TCP超时可达15s+，阻塞 MarketDataClient 构造；改为首次真正需要时才连接，
        # 失败一次后永久禁用（_protocol_disabled）。
        self._protocol_cfg = config
        self.protocol_client = None
        self._protocol_initialized = False
        self._protocol_disabled = False
        # 本地 .day 读取器（自研 struct 解析，docs/step1.md TdxIncremental）
        # 说明: mootdx Reader 期望 {tdxdir}/vipdoc/{market}/lday/ 结构（多一层vipdoc），
        # 与本项目 tdx_vipdoc/{market}/lday/ 不匹配导致 reader.daily 恒为空；
        # 因此实际 .day 读取统一走 TdxIncremental（兼容标准/扁平两种目录结构）。
        # 多目录（TDX_HOME 优先 → TDX_VIPDOC_DIR）各持一个 reader，惰性创建
        self.incremental_readers = {}
        if self.enable:
            try:
                # 目录不存在时自动创建（数据包下载脚本会写入）
                os.makedirs(self.vipdoc_dir, exist_ok=True)
                self.reader = Reader.factory(market='std', tdxdir=self.vipdoc_dir)
                self.login_success = True
                logger.info(f"📂 通达信本地数据源就绪: {self.kline_dirs}"
                            + (f"（协议补充·延迟初始化）"
                               if self._protocol_cfg is not None else ""))
            except Exception as e:
                logger.warning(f"⚠️ 通达信本地数据源初始化失败({e})，"
                               f"将由备用源兜底")

    def _reader_for(self, kdir: str):
        """获取指定目录的 TdxIncremental 读取器（惰性创建）"""
        if kdir not in self.incremental_readers:
            from tdx_incremental import TdxIncremental
            self.incremental_readers[kdir] = TdxIncremental(vipdoc_dir=kdir)
        return self.incremental_readers[kdir]

    # ============ 兼容接口 ============
    def login(self) -> bool:
        """本地数据无需登录"""
        return self.login_success

    def logout(self):
        """本地数据无需登出"""
        pass

    @staticmethod
    def normalize_stock_code(stock_code: str) -> str:
        """统一转为6位数字，去除市场前缀"""
        code = str(stock_code).strip().lower()
        for prefix in ["sh.", "sz.", "bj.", "sh", "sz", "bj"]:
            code = code.replace(prefix, "")
        digits = "".join(ch for ch in code if ch.isdigit())
        return digits.zfill(6)

    @staticmethod
    def _get_market(code: str) -> str:
        """根据代码判断市场：sh/sz/bj"""
        if code.startswith(("6", "9", "5")):      # 沪市A股/科创板/ETF
            return "sh"
        elif code.startswith(("0", "2", "3")):    # 深市A股/创业板
            return "sz"
        elif code.startswith(("4", "8")):         # 北交所
            return "bj"
        return "sh"  # 默认

    # ============ 行情获取 ============
    def get_daily_data(self, stock_code: str, start_date: str = None,
                       end_date: str = None, adjust: str = "qfq") -> pd.DataFrame:
        """
        读取本地日K线数据（.day 文件，自研 struct 解析）
        本地无数据/数据不足时，自动用协议客户端从行情服务器补充（docs/step2.md）
        返回标准中文列名 DataFrame，与 AKShare/Baostock 一致
        """
        code = self.normalize_stock_code(stock_code)

        # docs/tdx2.md: 本地优先 + 过期回退（新鲜度判定）
        # 日K文件缺失或末根K线超期 → 协议补充 → 失败回退在线源(akshare/baostock)
        # 用户要求: 目录优先级遍历——优先 TDX_HOME，失败则 TDX_VIPDOC_DIR
        from tdx_path_resolver import day_file_path, is_kline_fresh
        mkt = self._get_market(code)
        is_index = (mkt == 'sh' and code.startswith('000')) or \
                   (mkt == 'sz' and code.startswith('399'))
        df = pd.DataFrame()
        used_dir = None
        for kdir in self.kline_dirs:
            day_file = day_file_path(code, kdir)
            if not os.path.exists(day_file):
                continue
            if not is_kline_fresh(day_file):
                logger.info(f"[TDX本地-过期→fallback] {code} 本地日K超期"
                            f"({day_file})，继续下一目录/协议补充")
                continue
            df = self._reader_for(kdir)._read_day_file_tail(code, None)
            if df is not None and not df.empty:
                used_dir = kdir
                break
        if df is None or df.empty:
            # 本地无数据 → 指数快速失败（协议服务器不可达，避免卡 15s+）/ 协议补充
            if is_index:
                logger.info(f"[TDX本地-指数无本地数据→fallback] {code} "
                            f"指数无 .day，直接回退在线源")
                return pd.DataFrame(columns=STANDARD_COLS)
            return self._fetch_protocol(stock_code, start_date, end_date)
        logger.debug(f"[TDX本地-新鲜] {code} {used_dir}")

        # 日期过滤 + 排序
        if '日期' in df.columns:
            df['日期'] = df['日期'].dt.strftime('%Y-%m-%d')
            if start_date:
                df = df[df['日期'] >= str(start_date)]
            if end_date:
                df = df[df['日期'] <= str(end_date)]
            df = df.sort_values('日期')

        # 换手率补齐：.day 文件无换手率 → 从 SQLite 缓存按日期补（最新行 ffill 近似）
        # 否则走 tdx_local 路径时换手率全 None，导致筹码集中度/换手率指标退化
        if '换手率' in df.columns and df['换手率'].isna().all() \
                and not df.empty and '日期' in df.columns:
            try:
                from db_manager import MysteryDB
                db = MysteryDB()
                cached = db.load_kline(
                    f"{self._get_market(code)}.{code}", 'daily')
                if not cached.empty and 'turn' in cached.columns:
                    turn_map = dict(zip(cached['date'], cached['turn']))
                    df['换手率'] = df['日期'].map(turn_map)
                    df['换手率'] = df['换手率'].ffill()  # 缓存未覆盖的最新行用最近值
            except Exception as e:
                logger.debug(f"换手率补齐失败 {code}: {str(e)[:60]}")

        # 标准列输出
        for col in STANDARD_COLS:
            if col not in df.columns:
                df[col] = None
        return df[STANDARD_COLS].copy()

    def _get_protocol_client(self):
        """延迟初始化协议客户端（首次调用时连接，失败一次永久禁用）"""
        if self._protocol_disabled:
            return None
        if not self._protocol_initialized:
            self._protocol_initialized = True
            if self._protocol_cfg is None:
                self._protocol_disabled = True
                return None
            try:
                from tdx_protocol_client import TdxProtocolClient
                self.protocol_client = TdxProtocolClient(self._protocol_cfg)
            except Exception as e:
                logger.warning(f"⚠️ 协议客户端初始化失败({str(e)[:80]})，"
                               f"本会话禁用协议补充")
                self._protocol_disabled = True
                self.protocol_client = None
        return self.protocol_client

    def _fetch_protocol(self, stock_code: str, start_date: str = None,
                        end_date: str = None) -> pd.DataFrame:
        """本地无数据时，用协议客户端从行情服务器获取（协议增量）"""
        client = self._get_protocol_client()
        if client is None or not client.available:
            return pd.DataFrame(columns=STANDARD_COLS)
        if not start_date or not end_date:
            logger.debug("协议补充需提供 start_date/end_date，跳过")
            return pd.DataFrame(columns=STANDARD_COLS)
        df = client.fetch_daily(stock_code, start_date, end_date)
        if not df.empty:
            logger.info(f"📡 [{stock_code}] 本地无数据，协议补充 "
                        f"{len(df)} 条（{start_date}~{end_date}）")
        else:
            # 连接成功但无数据 → 服务器可能不可达，禁用避免重复超时
            logger.warning(f"⚠️ [{stock_code}] 协议补充为空，"
                           f"本会话禁用协议补充")
            self._protocol_disabled = True
        return df

    # ============ 财务数据（docs/step3.md 财务本地化） ============
    def get_financial_data(self, stock_code: str) -> pd.DataFrame:
        """
        读取本地财务数据（标准化字段：报告期/每股收益/每股净资产/ROE/净利润等）

        说明: 通达信财务包（gpcw*.dat，专有二进制格式）解析依赖 mootdx.financial；
        mootdx 0.11.7 financial 为空包 → 无法本地解析，返回空由上层
        （AKShare/Baostock）兜底获取并缓存至 SQLite（financial_storage）。
        此处保留接口 + 探测本地财务包状态，便于后续接入自研解析。
        """
        code = self.normalize_stock_code(stock_code)
        # docs/tdx2.md: 财务仅从 VIPDOC（fin_dir，含 cw/ 兼容）读取，绝不读 TDX_HOME
        from tdx_path_resolver import is_financial_fresh
        if not is_financial_fresh(self.fin_dir):
            logger.info(f"[TDX本地-财务过期→fallback] {code} 财务包缺失或超期，"
                        f"回退在线源")
            return pd.DataFrame()
        # 尝试 mootdx.financial（0.11.7 为空包，捕获 ImportError 降级）
        try:
            from mootdx.financial import Financial
            fin = Financial(tdxdir=self.fin_dir)
            df = fin.get_stock_financial(symbol=code,
                                         market=self._get_market(code))
            if df is not None and not df.empty:
                return df
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"mootdx财务解析 {code} 失败: {str(e)[:60]}")
        # 探测本地财务包状态（可观测性，兼容 根目录 与 cw/ 子目录）
        gpcw = (glob.glob(os.path.join(self.fin_dir, 'gpcw*.zip'))
                + glob.glob(os.path.join(self.fin_dir, 'cw', 'gpcw*.zip'))
                + glob.glob(os.path.join(self.fin_dir, 'gpcw*.dat')))
        if gpcw:
            logger.debug(f"{code} 本地财务包 {len(gpcw)} 个，"
                         f"二进制解析暂未实现，由在线源兜底")
        return pd.DataFrame()

    def get_block_data(self) -> dict:
        """读取通达信板块数据（docs/tdx2.md: 仅从 TDX_HOME/T0002 读取）
        本机无 TDX_HOME（默认 /mnt/bigdata/tdx/files/new_tdx 不存在）时返回空，
        由上层（db行业分类/baostock）兜底。返回 {'板块名': [代码]}。
        """
        from tdx_path_resolver import resolve_home, is_file_fresh
        home = resolve_home()
        block_dirs = [
            os.path.join(home, 'T0002', 'blocknew'),
            os.path.join(home, 'T0002', 'hq_cache'),
        ]
        result = {}
        for bdir in block_dirs:
            if not os.path.isdir(bdir):
                continue
            if not is_file_fresh(bdir, kind='block'):
                logger.info(f"[TDX本地-板块过期→fallback] {bdir}")
                return {}
            try:
                # 通达信板块文件: *.blk（每行 市场+代码，如 1#600150）
                for f in os.listdir(bdir):
                    if not f.endswith('.blk'):
                        continue
                    name = f[:-4]
                    codes = []
                    with open(os.path.join(bdir, f), encoding='gbk',
                              errors='ignore') as fh:
                        for line in fh:
                            line = line.strip()
                            if '#' in line:
                                mkt, c = line.split('#', 1)
                                mkt = 'sh' if mkt == '1' else (
                                    'sz' if mkt == '0' else 'bj')
                                codes.append(f"{mkt}.{c.strip()}")
                    if codes:
                        result[name] = codes
            except Exception as e:
                logger.warning(f"⚠️ 板块文件解析失败 {bdir}: {str(e)[:80]}")
        if result:
            logger.info(f"🏢 TDX 本地板块读取: {len(result)} 个（{home}）")
        return result

    def financial_source_status(self) -> dict:
        """本地财务数据源状态（可观测性报告用）"""
        gpcw = glob.glob(os.path.join(self.vipdoc_dir, 'gpcw*.zip'))
        return {
            'gpcw_count': len(gpcw),
            'gpcw_samples': [os.path.basename(f) for f in gpcw[:3]],
            'parse_supported': False,
            'note': 'mootdx 0.11.7 financial为空包，gpcw二进制解析未实现；'
                    '财务由在线源兜底并缓存SQLite',
        }

    # 兼容其他周期接口（tdx本地仅日线，周/月由上层重采样）
    def get_weekly_data(self, stock_code: str, start_date: str = None,
                        end_date: str = None, adjust: str = "qfq") -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_COLS)

    def get_monthly_data(self, stock_code: str, start_date: str = None,
                         end_date: str = None, adjust: str = "qfq") -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_COLS)
