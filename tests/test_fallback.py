#!/usr/bin/env python3
# test_fallback.py - 多源退避与健康熔断测试（docs/step3.md 3.4.1）
"""测试: 主源失败切换 / 健康熔断 / 空数据不误熔断"""
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'data'))

import pandas as pd

from source_health import SourceHealth


class TestSourceHealth(unittest.TestCase):

    def test_trip_after_3_failures(self):
        """连续3次失败 → 熔断"""
        h = SourceHealth({'data_source': {'health': {
            'enable': True, 'fail_threshold': 3, 'recover_seconds': 300}}})
        self.assertTrue(h.is_available('akshare'))
        for _ in range(3):
            h.record('akshare', False, latency_ms=50)
        self.assertFalse(h.is_available('akshare'))
        self.assertEqual(h.stats['akshare']['consecutive_failures'], 3)
        self.assertEqual(h.stats['akshare']['health_score'], 0.0)

    def test_recover_after_time(self):
        """超恢复期自动恢复"""
        h = SourceHealth({'data_source': {'health': {
            'enable': True, 'fail_threshold': 3, 'recover_seconds': 300}}})
        for _ in range(3):
            h.record('akshare', False, latency_ms=50)
        h.stats['akshare']['last_failure_time'] = time.time() - 301
        self.assertTrue(h.is_available('akshare'))
        self.assertEqual(h.stats['akshare']['consecutive_failures'], 0)

    def test_success_resets_counter(self):
        """成功后连续失败清零（未熔断时）"""
        h = SourceHealth({'data_source': {'health': {
            'enable': True, 'fail_threshold': 3}}})
        h.record('akshare', False, 10)
        h.record('akshare', False, 10)
        h.record('akshare', True, 10)
        self.assertEqual(h.stats['akshare']['consecutive_failures'], 0)
        self.assertTrue(h.is_available('akshare'))

    def test_tripped_not_reopened_by_success(self):
        """熔断中成功记录不立即解开（按设计需等恢复期）"""
        h = SourceHealth({'data_source': {'health': {
            'enable': True, 'fail_threshold': 3}}})
        for _ in range(3):
            h.record('akshare', False, 10)
        h.record('akshare', True, 10)
        self.assertFalse(h.is_available('akshare'))

    def test_get_ordered_sources(self):
        """剔除熔断源，保持preferred顺序"""
        h = SourceHealth({'data_source': {'health': {
            'enable': True, 'fail_threshold': 3}}})
        for _ in range(3):
            h.record('baostock', False, 10)
        ordered = h.get_ordered_sources(['tdx_local', 'akshare', 'baostock'])
        self.assertEqual(ordered, ['tdx_local', 'akshare'])

    def test_sort_by_health(self):
        """sort_by_health=true: 低分源排最后"""
        h = SourceHealth({'data_source': {'health': {
            'enable': True, 'fail_threshold': 3, 'sort_by_health': True}}})
        h.record('akshare', True, 10)
        h.record('baostock', False, 10)
        h.record('baostock', False, 10)
        ordered = h.get_ordered_sources(['tdx_local', 'akshare', 'baostock'])
        self.assertEqual(ordered[-1], 'baostock')
        self.assertLess(ordered.index('akshare'), ordered.index('baostock'))

    def test_disable_bypasses(self):
        """enable=false 时全部可用"""
        h = SourceHealth({'data_source': {'health': {'enable': False}}})
        h.record('akshare', False, 10)
        self.assertTrue(h.is_available('akshare'))
        self.assertEqual(h.get_ordered_sources(['akshare']), ['akshare'])


class TestFallbackSwitch(unittest.TestCase):
    """主源失败切换（通过 MarketDataClient 模拟）"""

    def test_fallback_on_exception(self):
        """主源异常 → 记录失败 → 切备用源"""
        import yaml
        from market_data_client import MarketDataClient
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'config', 'config.yaml')
        with open(cfg_path, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        cfg['data_source']['retry_delay'] = 0.01
        cfg['data_source']['retry_times'] = 1
        mc = MarketDataClient(cfg)

        with mock.patch.object(mc, '_fetch_from_source',
                               side_effect=ConnectionError('mock失败')):
            df = mc._fetch_with_fallback('sh600150', 'daily',
                                         '2026-08-01', '2026-08-14')
        self.assertTrue(df.empty)
        st = mc.source_health.stats
        # 至少有一个源记录了失败（akshare 或 baostock，tdx_local空记成功）
        failed = [s for s in st.values() if s['failure_count'] > 0]
        self.assertGreaterEqual(len(failed), 1)

    def test_incremental_still_works(self):
        """回归: fetch_daily 增量路径正常（毫秒级）"""
        import time
        import yaml
        from market_data_client import MarketDataClient
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'config', 'config.yaml')
        with open(cfg_path, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        mc = MarketDataClient(cfg)
        t0 = time.time()
        df = mc.fetch_daily('sh600150', '2026-07-01', '2026-08-14')
        elapsed = time.time() - t0
        self.assertLess(elapsed, 5)
        self.assertFalse(df.empty)
        self.assertIn('收盘价', df.columns)


if __name__ == '__main__':
    unittest.main()
