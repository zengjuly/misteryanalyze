#!/usr/bin/env python3
# test_mystery_logic.py - 三大心法核心逻辑测试（docs/refact1.md §8）
"""覆盖: 年线滤网 / 周线锚定 / 破五反五 / 主升浪信号 / 综合信号"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..'))

import pandas as pd
import numpy as np

from analysis.mystery_logic import MysteryLogic


def make_daily(n=300, trend='up', ma5_below=False):
    """合成日K: 上涨/横盘/破五场景，含 MA5/10/20/60/250"""
    dates = pd.bdate_range('2025-01-01', periods=n)
    if trend == 'up':
        closes = np.linspace(10, 30, n)
    elif trend == 'down':
        closes = np.linspace(30, 10, n)
    else:
        closes = np.linspace(10, 10.5, n)
    df = pd.DataFrame({'日期': dates, '收盘价': closes})
    for w in [5, 10, 20, 60, 250]:
        df[f'MA{w}'] = df['收盘价'].rolling(w).mean()
    df['成交量'] = 100000
    df['成交额'] = 1e8
    df['换手率'] = 1.0
    df['均线排列'] = 1
    df['量比'] = 1.0
    if ma5_below and len(df) > 1:
        # 最新收盘跌破 MA5
        df.loc[df.index[-1], '收盘价'] = df['MA5'].iloc[-1] * 0.98
    return df


def make_weekly(n=70, trend='up'):
    """合成周K（含 MA60_W）"""
    dates = pd.bdate_range('2024-01-01', periods=n * 5, freq='W-FRI')
    closes = np.linspace(10, 30, n) if trend == 'up' else np.linspace(30, 10, n)
    df = pd.DataFrame({'日期': dates[-n:], '收盘价': closes})
    df['MA60_W'] = df['收盘价'].rolling(60).mean()
    return df


class TestBasicFilter(unittest.TestCase):
    """心法① 年线滤网"""

    def setUp(self):
        self.ml = MysteryLogic()

    def test_pass_when_all_above_ma250(self):
        """上涨趋势: 股价与 MA5/10/20/60 全部在 MA250 之上 → 通过"""
        df = make_daily(300, 'up')
        passed, errors = self.ml.basic_filter(df)
        self.assertTrue(passed, errors)
        # 且无年线滤网错误
        self.assertFalse(any('年线' in e for e in errors))

    def test_fail_when_ma5_below_ma250(self):
        """空头趋势: MA5 在 MA250 之下 → 年线滤网拦截"""
        df = make_daily(300, 'down')
        passed, errors = self.ml.basic_filter(df)
        self.assertFalse(passed)
        self.assertTrue(any('MA5未运行在年线' in e for e in errors), errors)

    def test_insufficient_data(self):
        """数据不足250日 → 不通过"""
        df = make_daily(100, 'up')
        passed, _ = self.ml.basic_filter(df)
        self.assertFalse(passed)


class TestWeeklyAnchor(unittest.TestCase):
    """心法② 周线锚定"""

    def setUp(self):
        self.ml = MysteryLogic()

    def test_anchored_up_trend(self):
        """周线上涨且 60 周线斜率向上 → 锚定"""
        r = self.ml.weekly_anchor_check(make_weekly(70, 'up'))
        self.assertTrue(r['锚定'], r['原因'])

    def test_not_anchored_down_trend(self):
        """周线下跌 → 不锚定"""
        r = self.ml.weekly_anchor_check(make_weekly(70, 'down'))
        self.assertFalse(r['锚定'])

    def test_insufficient_data(self):
        """周线数据不足 → 不锚定"""
        r = self.ml.weekly_anchor_check(make_weekly(5))
        self.assertFalse(r['锚定'])
        self.assertIn('数据不足', r['原因'])

    def test_none_safe(self):
        """None 输入安全"""
        r = self.ml.weekly_anchor_check(None)
        self.assertFalse(r['锚定'])


class TestPo5Fan5(unittest.TestCase):
    """心法③ 破五反五"""

    def setUp(self):
        self.ml = MysteryLogic()

    def test_no_break(self):
        """未破五 → 破五反五 False"""
        df = make_daily(100, 'up')
        r = self.ml.check_po5_fan5(df)
        self.assertFalse(r['破五反五'])
        self.assertIn('未破五', r['原因'])

    def test_break_recovered_quickly(self):
        """破五后1日收回且 MA20 向上 → 破五反五 True"""
        df = make_daily(100, 'up')
        # 制造: 昨天跌破MA5, 今天收回且更高
        df.loc[df.index[-2], '收盘价'] = df['MA5'].iloc[-2] * 0.97
        df.loc[df.index[-1], '收盘价'] = df['MA5'].iloc[-1] * 1.03
        # 重算 MA5（含最新）
        df['MA5'] = df['收盘价'].rolling(5).mean()
        r = self.ml.check_po5_fan5(df)
        self.assertTrue(r['破五反五'], r['原因'])
        self.assertLessEqual(r['破五天数'], 2)

    def test_still_below_ma5(self):
        """仍处破五状态 → False"""
        df = make_daily(100, 'up', ma5_below=True)
        r = self.ml.check_po5_fan5(df)
        self.assertFalse(r['破五反五'])
        self.assertIn('仍处破五', r['原因'])


class TestMainBullWaveSignal(unittest.TestCase):
    """三大心法整合"""

    def setUp(self):
        self.ml = MysteryLogic()

    def test_main_wave_signal(self):
        """上涨趋势 + 周线锚定 + 股价在MA5上 → 主升浪信号"""
        df = make_daily(300, 'up')
        wk = make_weekly(70, 'up')
        r = self.ml.main_bull_wave_signal(df, wk)
        self.assertTrue(r['主升浪信号'], r['详情'])
        self.assertTrue(r['年线滤网'])
        self.assertTrue(r['周线锚定'])

    def test_no_signal_when_filter_fails(self):
        """年线滤网失败 → 无信号"""
        df = make_daily(300, 'down')
        r = self.ml.main_bull_wave_signal(df, None)
        self.assertFalse(r['主升浪信号'])
        self.assertFalse(r['年线滤网'])


class TestComprehensiveSignal(unittest.TestCase):
    """综合信号"""

    def setUp(self):
        self.ml = MysteryLogic()

    def test_filter_fail_advice_watch(self):
        """年线滤网未通过 → 观望"""
        df = make_daily(300, 'down')
        r = self.ml.comprehensive_signal_analysis(df, None)
        self.assertEqual(r['操作建议'], '观望（未通过年线滤网）')
        self.assertEqual(r['综合评分'], 0.0)

    def test_filter_pass_returns_structure(self):
        """滤网通过 → 返回完整结构（评分>0 或 有共振明细）"""
        df = make_daily(300, 'up')
        wk = make_weekly(70, 'up')
        r = self.ml.comprehensive_signal_analysis(df, wk)
        for k in ['综合评分', '操作建议', '主升浪信号', '年线滤网',
                  '周线锚定', '破五反五', '真三振', '共振评分', '共振级别']:
            self.assertIn(k, r, f"缺少字段 {k}")
        self.assertTrue(r['年线滤网'])
        self.assertTrue(r['主升浪信号'])
        # 综合评分 = 共振×0.6 + 主升浪40×0.4 → 至少 16 分
        self.assertGreaterEqual(r['综合评分'], 16.0)
        self.assertIn('操作建议', r)


if __name__ == '__main__':
    unittest.main()
