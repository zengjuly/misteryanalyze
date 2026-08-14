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
        self.vipdoc_dir = resolve_path(
            'TDX_VIPDOC_DIR', vipdoc_dir,
            '/home/ai/ai_runner/stock/data/tdx_vipdoc')
        self.enable = enable and MOOTDX_AVAILABLE
        self.reader = None
        self.login_success = False
        # 协议客户端（本地无数据时从行情服务器补充，docs/step2.md）
        self.protocol_client = None
        if config is not None:
            try:
                from tdx_protocol_client import TdxProtocolClient
                self.protocol_client = TdxProtocolClient(config)
            except Exception as e:
                logger.warning(f"⚠️ 协议客户端初始化失败({str(e)[:80]})")
        # 本地 .day 读取器（自研 struct 解析，docs/step1.md TdxIncremental）
        # 说明: mootdx Reader 期望 {tdxdir}/vipdoc/{market}/lday/ 结构（多一层vipdoc），
        # 与本项目 tdx_vipdoc/{market}/lday/ 不匹配导致 reader.daily 恒为空；
        # 因此实际 .day 读取统一走 TdxIncremental（兼容标准/扁平两种目录结构）。
        from tdx_incremental import TdxIncremental
        self.incremental_reader = TdxIncremental(vipdoc_dir=self.vipdoc_dir)
        if self.enable:
            try:
                # 目录不存在时自动创建（数据包下载脚本会写入）
                os.makedirs(self.vipdoc_dir, exist_ok=True)
                self.reader = Reader.factory(market='std', tdxdir=self.vipdoc_dir)
                self.login_success = True
                logger.info(f"📂 通达信本地数据源就绪: {self.vipdoc_dir}"
                            + ("（含协议补充）" if self.protocol_client
                               and self.protocol_client.available else ""))
            except Exception as e:
                logger.warning(f"⚠️ 通达信本地数据源初始化失败({e})，"
                               f"将由备用源兜底")

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

        # 本地读取（TdxIncremental 兼容标准/扁平目录结构）
        df = self.incremental_reader._read_day_file_tail(code, None)

        if df is None or df.empty:
            # 本地无数据 → 协议补充
            return self._fetch_protocol(stock_code, start_date, end_date)

        # 日期过滤 + 排序
        if '日期' in df.columns:
            df['日期'] = df['日期'].dt.strftime('%Y-%m-%d')
            if start_date:
                df = df[df['日期'] >= str(start_date)]
            if end_date:
                df = df[df['日期'] <= str(end_date)]
            df = df.sort_values('日期')

        # 标准列输出
        for col in STANDARD_COLS:
            if col not in df.columns:
                df[col] = None
        return df[STANDARD_COLS].copy()

    def _fetch_protocol(self, stock_code: str, start_date: str = None,
                        end_date: str = None) -> pd.DataFrame:
        """本地无数据时，用协议客户端从行情服务器获取（协议增量）"""
        if self.protocol_client is None or not self.protocol_client.available:
            return pd.DataFrame(columns=STANDARD_COLS)
        if not start_date or not end_date:
            logger.debug("协议补充需提供 start_date/end_date，跳过")
            return pd.DataFrame(columns=STANDARD_COLS)
        df = self.protocol_client.fetch_daily(
            stock_code, start_date, end_date)
        if not df.empty:
            logger.info(f"📡 [{stock_code}] 本地无数据，协议补充 "
                        f"{len(df)} 条（{start_date}~{end_date}）")
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
        # 尝试 mootdx.financial（0.11.7 为空包，捕获 ImportError 降级）
        try:
            from mootdx.financial import Financial
            fin = Financial(tdxdir=self.vipdoc_dir)
            df = fin.get_stock_financial(symbol=code,
                                         market=self._get_market(code))
            if df is not None and not df.empty:
                return df
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"mootdx财务解析 {code} 失败: {str(e)[:60]}")
        # 探测本地财务包状态（可观测性）
        gpcw = glob.glob(os.path.join(self.vipdoc_dir, 'gpcw*.zip'))
        if gpcw:
            logger.debug(f"{code} 本地财务包 {len(gpcw)} 个(gpcw*.zip)，"
                         f"二进制解析暂未实现，由在线源兜底")
        return pd.DataFrame()

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
