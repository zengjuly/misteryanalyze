#!/usr/bin/env python3
# data_feeder.py - 数据接入适配器（docs/refact1.md §5）
"""统一数据获取层：适配多源客户端，为分析模块提供带均线的标准DataFrame

用法:
    feeder = DataFeeder(config)
    daily = feeder.get_daily('sh600150')      # 含 MA5/10/20/60/250
    weekly = feeder.get_weekly('sh600150')    # 含 MA60_W
    market = feeder.get_market_index()        # {'上证指数': df, ...}
"""
import logging
import os
import sys
from typing import Dict, Optional

import pandas as pd

# 确保 data/ 目录可导入（独立运行扫描脚本时）
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
if _DATA_DIR not in sys.path:
    sys.path.insert(0, _DATA_DIR)

logger = logging.getLogger(__name__)


class DataFeeder:
    """数据接入适配器（docs/refact1.md §5）"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.client = None
        ds_cfg = (config or {}).get('data_source') or {}
        if ds_cfg:
            try:
                from market_data_client import MarketDataClient
                self.client = MarketDataClient(config)
                logger.info(f"🔄 DataFeeder 多源客户端就绪: {self.client.source_order}")
            except Exception as e:
                logger.warning(f"⚠️ DataFeeder 多源客户端初始化失败({e})，"
                               f"使用 Baostock 单源")
        if self.client is None:
            try:
                from multi_source_client import MultiSourceClient
                self.client = MultiSourceClient(config)
            except Exception as e:
                logger.warning(f"⚠️ DataFeeder 回退客户端初始化失败: {e}")

    def get_daily(self, code: str, start_date: str = None,
                  end_date: str = None) -> Optional[pd.DataFrame]:
        """获取日K并附加常用均线（MA5/10/20/60/250）
        :return: 含指标列的日K DataFrame（日期升序），失败返回 None
        """
        try:
            if self.client is None:
                return None
            if hasattr(self.client, 'fetch_daily'):
                df = self.client.fetch_daily(code, start_date, end_date)
            else:
                df = self.client.get_daily_data(code, start_date, end_date)
            if df is None or df.empty:
                return None
            df = df.copy()
            close_col = '收盘价' if '收盘价' in df.columns else 'close'
            for w in [5, 10, 20, 60, 250]:
                df[f'MA{w}'] = df[close_col].rolling(w).mean()
            return df
        except Exception as e:
            logger.warning(f"⚠️ DataFeeder.get_daily({code}) 异常: {str(e)[:80]}")
            return None

    def get_weekly(self, code: str, start_date: str = None,
                   end_date: str = None) -> Optional[pd.DataFrame]:
        """获取周K并附加 60 周均线（MA60_W）
        :return: 周K DataFrame（日期升序），失败返回 None
        """
        try:
            if self.client is None:
                return None
            if hasattr(self.client, 'fetch_weekly'):
                df = self.client.fetch_weekly(code, start_date, end_date)
            else:
                df = self.client.get_weekly_data(code, start_date, end_date)
            if df is None or df.empty:
                return None
            df = df.copy()
            close_col = '收盘价' if '收盘价' in df.columns else 'close'
            df['MA60_W'] = df[close_col].rolling(60).mean()
            return df
        except Exception as e:
            logger.warning(f"⚠️ DataFeeder.get_weekly({code}) 异常: {str(e)[:80]}")
            return None

    def get_market_index(self, codes: Dict[str, str] = None) -> Dict[str, pd.DataFrame]:
        """获取主要指数日K
        :param codes: {指数名: 代码}，默认 上证指数/深证成指/创业板指
        :return: {指数名: DataFrame}
        """
        codes = codes or {'上证指数': 'sh.000001', '深证成指': 'sz.399001',
                          '创业板指': 'sz.399006'}
        result = {}
        for name, code in codes.items():
            df = self.get_daily(code)
            if df is not None and not df.empty:
                result[name] = df
        if not result:
            logger.warning("⚠️ DataFeeder 指数获取全部失败")
        return result
