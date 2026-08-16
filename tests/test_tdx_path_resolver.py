#!/usr/bin/env python3
# test_tdx_path_resolver.py - docs/tdx2.md 路径解析与新鲜度测试
"""覆盖: 日K新鲜/过期判定 / 财务目录隔离(VIPDOC不读home) / 路径解析优先级"""
import os
import struct
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'data'))


def _make_day_file(path, last_date_int: int):
    """构造最小 .day 文件（定长32字节/条，末条日期=last_date_int）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        for _ in range(3):  # 3条记录
            f.write(struct.pack('<IIIIIIII', 20260101, 10, 10, 10,
                                10, 100, 1000000, 0))
        f.seek(-32, os.SEEK_END)
        f.write(struct.pack('<I', last_date_int))


class TestPathResolver(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='hermes-tdx2-')
        self.old_home = os.environ.get('TDX_HOME')
        self.old_vip = os.environ.get('TDX_VIPDOC_DIR')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self.old_home:
            os.environ['TDX_HOME'] = self.old_home
        else:
            os.environ.pop('TDX_HOME', None)
        if self.old_vip:
            os.environ['TDX_VIPDOC_DIR'] = self.old_vip
        else:
            os.environ.pop('TDX_VIPDOC_DIR', None)

    # ============ 新鲜度 ============
    def test_kline_fresh_today(self):
        """末根K线=今天 → 新鲜"""
        from tdx_path_resolver import is_kline_fresh
        today = int(datetime.now().strftime('%Y%m%d'))
        f = os.path.join(self.tmp, 'sh600150.day')
        _make_day_file(f, today)
        self.assertTrue(is_kline_fresh(f, max_age_days=1))

    def test_kline_stale_old(self):
        """末根K线=30天前 → 过期"""
        from tdx_path_resolver import is_kline_fresh
        from datetime import timedelta
        old = int((datetime.now() - timedelta(days=30)).strftime('%Y%m%d'))
        f = os.path.join(self.tmp, 'sh600150.day')
        _make_day_file(f, old)
        self.assertFalse(is_kline_fresh(f, max_age_days=1))

    def test_kline_missing_file(self):
        """文件不存在 → 过期（回退在线源）"""
        from tdx_path_resolver import is_kline_fresh
        self.assertFalse(is_kline_fresh(
            os.path.join(self.tmp, 'nope.day'), max_age_days=1))

    def test_kline_weekend_buffer(self):
        """周五数据周一仍新鲜（+2缓冲）"""
        from tdx_path_resolver import is_kline_fresh
        from datetime import timedelta
        fri = int((datetime.now() - timedelta(days=2)).strftime('%Y%m%d'))
        f = os.path.join(self.tmp, 'sh600150.day')
        _make_day_file(f, fri)
        self.assertTrue(is_kline_fresh(f, max_age_days=1))

    # ============ 路径解析 ============
    def test_resolve_kline_prefers_vipdoc_with_lday(self):
        """显式 vipdoc_dir 含 lday → 日K用它（本机结构）"""
        from tdx_path_resolver import resolve_vipdoc_for_kline
        os.environ['TDX_HOME'] = '/nonexistent/home'
        os.environ['TDX_VIPDOC_DIR'] = self.tmp
        os.makedirs(os.path.join(self.tmp, 'sh', 'lday'), exist_ok=True)
        self.assertEqual(resolve_vipdoc_for_kline(), self.tmp)

    def test_resolve_kline_prefers_home_vipdoc(self):
        """home/vipdoc 含 lday → 优先 TDX_HOME（tdx2 规则）"""
        from tdx_path_resolver import resolve_vipdoc_for_kline
        os.environ['TDX_HOME'] = self.tmp
        os.environ['TDX_VIPDOC_DIR'] = '/nonexistent/vip'
        os.makedirs(os.path.join(self.tmp, 'vipdoc', 'sh', 'lday'),
                    exist_ok=True)
        self.assertEqual(resolve_vipdoc_for_kline(),
                         os.path.join(self.tmp, 'vipdoc'))

    def test_resolve_fin_never_home(self):
        """财务目录 = VIPDOC_DIR，绝不等于 TDX_HOME/vipdoc"""
        from tdx_path_resolver import resolve_vipdoc_for_fin
        os.environ['TDX_HOME'] = self.tmp
        os.environ['TDX_VIPDOC_DIR'] = os.path.join(self.tmp, 'fin')
        fin = resolve_vipdoc_for_fin()
        self.assertEqual(fin, os.path.join(self.tmp, 'fin'))
        self.assertNotEqual(fin, os.path.join(self.tmp, 'vipdoc'))

    # ============ 财务新鲜度 ============
    def test_financial_fresh_with_new_gpcw(self):
        """最新 gpcw 报告期在缓冲期内 → 新鲜"""
        from tdx_path_resolver import is_financial_fresh
        from datetime import timedelta
        period = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        os.makedirs(os.path.join(self.tmp, 'cw'), exist_ok=True)
        open(os.path.join(self.tmp, 'cw', f'gpcw{period}.dat'), 'w').close()
        self.assertTrue(is_financial_fresh(self.tmp, max_age_days=30))

    def test_financial_stale_no_package(self):
        """无 gpcw 包 → 过期（走在线源）"""
        from tdx_path_resolver import is_financial_fresh
        self.assertFalse(is_financial_fresh(self.tmp, max_age_days=30))

    def test_day_file_path_structure(self):
        """日K路径: {dir}/{mkt}/lday/{mkt}{code}.day"""
        from tdx_path_resolver import day_file_path
        p = day_file_path('600150', self.tmp)
        self.assertEqual(p, os.path.join(self.tmp, 'sh', 'lday',
                                         'sh600150.day'))
        p2 = day_file_path('000001', self.tmp)
        self.assertEqual(p2, os.path.join(self.tmp, 'sz', 'lday',
                                          'sz000001.day'))

    def test_resolve_kline_dirs_home_first(self):
        """目录优先级: [home/vipdoc, vipdoc_dir]（用户要求: 优先TDX_HOME）"""
        from tdx_path_resolver import resolve_kline_dirs
        os.environ['TDX_HOME'] = self.tmp
        os.environ['TDX_VIPDOC_DIR'] = os.path.join(self.tmp, 'vip2')
        os.makedirs(os.path.join(self.tmp, 'vipdoc', 'sh', 'lday'),
                    exist_ok=True)
        os.makedirs(os.path.join(self.tmp, 'vip2', 'sh', 'lday'),
                    exist_ok=True)
        dirs = resolve_kline_dirs()
        self.assertEqual(dirs[0], os.path.join(self.tmp, 'vipdoc'))
        self.assertEqual(dirs[1], os.path.join(self.tmp, 'vip2'))

    def test_tdx_local_multi_dir_fallback(self):
        """TdxLocalClient: home 无该股 .day → 回退 vipdoc_dir 读取（用户要求）"""
        from tdx_path_resolver import resolve_kline_dirs, day_file_path
        os.environ['TDX_HOME'] = self.tmp
        os.environ['TDX_VIPDOC_DIR'] = self.tmp
        os.makedirs(os.path.join(self.tmp, 'vipdoc', 'sh', 'lday'),
                    exist_ok=True)
        os.makedirs(os.path.join(self.tmp, 'sh', 'lday'), exist_ok=True)
        # 股票 .day 只在 vipdoc_dir（tmp 根目录 sh/lday），home/vipdoc 没有
        _make_day_file(os.path.join(self.tmp, 'sh', 'lday',
                                    'sh600150.day'),
                       int(datetime.now().strftime('%Y%m%d')))
        import importlib
        from tdx_local_client import TdxLocalClient
        # config=None → 协议客户端禁用（不尝试连接行情服务器，测试快速失败）
        tc = TdxLocalClient(vipdoc_dir=None, enable=True, config=None)
        # home 优先目录无文件 → 回退到第二目录读取
        df = tc.get_daily_data('sh600150', '2026-01-01', '2026-12-31')
        self.assertFalse(df is None or df.empty)
        self.assertGreater(len(df), 0)


if __name__ == '__main__':
    unittest.main()
