#!/usr/bin/env python3
# test_resampler.py - 重采样边界测试（docs/step3.md 3.4.1）
"""测试: 不足min_bars / 跨周期 / 交易日历过滤 / 最新周期豁免"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'data'))

import pandas as pd

from kline_resampler import KLineResampler


def make_daily(days_per_week=(3, 2, 5, 1)):
    """合成日K: 各周日K数为 days_per_week（07-06起）"""
    dates = []
    for w, nd in enumerate(days_per_week):
        base = pd.Timestamp('2026-07-06') + pd.Timedelta(days=7 * w)
        dates += [base + pd.Timedelta(days=i) for i in range(nd)]
    return pd.DataFrame({
        '日期': dates, '开盘价': 10.0, '最高价': 11.0, '最低价': 9.5,
        '收盘价': [10 + i * 0.1 for i in range(len(dates))],
        '成交量': 1000, '成交额': 1e6, '换手率': 1.0})


class TestResampler(unittest.TestCase):

    def test_min_bars_remove_incomplete(self):
        """默认min_bars=3: 剔除中间不足周，最新周豁免保留"""
        rs = KLineResampler()
        wk = rs.resample(make_daily([3, 2, 5, 5]), 'weekly')
        # 第2周只有2天被剔除 → 3周（第1/3/4周）
        self.assertEqual(len(wk), 3)
        dates = list(wk['日期'])
        self.assertNotIn('2026-07-13', dates)  # 第2周(2天)被剔除

    def test_min_bars_5_no_keep_latest(self):
        """min_bars=5 且 keep_latest_period=False: 仅满5天周保留"""
        rs = KLineResampler({'data_source': {'resample': {
            'min_bars_weekly': 5, 'keep_latest_period': False}}})
        wk = rs.resample(make_daily([5, 2, 5, 1]), 'weekly')
        self.assertEqual(len(wk), 2)  # 第1/3周满5天

    def test_keep_latest_period(self):
        """keep_latest_period=True: 最新不完整周保留"""
        rs = KLineResampler({'data_source': {'resample': {
            'min_bars_weekly': 5, 'keep_latest_period': True}}})
        wk = rs.resample(make_daily([5, 2, 5, 1]), 'weekly')
        self.assertEqual(len(wk), 3)  # 第1/3周 + 最新(1天)豁免

    def test_calendar_filter(self):
        """交易日历过滤: 日历覆盖全部交易日时全部保留；混入周末被剔除"""
        daily = make_daily()
        # 注入周末日期（周六）
        weekend_row = pd.DataFrame([{
            '日期': pd.Timestamp('2026-07-18'), '开盘价': 10.0,
            '最高价': 10.5, '最低价': 9.8, '收盘价': 10.3,
            '成交量': 100, '成交额': 1e5, '换手率': 1.0}])
        daily = pd.concat([daily, weekend_row], ignore_index=True)
        # 完整日历（不含周末）
        cal = pd.DatetimeIndex([d for d in daily['日期']
                                if pd.Timestamp(d).dayofweek < 5])
        rs = KLineResampler({'data_source': {'resample': {
            'use_trading_calendar': True}}})
        rs.set_calendar(cal)
        wk = rs.resample(daily, 'weekly')
        # 周末(07-18)被日历剔除；第2周仅2天被min_bars=3剔除，最新周豁免
        # → 保留 3 周（第1/3/4周）
        self.assertEqual(len(wk), 3)
        # 周末行不在任何周K中（07-18 收盘 10.3 不应出现在结果）
        self.assertNotIn(10.3, wk['收盘价'].tolist())

    def test_calendar_behind_data(self):
        """日历落后于数据（增量最新交易日）: 最新交易日保留"""
        dates = pd.date_range('2026-08-03', '2026-08-14', freq='B')
        daily = pd.DataFrame({
            '日期': dates, '开盘价': 33.0, '最高价': 34.0, '最低价': 32.5,
            '收盘价': [33.0 + i * 0.1 for i in range(len(dates))],
            '成交量': 1000, '成交额': 1e6, '换手率': 1.0})
        cal = pd.DatetimeIndex([d for d in dates
                                if d <= pd.Timestamp('2026-08-13')])
        rs = KLineResampler({'data_source': {'resample': {
            'use_trading_calendar': True, 'min_bars_weekly': 3}}})
        rs.set_calendar(cal)
        wk = rs.resample(daily, 'weekly')
        self.assertEqual(str(wk['日期'].iloc[-1]), '2026-08-14')

    def test_monthly_agg(self):
        """月K聚合 + min_bars_monthly"""
        rs = KLineResampler({'data_source': {'resample': {
            'min_bars_monthly': 5}}})
        mo = rs.resample(make_daily([5] * 4 + [3]), 'monthly')
        self.assertGreaterEqual(len(mo), 1)
        # 聚合规则: 收盘=last
        self.assertEqual(mo['收盘价'].iloc[-1],
                         make_daily([5] * 4 + [3])['收盘价'].iloc[-1])

    def test_empty_input(self):
        """空输入返回空DataFrame"""
        rs = KLineResampler()
        out = rs.resample(pd.DataFrame(), 'weekly')
        self.assertTrue(out.empty)
        self.assertTrue(rs.resample(None, 'weekly').empty)  # None安全


if __name__ == '__main__':
    unittest.main()
