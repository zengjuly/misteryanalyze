#!/usr/bin/env python3
# kline_resampler.py - 日K重采样为周K/月K（升级版：交易日历感知 + 最少K线数过滤）
"""
日K → 周K/月K 聚合器（升级版）
==============================
理论来源: docs/sources.md（双源退避与日K重采样）+ docs/step1.md（阶段1优化）

升级内容（step1.md）:
  1. 交易日历感知: use_trading_calendar=true 时，仅保留交易日（日历可注入）
  2. 最少K线数过滤: 周K≥min_bars_weekly(3)根日K、月K≥min_bars_monthly(10)根日K
     否则视为不完整周期剔除；keep_latest_period=true 时最新周期豁免（进行中）
  3. 向后兼容: 不传config时使用默认参数，行为与原版一致（无过滤）

聚合规则:
  - 周K(weekly): 按周五(W-FRI)聚合
  - 月K(monthly): 按月末(ME)聚合（pandas 3.0: M 已改为 ME）
  - 开=first, 高=max, 低=min, 收=last, 量=sum, 额=sum, 换手=sum
  - 涨跌幅: 收盘价 pct_change 重算
"""

import logging
from typing import List, Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

# 标准中文列名
STANDARD_COLS = ["日期", "代码", "开盘价", "最高价", "最低价",
                 "收盘价", "成交量", "成交额", "换手率", "涨跌幅"]

# 聚合规则
AGG_RULES = {
    "weekly": {
        "rule": "W-FRI",  # 按周五为周结束
        "agg": {
            "开盘价": "first", "最高价": "max", "最低价": "min",
            "收盘价": "last", "成交量": "sum", "成交额": "sum",
            "换手率": "sum",
        },
    },
    "monthly": {
        "rule": "ME",  # 按月末（pandas 3.0: M 已改为 ME）
        "agg": {
            "开盘价": "first", "最高价": "max", "最低价": "min",
            "收盘价": "last", "成交量": "sum", "成交额": "sum",
            "换手率": "sum",
        },
    },
}

# 默认最少K线数（docs/step1.md）
DEFAULT_MIN_BARS = {"weekly": 3, "monthly": 10}


class KLineResampler:
    """日K → 周K/月K 聚合器（交易日历感知 + 最少K线数过滤）"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        resample_cfg = self.config.get("data_source", {}).get("resample", {})
        self.min_bars_weekly = int(resample_cfg.get(
            "min_bars_weekly", DEFAULT_MIN_BARS["weekly"]))
        self.min_bars_monthly = int(resample_cfg.get(
            "min_bars_monthly", DEFAULT_MIN_BARS["monthly"]))
        self.use_trading_calendar = bool(resample_cfg.get(
            "use_trading_calendar", True))
        # 最新周期豁免（进行中的周/月K必须保留，否则最新分析数据缺失）
        self.keep_latest_period = bool(resample_cfg.get(
            "keep_latest_period", True))
        self._calendar: Optional[pd.DatetimeIndex] = None

    def set_calendar(self, calendar: Union[pd.DatetimeIndex, List[str]]):
        """
        注入交易日历（DatetimeIndex 或 'YYYY-MM-DD' 字符串列表）
        来源建议: db.get_trading_calendar()（缓存日K日期并集）
        """
        if calendar is None:
            self._calendar = None
            return
        if isinstance(calendar, pd.DatetimeIndex):
            self._calendar = calendar.normalize()
        else:
            self._calendar = pd.DatetimeIndex(
                [pd.Timestamp(c) for c in calendar]).normalize()

    def resample(self, daily_df: pd.DataFrame, period: str = "weekly") -> pd.DataFrame:
        """
        从日K聚合为周K(weekly)或月K(monthly)
        :param daily_df: 日K DataFrame（标准中文列名）
        :param period: weekly / monthly
        :return: 重采样后的K线DataFrame（标准中文列名）
        """
        if daily_df is None or daily_df.empty:
            return pd.DataFrame(columns=STANDARD_COLS)

        if period not in AGG_RULES:
            logger.error(f"❌ 不支持的聚合周期: {period}")
            return pd.DataFrame(columns=STANDARD_COLS)

        rule_cfg = AGG_RULES[period]
        min_bars = (self.min_bars_weekly if period == "weekly"
                    else self.min_bars_monthly)
        df = daily_df.copy()

        # 1. 日期标准化 + 排序去重
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期").drop_duplicates(subset=["日期"], keep="last")

        # 1.5 交易日历过滤（仅保留交易日）
        if self.use_trading_calendar and self._calendar is not None:
            df = df[df["日期"].dt.normalize().isin(self._calendar)]

        df = df.set_index("日期")

        # 2. 缺失列补默认值
        for col in ["开盘价", "最高价", "最低价", "收盘价", "成交量",
                    "成交额", "换手率"]:
            if col not in df.columns:
                df[col] = None

        # 3. 重采样聚合
        counts = df.resample(rule_cfg["rule"]).size()
        resampled = df.resample(rule_cfg["rule"]).agg(rule_cfg["agg"])
        resampled = resampled.dropna(subset=["收盘价"])

        # 3.5 最少K线数过滤（剔除不完整周期；最新周期豁免）
        if min_bars and min_bars > 0:
            keep = counts >= min_bars
            if self.keep_latest_period and len(keep) > 0:
                keep.iloc[-1] = True  # 进行中的最新周期必须保留
            resampled = resampled[keep]

        # 4. 重算涨跌幅
        resampled["涨跌幅"] = resampled["收盘价"].pct_change() * 100

        # 5. 补齐代码列
        if "代码" in df.columns and not df["代码"].dropna().empty:
            resampled["代码"] = df["代码"].dropna().iloc[0]
        else:
            resampled["代码"] = ""

        # 6. 重置索引 + 日期格式化
        resampled = resampled.reset_index()
        resampled["日期"] = resampled["日期"].dt.strftime("%Y-%m-%d")

        # 7. 标准列输出
        for col in STANDARD_COLS:
            if col not in resampled.columns:
                resampled[col] = None
        return resampled[STANDARD_COLS].copy()
