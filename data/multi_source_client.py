#!/usr/bin/env python3
# multi_source_client.py - 多源退避客户端（主分析流程接入 tdx_local → akshare → baostock）
"""
MultiSourceClient - 主分析流程多源数据客户端
=============================================
理论来源: docs/tdx.md + docs/sources.md（多源退避集成）

问题背景:
  main.py 主分析流程原本直接使用 BaostockClient 获取日/周/月线，
  未接入 MarketDataClient 多源退避层，导致 tdx_local 本地数据未生效。

方案:
  继承 BaostockClient（保持 login/logout/get_industry_data/get_financial_data/
  get_stock_name/get_index_data 等原有接口不变），仅重写行情获取方法:
    get_daily_data / get_weekly_data / get_monthly_data
  → 优先走 MarketDataClient（tdx_local → akshare → baostock 三级退避）
  → 全部失败时回退到 baostock 直连（兼容单源模式）

用法:
  client = MultiSourceClient(config)   # config 含 data_source 段
  # 或
  client = MultiSourceClient()          # 无 config = 纯 baostock（原行为）
"""

import logging
import os
import sys

import pandas as pd

# 确保 data/ 目录在 sys.path
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from baostock_client import BaostockClient
from market_data_client import MarketDataClient

logger = logging.getLogger(__name__)

# baostock adjustflag → 多源 adjust 映射
ADJUSTFLAG_TO_ADJUST = {"1": "hfq", "2": "qfq", "3": "none"}


class MultiSourceClient(BaostockClient):
    """
    多源退避数据客户端：
    - 行情（日/周/月K）→ MarketDataClient 三级退避（tdx_local → akshare → baostock）
    - 其他（行业/财务/名称/指数/股票列表）→ 继承 BaostockClient 原逻辑
    """

    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config
        self.market_client = None
        ds_cfg = (config or {}).get("data_source") or {}
        if ds_cfg:
            try:
                self.market_client = MarketDataClient(config)
                logger.info(f"🔄 多源退避启用: {self.market_client.source_order}")
            except Exception as e:
                logger.warning(f"⚠️ 多源退避初始化失败({e})，使用 baostock 单源")
        else:
            logger.debug("未配置 data_source，使用 baostock 单源（原行为）")

    # ============ 行情获取（多源退避） ============
    def get_daily_data(self, stock_code: str, start_date: str, end_date: str,
                       adjustflag: str = '3') -> pd.DataFrame:
        """日线：优先多源退避，失败回退 baostock"""
        if self.market_client is not None:
            try:
                df = self.market_client.fetch_daily(stock_code, start_date, end_date)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"⚠️ 多源日线失败({e})，回退baostock: {stock_code}")
        return super().get_daily_data(stock_code, start_date, end_date, adjustflag)

    def get_weekly_data(self, stock_code: str, start_date: str, end_date: str,
                        adjustflag: str = '3') -> pd.DataFrame:
        """周线：优先多源（日K重采样），失败回退 baostock"""
        if self.market_client is not None:
            try:
                df = self.market_client.fetch_weekly(stock_code, start_date, end_date)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"⚠️ 多源周线失败({e})，回退baostock: {stock_code}")
        return super().get_weekly_data(stock_code, start_date, end_date, adjustflag)

    def get_monthly_data(self, stock_code: str, start_date: str, end_date: str,
                         adjustflag: str = '3') -> pd.DataFrame:
        """月线：优先多源（日K重采样），失败回退 baostock"""
        if self.market_client is not None:
            try:
                df = self.market_client.fetch_monthly(stock_code, start_date, end_date)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"⚠️ 多源月线失败({e})，回退baostock: {stock_code}")
        return super().get_monthly_data(stock_code, start_date, end_date, adjustflag)
