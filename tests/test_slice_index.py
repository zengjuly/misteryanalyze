#!/usr/bin/env python3
# test_slice_index.py - 切片索引重置 + 增量合并新鲜度回退测试（2026-08-20 v1.18.2）
"""回归测试:
1. _slice 布尔掩码切片后必须重置为 0 起点 RangeIndex
   （否则下游指标函数 range(len(df))+df.loc[i] 抛 KeyError('0')，
   日志刷 ❌ 计算均线排列状态异常: 0，5 组指标静默缺失）
2. 增量合并结果落后于最近应有交易日 → 回退在线源（.day 停昨日、缓存停前日时
   不得把昨日收盘冒充当日数据输出）
"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'data'))

import pandas as pd

from market_data_client import MarketDataClient


def _mk_df(dates, last_close=10.0):
    """构造中文列日线 DataFrame（日期 str）"""
    return pd.DataFrame({
        '日期': [d.strftime('%Y-%m-%d') for d in dates],
        '代码': 'sh.600150',
        '开盘价': 10.0, '最高价': 10.5, '最低价': 9.8, '收盘价': last_close,
        '成交量': 1000.0, '成交额': 10000.0, '换手率': 1.0, '涨跌幅': 0.0,
    })


def _mk_mc():
    """构造 MarketDataClient（带真实配置，短重试；db/增量用桩替换）"""
    import yaml
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'config', 'config.yaml')
    with open(cfg_path, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    cfg['data_source']['retry_delay'] = 0.01
    cfg['data_source']['retry_times'] = 1
    mc = MarketDataClient(cfg)
    return mc


class TestSliceResetsIndex(unittest.TestCase):

    def test_slice_mid_frame_resets_index(self):
        """切片中间段 → 索引必须从 0 开始（原 bug: 从切片起点开始）"""
        dates = pd.date_range('2025-01-01', periods=500, freq='B')
        df = _mk_df(dates)
        sliced = MarketDataClient._slice(df, '2026-01-01', '2026-12-31')
        self.assertFalse(sliced.empty)
        self.assertEqual(sliced.index[0], 0)
        self.assertEqual(sliced.index[-1], len(sliced) - 1)

    def test_slice_no_filter_keeps_clean_index(self):
        """无过滤（start/end 为空）→ 索引仍 0 起点"""
        df = _mk_df(pd.date_range('2025-01-01', periods=10, freq='B'))
        sliced = MarketDataClient._slice(df, None, None)
        self.assertEqual(list(sliced.index), list(range(10)))


class TestIncrementalFreshness(unittest.TestCase):
    """增量路径: 合并结果新鲜度 + 索引（mock db/tdx_incremental，零网络）"""

    def _patch_mc(self, mc, cache_df, delta_df, last_date):
        """用桩替换 db 与 tdx_incremental"""
        class FakeDB:
            def get_last_date(self, code, period):
                return last_date
            def load_kline(self, code, period):
                return cache_df
        class FakeInc:
            def fetch_delta(self, code, last_date):
                return delta_df
        mc.db = FakeDB()
        mc.tdx_incremental = FakeInc()

    def test_delta_empty_fresh_cache_returns_clean_index(self):
        """delta 空 + 缓存覆盖最新交易日 → 返回切片缓存且索引 0 起点"""
        end = datetime.now().date()
        while end.weekday() >= 5:  # 周六/周日 → 最近工作日（周五）
            end -= timedelta(days=1)
        dates = pd.date_range(end=end, periods=40, freq='B')  # 末根=最近交易日
        cache = _mk_df(dates)
        mc = _mk_mc()
        self._patch_mc(mc, cache, pd.DataFrame(), str(dates[-1].date()))
        out = mc._fetch_with_incremental('sh600150', '2026-01-01',
                                         '2026-12-31')
        self.assertIsNotNone(out)
        self.assertFalse(out.empty)
        self.assertEqual(out.index[0], 0, "切片后索引必须从 0 开始")

    def test_delta_nonempty_merged_stale_returns_none(self):
        """delta 非空但合并结果仍落后（.day 只到昨日）→ 回退在线源(None)"""
        today = datetime.now().date()
        # 缓存停 3 天前，增量只补到 2 天前 → 合并仍落后
        cache_dates = pd.date_range(today - timedelta(days=60), periods=38,
                                    freq='B')
        cache = _mk_df(cache_dates)
        delta = _mk_df([cache_dates[-1] + timedelta(days=1)])
        mc = _mk_mc()
        self._patch_mc(mc, cache, delta, str(cache_dates[-1].date()))
        with mock.patch.object(mc, '_fetch_with_fallback',
                               return_value=pd.DataFrame()) as fb:
            out = mc.fetch_daily('sh600150', '2026-01-01', '2026-12-31')
        self.assertTrue(out.empty)
        fb.assert_called_once()

    def test_delta_nonempty_merged_fresh_returns_clean_index(self):
        """delta 非空 + 合并结果已最新 → 返回合并数据且索引 0 起点"""
        today = datetime.now().date()
        cache_dates = pd.date_range(today - timedelta(days=60), periods=38,
                                    freq='B')
        cache = _mk_df(cache_dates)
        # 增量补到最新交易日（今天/最近工作日）→ 合并新鲜
        delta = _mk_df([today])
        mc = _mk_mc()
        self._patch_mc(mc, cache, delta, str(cache_dates[-1].date()))
        with mock.patch.object(mc, '_fetch_with_fallback') as fb:
            out = mc.fetch_daily('sh600150', '2026-01-01', '2026-12-31')
        self.assertFalse(out.empty)
        fb.assert_not_called()
        self.assertEqual(out.index[0], 0, "合并结果索引必须从 0 开始")


if __name__ == '__main__':
    unittest.main()
