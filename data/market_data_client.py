#!/usr/bin/env python3
# market_data_client.py - 统一数据入口（AKShare主源 + Baostock备用源退避）
"""
MarketDataClient - 统一数据入口（主备切换 + 退避）
====================================================
理论来源: docs/sources.md（AKShare + Baostock 双源退避与日K重采样）

功能:
  1. 主源失败自动切换备用源（指数退避 + 日志，不中断分析流程）
  2. 周K/月K 默认由日K重采样生成（prefer_resample=true，周期严格对齐）
  3. 线程安全: Baostock 复用全局锁（BAOSTOCK_LOCK），AKShare 内置限速

数据流:
  上层调用 fetch_daily/fetch_weekly/fetch_monthly
    → 主备退避获取原始K线
    → KLineResampler 聚合周/月K
    → 返回标准中文列名 DataFrame
"""

import logging
import os
import sys
import time
from typing import Dict, Optional

import pandas as pd

# 确保 data/ 目录在 sys.path（支持 data.market_data_client 与 market_data_client 两种导入方式）
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from akshare_client import AkshareClient
from baostock_client import BaostockClient, BAOSTOCK_LOCK
from kline_resampler import KLineResampler
from tdx_local_client import TdxLocalClient

logger = logging.getLogger(__name__)

# 复权映射: 方案配置值 → baostock adjustflag
ADJUSTFLAG_MAP = {"qfq": "2", "hfq": "1", "none": "3"}


class MarketDataClient:
    """统一数据入口：主备退避 + 周期选择 + 日K重采样"""

    def __init__(self, config: Dict):
        ds_cfg = config.get("data_source", {}) if config else {}
        self.ak_client = AkshareClient(
            rate_limit=ds_cfg.get("rate_limit_akshare", 0.3),
            timeout=ds_cfg.get("timeout", 30))
        self.bs_client = BaostockClient()
        # 通达信本地数据源（tdx_local）
        tdx_cfg = ds_cfg.get("tdx", {})
        self.tdx_client = TdxLocalClient(
            vipdoc_dir=tdx_cfg.get("vipdoc_dir"),
            enable=tdx_cfg.get("enable", True))
        self.resampler = KLineResampler()
        self.primary = ds_cfg.get("primary", "akshare")
        # fallback 支持: 字符串或列表
        fb = ds_cfg.get("fallback", "baostock")
        self.fallback_list = fb if isinstance(fb, list) else [fb]
        self.retry_times = int(ds_cfg.get("retry_times", 3))
        self.retry_delay = float(ds_cfg.get("retry_delay", 2))
        self.prefer_resample = bool(ds_cfg.get("prefer_resample", True))
        self.adjust = ds_cfg.get("adjust", "qfq")
        # 源顺序: 主源 + 去重后的备用源列表
        self.source_order = [self.primary]
        for s in self.fallback_list:
            if s and s != self.primary and s not in self.source_order:
                self.source_order.append(s)
        self._bs_logged_in = False

    # ============ 对外接口 ============
    def fetch_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._fetch_with_fallback(code, "daily", start_date, end_date)

    def fetch_weekly(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self.prefer_resample:
            daily = self.fetch_daily(code, start_date, end_date)
            if not daily.empty:
                return self.resampler.resample(daily, "weekly")
            return pd.DataFrame()
        return self._fetch_with_fallback(code, "weekly", start_date, end_date)

    def fetch_monthly(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self.prefer_resample:
            daily = self.fetch_daily(code, start_date, end_date)
            if not daily.empty:
                return self.resampler.resample(daily, "monthly")
            return pd.DataFrame()
        return self._fetch_with_fallback(code, "monthly", start_date, end_date)

    # ============ 主备退避核心 ============
    def _fetch_with_fallback(self, code: str, period: str,
                             start_date: str, end_date: str) -> pd.DataFrame:
        """
        主备源退避获取：
        先主源重试 retry_times 次（指数退避）→ 失败切换备用源 → 全部失败返回空
        """
        sources = self.source_order

        last_error = None
        for src in sources:
            for attempt in range(self.retry_times):
                try:
                    df = self._fetch_from_source(src, code, period, start_date, end_date)
                    if df is not None and not df.empty:
                        logger.info(f"[{src}] {code} {period} 获取成功，{len(df)} 条")
                        return df
                    # 空结果视为失败（可能是网络解码错误被内部吞掉）
                    last_error = RuntimeError(f"{src} 返回空数据")
                except Exception as e:
                    last_error = e
                    wait = self.retry_delay * (2 ** attempt)
                    logger.warning(f"[{src}] {code} {period} 第{attempt+1}次失败: "
                                   f"{str(e)[:100]}，{wait:.1f}s后重试")
                    time.sleep(wait)
            logger.error(f"[{src}] {code} {period} 重试{self.retry_times}次耗尽，"
                         f"切换下一数据源")
        logger.error(f"❌ {code} {period} 所有数据源均失败，最后错误: {last_error}")
        return pd.DataFrame()

    def _fetch_from_source(self, src: str, code: str, period: str,
                           start_date: str, end_date: str) -> pd.DataFrame:
        """从指定源获取数据"""
        adjust = self.adjust
        if src == "tdx_local":
            # 通达信本地源仅支持日线；周/月由上层 prefer_resample 重采样
            if period == "daily":
                return self.tdx_client.get_daily_data(code, start_date, end_date)
            return pd.DataFrame()
        if src == "akshare":
            if period == "daily":
                return self.ak_client.get_daily_data(code, start_date, end_date, adjust=adjust)
            elif period == "weekly":
                return self.ak_client.get_weekly_data(code, start_date, end_date, adjust=adjust)
            elif period == "monthly":
                return self.ak_client.get_monthly_data(code, start_date, end_date, adjust=adjust)
        elif src == "baostock":
            adjustflag = ADJUSTFLAG_MAP.get(adjust, "2")
            # baostock 全局单socket：加锁串行化（线程安全）
            with BAOSTOCK_LOCK:
                if period == "daily":
                    return self.bs_client.get_daily_data(code, start_date, end_date,
                                                         adjustflag=adjustflag)
                elif period == "weekly":
                    return self.bs_client.get_weekly_data(code, start_date, end_date,
                                                          adjustflag=adjustflag)
                elif period == "monthly":
                    return self.bs_client.get_monthly_data(code, start_date, end_date,
                                                           adjustflag=adjustflag)
        raise ValueError(f"未知数据源: {src}")

    # ============ 生命周期 ============
    def logout(self):
        """登出所有数据源"""
        try:
            if self._bs_logged_in:
                self.bs_client.logout()
                self._bs_logged_in = False
        except Exception:
            pass
