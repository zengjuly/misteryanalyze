#!/usr/bin/env python3
# kline_resampler.py - 日K重采样为周K/月K（基于docs/sources.md双源退避方案）
"""
日K → 周K/月K 聚合器
=====================
理论来源: docs/sources.md（AKShare + Baostock 双源退避与日K重采样）

- 周K(weekly): 按周五(W-FRI)聚合
- 月K(monthly): 按月末(M)聚合
- 聚合规则: 开=first, 高=max, 低=min, 收=last, 量=sum, 额=sum, 换手=sum
- 涨跌幅: 收盘价 pct_change 重算
- 独立可测试，不依赖任何数据源
"""

import logging

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


class KLineResampler:
    """日K → 周K/月K 聚合器"""

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
        df = daily_df.copy()

        # 1. 日期标准化 + 排序去重
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期").drop_duplicates(subset=["日期"], keep="last")
        df = df.set_index("日期")

        # 2. 缺失列补默认值
        for col in ["开盘价", "最高价", "最低价", "收盘价", "成交量",
                    "成交额", "换手率"]:
            if col not in df.columns:
                df[col] = None

        # 3. 重采样聚合
        resampled = df.resample(rule_cfg["rule"]).agg(rule_cfg["agg"])
        resampled = resampled.dropna(subset=["收盘价"])

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
