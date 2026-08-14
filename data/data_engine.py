#!/usr/bin/env python3
# data_engine.py - Cache-Aside 数据抽象层（基于docs/gemmi_an.md数据中枢方案）
"""
MysteryDataEngine - 数据抽象与缓存穿透控制层
=============================================
理论来源: docs/gemmi_an.md（数据中枢与全量自动化分析方案）

采用 Cache-Aside（旁路缓存）模式:
  读取: 先查本地 SQLite 缓存 → 未命中则请求 baostock → 清洗后回填缓存
  写入: safe_upsert 线程安全增量写入，确保分析层始终基于最新本地行情工作
"""

import os
import sys
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_manager import MysteryDB, DEFAULT_DB_PATH
from baostock_client import BaostockClient, BAOSTOCK_LOCK

logger = logging.getLogger(__name__)

# 行情默认回溯天数（日线约3年、周线约5年、月线约10年）
DEFAULT_LOOKBACK_DAYS = {
    'daily': 1100,
    'weekly': 1830,
    'monthly': 3650,
}


class MysteryDataEngine:
    """Cache-Aside 数据引擎：本地缓存 + 双源（AKShare主/baostock备）穿透回填"""

    def __init__(self, db_path: str = DEFAULT_DB_PATH,
                 baostock_client: BaostockClient = None,
                 config: dict = None):
        self.db = MysteryDB(db_path)
        self.client = baostock_client if baostock_client else BaostockClient()
        self._logged_in = False
        # K线保留条数配置（循环覆盖，控制存储成本）
        self.kline_limit = {}
        if config and config.get('data_source'):
            kl = config['data_source'].get('kline_limit', {})
            if kl.get('enable_cleanup', True):
                self.kline_limit = {
                    'daily': int(kl.get('daily', 2000)),
                    'weekly': int(kl.get('weekly', 500)),
                    'monthly': int(kl.get('monthly', 300)),
                }
        # 双源退避统一客户端（config 含 data_source 段时启用）
        self.market_client = None
        if config and config.get('data_source'):
            from market_data_client import MarketDataClient
            self.market_client = MarketDataClient(config)
            self.client = self.market_client.bs_client  # 兼容旧接口

    # ============ 连接管理 ============
    def ensure_login(self) -> bool:
        """确保已登录baostock"""
        if not self._logged_in:
            self._logged_in = self.client.login()
        return self._logged_in

    def logout(self):
        if self._logged_in:
            self.client.logout()
            self._logged_in = False

    # ============ 全量股票列表 ============
    def sync_stock_list(self, include_index: bool = False) -> int:
        """
        同步全市场证券列表到本地缓存（query_stock_basic 全量）
        :param include_index: 是否包含指数（默认仅股票）
        :return: 写入数量
        """
        if not self.ensure_login():
            logger.error("❌ baostock登录失败，无法同步证券列表")
            return 0
        try:
            import baostock as bs
            rs = bs.query_stock_basic()
            if rs.error_code != '0':
                logger.error(f"❌ query_stock_basic失败: {rs.error_msg}")
                return 0
            df = rs.get_data()
            if df is None or df.empty:
                return 0
            # 默认过滤：仅股票(type=1)且上市(status=1)
            if not include_index:
                df = df[df['type'] == '1'].copy()
                df = df[df['status'] == '1'].copy()
            n = self.db.upsert_stock_info(df)
            logger.info(f"✅ 同步证券列表 {n} 条（含指数: {include_index}）")
            return n
        except Exception as e:
            logger.error(f"❌ 同步证券列表异常: {e}")
            return 0

    # ============ 行情同步（缓存穿透） ============
    def get_kline(self, code: str, period: str = 'daily',
                  start_date: str = None, end_date: str = None,
                  force_refresh: bool = False,
                  auto_backfill: bool = True) -> pd.DataFrame:
        """
        读取行情：优先本地缓存，未命中则请求baostock并回填（Cache-Aside）
        :param code: 证券代码（9位 sh.600150）
        :param period: 周期 daily/weekly/monthly
        :param start_date: 起始日期
        :param end_date: 截止日期
        :param force_refresh: 强制刷新（忽略缓存）
        :param auto_backfill: 未命中时自动回填
        :return: 行情DataFrame（按日期升序）
        """
        # 1. 查缓存
        if not force_refresh:
            cached = self.db.load_kline(code, period, start_date, end_date)
            if not cached.empty:
                return cached

        # 2. 缓存未命中 → 请求baostock
        if not auto_backfill:
            return pd.DataFrame()

        if not self.ensure_login():
            logger.error(f"❌ 登录失败，无法获取 {code} {period}")
            return pd.DataFrame()

        # 计算默认日期范围（如未指定）
        if start_date is None or end_date is None:
            end = datetime.now()
            lookback = DEFAULT_LOOKBACK_DAYS.get(period, 1100)
            start = end - timedelta(days=lookback)
            start_date = start.strftime('%Y-%m-%d')
            end_date = end.strftime('%Y-%m-%d')

        # 按周期调用对应接口（网络解码错误自动重试3次，带退避）
        import time as _time
        max_net_retry = 3

        # 双源退避模式：走 MarketDataClient（主备切换 + 日K重采样）
        if self.market_client is not None:
            try:
                if period == 'daily':
                    df = self.market_client.fetch_daily(code, start_date, end_date)
                elif period == 'weekly':
                    df = self.market_client.fetch_weekly(code, start_date, end_date)
                elif period == 'monthly':
                    df = self.market_client.fetch_monthly(code, start_date, end_date)
                else:
                    logger.error(f"❌ 未知周期: {period}")
                    return pd.DataFrame()
            except Exception as e:
                logger.error(f"❌ 双源获取 {code} {period} 异常: {str(e)[:150]}")
                return pd.DataFrame()

            if df is None or df.empty:
                return pd.DataFrame()
            df_clean = self._clean_kline(df)
            if auto_backfill and not df_clean.empty:
                # 双源模式同样应用循环覆盖（kline_limit）
                max_rows = self.kline_limit.get(period) if self.kline_limit else None
                self.db.upsert_kline(df_clean, code, period, max_rows=max_rows)
            return df_clean

        # 单源模式（兼容旧逻辑）：baostock 直连 + 重试
        for attempt in range(max_net_retry):
            try:
                # baostock 全局单socket：加锁串行化网络请求，防止多线程数据交错
                with BAOSTOCK_LOCK:
                    if period == 'daily':
                        df = self.client.get_daily_data(code, start_date, end_date)
                    elif period == 'weekly':
                        df = self.client.get_weekly_data(code, start_date, end_date)
                    elif period == 'monthly':
                        df = self.client.get_monthly_data(code, start_date, end_date)
                    else:
                        logger.error(f"❌ 未知周期: {period}")
                        return pd.DataFrame()

                    if df is None or df.empty:
                        # 空结果可能是网络解码失败被内部吞掉 → 重试
                        if attempt < max_net_retry - 1:
                            logger.warning(f"⚠️ {code} {period} 返回空(第{attempt+1}次)，退避重试...")
                            _time.sleep(1.0 * (attempt + 1))
                            continue
                        return pd.DataFrame()

                    # 3. 清洗 + 回填缓存（线程安全 upsert）
                    df_clean = self._clean_kline(df)
                    if auto_backfill and not df_clean.empty:
                        max_rows = self.kline_limit.get(period) if self.kline_limit else None
                        self.db.upsert_kline(df_clean, code, period, max_rows=max_rows)
                    return df_clean
            except Exception as e:
                err_str = str(e)
                if attempt < max_net_retry - 1:
                    logger.warning(f"⚠️ {code} {period} 网络异常(第{attempt+1}次): {err_str[:80]}，重试...")
                    _time.sleep(1.0 * (attempt + 1))
                    continue
                logger.error(f"❌ 获取 {code} {period} 行情异常(重试{max_net_retry}次): {err_str[:150]}")
                return pd.DataFrame()
        return pd.DataFrame()

    @staticmethod
    def _clean_kline(df: pd.DataFrame) -> pd.DataFrame:
        """行情数据清洗（列名标准化 + 去重排序）"""
        df = df.copy()
        # 中文列名 → 英文列名
        cn_map = {'日期': 'date', '开盘价': 'open', '最高价': 'high', '最低价': 'low',
                  '收盘价': 'close', '成交量': 'volume', '成交额': 'amount',
                  '换手率': 'turn', '涨跌幅': 'pctChg', '代码': 'code',
                  'tradestatus': 'tradestatus', '是否ST': 'isST'}
        df = df.rename(columns=cn_map)
        # 删除残留的中文列（避免重复列）
        for cn_col in ['日期', '开盘价', '最高价', '最低价', '收盘价',
                       '成交量', '成交额', '换手率', '涨跌幅', '代码', '是否ST']:
            if cn_col in df.columns:
                df = df.drop(columns=[cn_col])
        # 去重列名（安全兜底）
        df = df.loc[:, ~df.columns.duplicated()]
        # 确保关键列存在
        for col in ['date', 'open', 'high', 'low', 'close', 'volume',
                    'amount', 'turn', 'pctChg', 'preclose', 'adjustflag']:
            if col not in df.columns:
                df[col] = None
        if 'date' in df.columns:
            df['date'] = df['date'].astype(str)
            df = df.drop_duplicates(subset=['date']).sort_values('date')
        return df

    # ============ 财务数据 ============
    def get_financial(self, code: str, current_price: float = None) -> Dict[str, Any]:
        """
        获取财务数据（Cache-Aside：先查缓存，未命中请求baostock回填）
        :param code: 证券代码
        :param current_price: 当前股价（计算PE/PB）
        """
        # 1. 查缓存
        cached = self.db.load_financial(code, limit=1)
        if not cached.empty:
            row = cached.iloc[0]
            return {
                'ROE': row.get('roe'), 'ROE_AVG': row.get('roe_avg'),
                'EPS': row.get('eps_ttm'), 'PE': row.get('PE'), 'PB': row.get('PB'),
                '报告期': row.get('report_date'),
            }

        # 2. 未命中 → 请求baostock
        if not self.ensure_login():
            return {}
        try:
            fin = self.client.get_financial_data(code, current_price)
            # 回填缓存
            self.db.upsert_financial(
                code, str(fin.get('报告期') or ''),
                roe=fin.get('ROE'), roe_avg=fin.get('ROE'),
                eps_ttm=fin.get('EPS'), pe=fin.get('PE'), pb=fin.get('PB'),
                divid_cash=fin.get('每股股息'))
            return fin
        except Exception as e:
            logger.error(f"❌ 获取 {code} 财务异常: {e}")
            return {}

    # ============ 统计与维护 ============
    def stats(self) -> Dict[str, Any]:
        return self.db.stats()

    def close(self):
        self.logout()
        self.db.close()
