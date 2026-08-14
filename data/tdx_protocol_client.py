#!/usr/bin/env python3
# tdx_protocol_client.py - 通达信行情协议客户端（基于docs/step2.md阶段2优化）
"""
TdxProtocolClient - 通达信行情协议客户端
========================================
理论来源: docs/step2.md（阶段2详细设计：协议增强与性能）

功能:
  从通达信行情服务器（TCP协议）实时获取日K数据，
  用于本地 .day 数据缺失时的增量补充（协议增量）。

客户端选型（自动降级）:
  1. easy_tdx   — UnifiedTdxClient（优先，若已安装）
  2. mootdx     — Quotes.factory 行情协议（默认降级路径，mootdx 0.11.7 已装）
  3. 均不可用   — client=None，仅本地数据（graceful）

说明:
  - 接口与 TdxLocalClient 对齐: fetch_daily(code, start_date, end_date, adjust)
  - 输出统一中文列名: 日期/代码/开盘价/最高价/最低价/收盘价/成交量/成交额/换手率/涨跌幅
  - 协议数据为不复权原始价（与 .day 文件一致），复权由上层处理
"""

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 标准中文列名（与 TdxLocalClient/AKShare/Baostock 输出一致）
STANDARD_COLS = ["日期", "代码", "开盘价", "最高价", "最低价",
                 "收盘价", "成交量", "成交额", "换手率", "涨跌幅"]

# 通达信公开行情服务器（可通过配置覆盖）
DEFAULT_HOST = "119.147.212.81"
DEFAULT_PORT = 7709


class TdxProtocolClient:
    """通达信协议客户端：从行情服务器获取日K（本地数据缺失时补充）"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        tdx_cfg = self.config.get("data_source", {}).get("tdx", {}) \
            if self.config.get("data_source") else {}
        self.host = tdx_cfg.get("server_host", DEFAULT_HOST)
        self.port = int(tdx_cfg.get("server_port", DEFAULT_PORT))
        self.client = None
        self.client_type = None  # easy_tdx / mootdx_quotes / None
        self._init_client()

    def _init_client(self):
        """初始化协议客户端：easy_tdx 优先，mootdx Quotes 降级"""
        # 1. 尝试 easy_tdx
        try:
            from easy_tdx import UnifiedTdxClient
            self.client = UnifiedTdxClient(host=self.host, port=self.port)
            self.client_type = "easy_tdx"
            logger.info(f"📡 使用 easy_tdx 协议客户端 "
                        f"({self.host}:{self.port})")
            return
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"⚠️ easy_tdx 初始化失败({str(e)[:60]})，降级 mootdx")
        # 2. 降级 mootdx Quotes
        try:
            from mootdx.quotes import Quotes
            self.client = Quotes.factory(market='std',
                                         server=(self.host, self.port))
            self.client_type = "mootdx_quotes"
            logger.info(f"📡 使用 mootdx Quotes 协议客户端 "
                        f"({self.host}:{self.port})")
            return
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"⚠️ mootdx Quotes 初始化失败({str(e)[:60]})")
        # 3. 无可用协议客户端
        self.client = None
        self.client_type = None
        logger.warning("⚠️ 无可用协议客户端（easy_tdx/mootdx 均不可用），"
                       "仅使用本地数据")

    @property
    def available(self) -> bool:
        """协议客户端是否可用"""
        return self.client is not None

    # ============ 行情获取 ============
    @staticmethod
    def _normalize_code(stock_code: str) -> str:
        """统一转为6位数字（sh600150→600150，sh.600150→600150）"""
        code = str(stock_code).strip().lower()
        for prefix in ["sh.", "sz.", "bj.", "sh", "sz", "bj"]:
            code = code.replace(prefix, "")
        digits = "".join(ch for ch in code if ch.isdigit())
        return digits.zfill(6)

    def _fetch_raw(self, code: str) -> Optional[pd.DataFrame]:
        """调用底层客户端获取原始日K（列名各异）"""
        if self.client is None:
            return None
        # easy_tdx: daily / get_daily
        if hasattr(self.client, 'daily'):
            return self.client.daily(symbol=code)
        if hasattr(self.client, 'get_daily'):
            return self.client.get_daily(code)
        # mootdx Quotes: bars(frequency=9 日线)
        if hasattr(self.client, 'bars'):
            return self.client.bars(symbol=code, frequency=9, offset=800)
        logger.error("协议客户端不支持日K方法")
        return None

    def fetch_daily(self, code: str, start_date: str = None,
                    end_date: str = None, adjust: str = "qfq") -> pd.DataFrame:
        """
        从行情服务器获取日K（标准中文列名）
        :param code: 证券代码（sh600150/600150/sh.600150）
        :param start_date: 起始日期 YYYY-MM-DD
        :param end_date: 截止日期 YYYY-MM-DD
        :param adjust: 复权类型（协议返回原始价，复权由上层处理）
        :return: 标准中文列名 DataFrame，失败返回空
        """
        if self.client is None:
            return pd.DataFrame(columns=STANDARD_COLS)
        code6 = self._normalize_code(code)
        try:
            df = self._fetch_raw(code6)
            if df is None or df.empty:
                return pd.DataFrame(columns=STANDARD_COLS)

            df = df.copy()
            # 列名标准化（兼容 datetime/vol 与 date/volume 两种风格）
            rename_map = {
                'datetime': '日期', 'date': '日期', 'open': '开盘价',
                'high': '最高价', 'low': '最低价', 'close': '收盘价',
                'vol': '成交量', 'volume': '成交量', 'amount': '成交额',
            }
            df = df.rename(columns=rename_map)
            df['代码'] = code6
            # 日期标准化
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
            # 数值转换
            for col in ['开盘价', '最高价', '最低价', '收盘价', '成交量', '成交额']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            # 按日期过滤 + 排序去重
            if '日期' in df.columns:
                if start_date:
                    df = df[df['日期'] >= str(start_date)]
                if end_date:
                    df = df[df['日期'] <= str(end_date)]
                df = df.sort_values('日期').drop_duplicates(
                    subset=['日期'], keep='last')
            # 涨跌幅/换手率补齐
            if '涨跌幅' not in df.columns:
                df['涨跌幅'] = df['收盘价'].pct_change() * 100
            if '换手率' not in df.columns:
                df['换手率'] = None
            # 标准列输出
            for col in STANDARD_COLS:
                if col not in df.columns:
                    df[col] = None
            return df[STANDARD_COLS].copy()
        except Exception as e:
            logger.error(f"❌ 协议获取 {code} 日K失败: {str(e)[:100]}")
            return pd.DataFrame(columns=STANDARD_COLS)
