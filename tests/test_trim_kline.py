#!/usr/bin/env python3
# test_trim_kline.py - K线循环覆盖测试（docs/step3.md 3.4.1）
"""测试: 2000条限制 / 循环覆盖 / 中文列名兼容"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'data'))

import pandas as pd

from db_manager import MysteryDB


def make_kline_dates(n, start='2020-01-01'):
    """生成 n 个交易日（工作日）字符串"""
    import datetime
    d = datetime.date.fromisoformat(start)
    out = []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


class TestTrimKline(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.mkdtemp(prefix='hermes-test-trim-')
        self.db_path = os.path.join(tmp, 't.db')
        self.db = MysteryDB(self.db_path)
        self.addCleanup(shutil.rmtree, os.path.dirname(self.db_path),
                        ignore_errors=True)

    def test_trim_keeps_newest(self):
        """插入120条 max_rows=100 → 保留最新100条"""
        dates = make_kline_dates(120)
        df = pd.DataFrame({
            'date': dates, 'open': 10.0, 'high': 11.0, 'low': 9.0,
            'close': [10 + i * 0.01 for i in range(len(dates))],
            'volume': 1000, 'amount': 1e6, 'turn': 1.0, 'pctChg': 0.1})
        n = self.db.upsert_kline(df, 'sh.999999', 'daily', max_rows=100)
        self.assertEqual(n, 120)
        remain = self.db.load_kline('sh.999999', 'daily')
        self.assertEqual(len(remain), 100)
        self.assertEqual(remain['date'].min(), dates[20])   # 最早的20条被删
        self.assertEqual(remain['date'].max(), dates[-1])   # 最新保留

    def test_upsert_cn_columns(self):
        """中文列名兼容写入"""
        df = pd.DataFrame({
            '日期': ['2026-08-10', '2026-08-11'],
            '开盘价': [10.0, 10.2], '最高价': [10.5, 10.6],
            '最低价': [9.9, 10.1], '收盘价': [10.1, 10.4],
            '成交量': [100000, 120000], '成交额': [1e6, 1.2e6],
            '换手率': [1.0, 1.2], '涨跌幅': [1.0, 2.97]})
        n = self.db.upsert_kline(df, 'sh.888888', 'daily')
        self.assertEqual(n, 2)
        loaded = self.db.load_kline('sh.888888', 'daily')
        self.assertEqual(loaded.iloc[-1]['close'], 10.4)
        self.assertEqual(self.db.get_last_date('sh.888888', 'daily'),
                         '2026-08-11')

    def test_get_last_date(self):
        """get_last_date 返回最大日期"""
        df = pd.DataFrame({
            'date': ['2026-08-01', '2026-08-04', '2026-08-05'],
            'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2,
            'volume': 100, 'amount': 1e5})
        self.db.upsert_kline(df, 'sh.777777', 'daily')
        self.assertEqual(self.db.get_last_date('sh.777777', 'daily'),
                         '2026-08-05')
        self.assertIsNone(self.db.get_last_date('sh.666666', 'daily'))

    def test_get_trading_calendar(self):
        """交易日历 = daily日期并集"""
        df = pd.DataFrame({
            'date': ['2026-08-01', '2026-08-04'],
            'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2,
            'volume': 100, 'amount': 1e5})
        self.db.upsert_kline(df, 'sh.555555', 'daily')
        cal = self.db.get_trading_calendar()
        self.assertIn('2026-08-01', cal)
        self.assertIn('2026-08-04', cal)
        self.assertEqual(cal, sorted(cal))


if __name__ == '__main__':
    unittest.main()
