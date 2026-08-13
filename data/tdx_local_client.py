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

import logging
import os

import pandas as pd

try:
    from mootdx.reader import Reader
    MOOTDX_AVAILABLE = True
except ImportError:
    MOOTDX_AVAILABLE = False
    logging.warning("⚠️ mootdx 未安装，通达信本地数据源不可用")

logger = logging.getLogger(__name__)

# 标准中文列名（与 AKShare/Baostock 输出一致）
STANDARD_COLS = ["日期", "代码", "开盘价", "最高价", "最低价",
                 "收盘价", "成交量", "成交额", "换手率", "涨跌幅"]


class TdxLocalClient:
    """通达信本地数据客户端（mootdx 读取 .day 文件）"""

    def __init__(self, vipdoc_dir: str = None, enable: bool = True):
        # 优先级: 环境变量 > 配置 > 默认绝对路径（仓库外）
        self.vipdoc_dir = (os.getenv("TDX_VIPDOC_DIR")
                           or vipdoc_dir
                           or "/home/ai/ai_runner/stock/data/tdx_vipdoc")
        self.enable = enable and MOOTDX_AVAILABLE
        self.reader = None
        self.login_success = False
        if self.enable:
            try:
                # 目录不存在时自动创建（数据包下载脚本会写入）
                os.makedirs(self.vipdoc_dir, exist_ok=True)
                self.reader = Reader.factory(market='std', tdxdir=self.vipdoc_dir)
                self.login_success = True
                logger.info(f"📂 通达信本地数据源就绪: {self.vipdoc_dir}")
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
        读取本地日K线数据（.day 文件）
        返回标准中文列名 DataFrame，与 AKShare/Baostock 一致
        """
        if not self.login_success or self.reader is None:
            return pd.DataFrame(columns=STANDARD_COLS)

        code = self.normalize_stock_code(stock_code)
        market = self._get_market(code)

        try:
            df = self.reader.daily(symbol=code)
        except Exception as e:
            logger.error(f"❌ mootdx 读取 {code} 日线失败: {e}")
            return pd.DataFrame(columns=STANDARD_COLS)

        if df is None or df.empty:
            return pd.DataFrame(columns=STANDARD_COLS)

        # mootdx 列名: date/open/high/low/close/volume/amount → 中文
        rename_map = {
            'date': '日期', 'open': '开盘价', 'high': '最高价',
            'low': '最低价', 'close': '收盘价', 'volume': '成交量',
            'amount': '成交额',
        }
        df = df.rename(columns=rename_map)
        df['代码'] = code

        # 日期标准化
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')

        # 数值类型转换
        for col in ['开盘价', '最高价', '最低价', '收盘价', '成交量', '成交额']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 过滤无效行
        if '开盘价' in df.columns and '收盘价' in df.columns:
            df = df.dropna(subset=['开盘价', '收盘价'])

        # 按日期过滤 + 排序
        if '日期' in df.columns:
            if start_date:
                df = df[df['日期'] >= str(start_date)]
            if end_date:
                df = df[df['日期'] <= str(end_date)]
            df = df.sort_values('日期')

        # 涨跌幅（缺失时计算）
        if '涨跌幅' not in df.columns:
            df['涨跌幅'] = df['收盘价'].pct_change() * 100
        # 换手率（本地.day文件无换手率，置None）
        if '换手率' not in df.columns:
            df['换手率'] = None

        # 标准列输出
        for col in STANDARD_COLS:
            if col not in df.columns:
                df[col] = None
        return df[STANDARD_COLS].copy()

    # 兼容其他周期接口（tdx本地仅日线，周/月由上层重采样）
    def get_weekly_data(self, stock_code: str, start_date: str = None,
                        end_date: str = None, adjust: str = "qfq") -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_COLS)

    def get_monthly_data(self, stock_code: str, start_date: str = None,
                         end_date: str = None, adjust: str = "qfq") -> pd.DataFrame:
        return pd.DataFrame(columns=STANDARD_COLS)
