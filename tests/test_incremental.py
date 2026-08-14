#!/usr/bin/env python3
# test_incremental.py - 增量更新测试（docs/step3.md 3.4.1）
"""测试: 增量幂等性、.day尾部读取、标准/扁平路径兼容"""
import os
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'data'))

import pandas as pd

from tdx_incremental import TdxIncremental

REC = '<IIIIIfII'


def write_day_file(path, dates, base_close=1000):
    """写入合成 .day 文件（32字节/条）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        for i, d in enumerate(dates):
            f.write(struct.pack(REC, int(d), base_close + i * 10,
                                base_close + i * 10 + 50, base_close + i * 10 - 10,
                                base_close + i * 10 + 20, 1e6, 100000 + i, 0))


class TestIncremental(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='hermes-test-inc-')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self, flat=False):
        if flat:
            path = os.path.join(self.tmp, 'sh\\lday\\sh999999.day')
        else:
            path = os.path.join(self.tmp, 'sh', 'lday', 'sh999999.day')
        write_day_file(path, ['20260810', '20260811', '20260812',
                              '20260813', '20260814'])
        return TdxIncremental(vipdoc_dir=self.tmp)

    def test_read_tail_after_last_date(self):
        """只读取 last_date 之后的数据"""
        inc = self._make()
        d = inc.fetch_delta('sh999999', '2026-08-12')
        self.assertEqual(len(d), 2)
        self.assertEqual(list(d['日期'].dt.strftime('%Y%m%d')),
                         ['20260813', '20260814'])

    def test_idempotent(self):
        """幂等: 重复调用结果一致"""
        inc = self._make()
        d1 = inc.fetch_delta('sh999999', '2026-08-10')
        d2 = inc.fetch_delta('sh999999', '2026-08-10')
        self.assertTrue(d1.equals(d2))

    def test_price_parse(self):
        """价格解析正确（分→元）"""
        inc = self._make()
        d = inc.fetch_delta('sh999999', '2026-08-12')
        self.assertEqual(d.iloc[0]['收盘价'], 10.50)  # 1030/100

    def test_flat_structure_compat(self):
        """扁平遗留结构兼容（反斜杠文件名）"""
        inc = self._make(flat=True)
        d = inc.fetch_delta('sh999999', '2026-08-12')
        self.assertEqual(len(d), 2)

    def test_no_file_returns_empty(self):
        """无.day文件返回空"""
        inc = TdxIncremental(vipdoc_dir=self.tmp)
        self.assertTrue(inc.fetch_delta('600001', None).empty)
        self.assertFalse(inc.has_local_data('600001'))

    def test_market_detection(self):
        """市场判定"""
        self.assertEqual(TdxIncremental._get_market('600150'), 'sh')
        self.assertEqual(TdxIncremental._get_market('000001'), 'sz')
        self.assertEqual(TdxIncremental._get_market('430017'), 'bj')


if __name__ == '__main__':
    unittest.main()
