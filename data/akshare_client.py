#!/usr/bin/env python3
# akshare_client.py - AKShare数据源客户端（基于docs/sources.md双源退避方案）
"""
AKShare 数据源封装
==================
理论来源: docs/sources.md（AKShare + Baostock 双源退避与日K重采样）

- 接口与 BaostockClient 对齐: login/logout/get_daily_data/get_weekly_data/get_monthly_data
- 输出统一为中文列: 日期/代码/开盘价/最高价/最低价/收盘价/成交量/成交额/换手率/涨跌幅
- 内置限速控制（rate_limit），避免高频请求被封
- 本质为爬虫数据源，稳定性依赖上游网站；失败抛异常由上层退避机制处理
"""

import logging
import time
from typing import Optional

import pandas as pd

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    logging.warning("⚠️ akshare 未安装，AKShare数据源不可用")

logger = logging.getLogger(__name__)

# 标准中文列名（与 BaostockClient 输出一致）
STANDARD_COLS = ["日期", "代码", "开盘价", "最高价", "最低价",
                 "收盘价", "成交量", "成交额", "换手率", "涨跌幅"]


class AkshareClient:
    """AKShare 数据获取客户端（接口与 BaostockClient 对齐）"""

    def __init__(self, rate_limit: float = 0.3, timeout: int = 30):
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.login_success = AKSHARE_AVAILABLE

    # ============ 兼容接口 ============
    def login(self) -> bool:
        """AKShare 无需登录，返回可用状态"""
        return AKSHARE_AVAILABLE

    def logout(self):
        """AKShare 无需登出"""
        pass

    @staticmethod
    def normalize_stock_code(stock_code: str) -> str:
        """
        转为6位数字代码，如 sh.600000 -> 600000，bj.430047 -> 430047
        支持输入: sh600150 / sh.600150 / 600150 / 000001
        """
        code = str(stock_code).strip().lower()
        for prefix in ["sh.", "sz.", "bj.", "sh", "sz", "bj"]:
            code = code.replace(prefix, "")
        # 提取数字部分
        digits = "".join(ch for ch in code if ch.isdigit())
        return digits.zfill(6)

    # ============ 行情获取 ============
    def get_daily_data(self, stock_code: str, start_date: str, end_date: str,
                       adjust: str = "qfq") -> pd.DataFrame:
        """获取日线数据（前复权）"""
        code = self.normalize_stock_code(stock_code)
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        self._rate_limit()
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                start_date=start, end_date=end, adjust=adjust)
        return self._rename_and_filter(df, code)

    def get_weekly_data(self, stock_code: str, start_date: str, end_date: str,
                        adjust: str = "qfq") -> pd.DataFrame:
        """获取周线数据"""
        code = self.normalize_stock_code(stock_code)
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        self._rate_limit()
        df = ak.stock_zh_a_hist(symbol=code, period="weekly",
                                start_date=start, end_date=end, adjust=adjust)
        return self._rename_and_filter(df, code)

    def get_monthly_data(self, stock_code: str, start_date: str, end_date: str,
                         adjust: str = "qfq") -> pd.DataFrame:
        """获取月线数据"""
        code = self.normalize_stock_code(stock_code)
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        self._rate_limit()
        df = ak.stock_zh_a_hist(symbol=code, period="monthly",
                                start_date=start, end_date=end, adjust=adjust)
        return self._rename_and_filter(df, code)

    # ============ 内部工具 ============
    def _rate_limit(self):
        """简单限速，避免高频请求"""
        if self.rate_limit and self.rate_limit > 0:
            time.sleep(self.rate_limit)

    def _rename_and_filter(self, df: pd.DataFrame, code: str) -> pd.DataFrame:
        """
        AKShare返回列 → 标准中文列名
        AKShare列: 日期/股票代码/开盘/收盘/最高/最低/成交量/成交额/振幅/涨跌幅/涨跌额/换手率
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=STANDARD_COLS)

        rename_map = {
            "日期": "日期", "开盘": "开盘价", "收盘": "收盘价",
            "最高": "最高价", "最低": "最低价", "成交量": "成交量",
            "成交额": "成交额", "换手率": "换手率", "涨跌幅": "涨跌幅",
        }
        df = df.rename(columns=rename_map)
        df["代码"] = code
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
        # 字段类型转换
        for col in ["开盘价", "最高价", "最低价", "收盘价", "成交量", "成交额",
                    "换手率", "涨跌幅"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # 移除无效行
        if "开盘价" in df.columns and "收盘价" in df.columns:
            df = df.dropna(subset=["开盘价", "收盘价"])
        # 仅保留标准列（缺失列补空）
        for col in STANDARD_COLS:
            if col not in df.columns:
                df[col] = None
        return df[STANDARD_COLS].copy()

    def get_stock_name(self, stock_code: str) -> str:
        """获取股票名称（AKShare 简版，失败返回空）"""
        try:
            code = self.normalize_stock_code(stock_code)
            self._rate_limit()
            info = ak.stock_individual_info_em(symbol=code)
            name_row = info[info["item"] == "股票简称"]
            if not name_row.empty:
                return str(name_row["value"].iloc[0])
        except Exception as e:
            logger.warning(f"⚠️ AKShare 获取名称失败 {stock_code}: {e}")
        return ""
