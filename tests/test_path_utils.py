#!/usr/bin/env python3
# test_path_utils.py - 路径解析工具测试（docs/step3.md 3.4.1）
"""测试环境变量覆盖路径解析"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'utils'))

from path_utils import resolve_path, resolve_path_abs, get_env_or


class TestResolvePath(unittest.TestCase):

    def tearDown(self):
        os.environ.pop('TDX_VIPDOC_DIR', None)

    def test_env_priority(self):
        """环境变量 > 配置值 > 默认值"""
        os.environ['TDX_VIPDOC_DIR'] = '/tmp/env_dir'
        self.assertEqual(resolve_path('TDX_VIPDOC_DIR', '/cfg/dir',
                                      '/default/dir'), '/tmp/env_dir')

    def test_config_fallback(self):
        """无环境变量时用配置值"""
        os.environ.pop('TDX_VIPDOC_DIR', None)
        self.assertEqual(resolve_path('TDX_VIPDOC_DIR', '/cfg/dir',
                                      '/default/dir'), '/cfg/dir')

    def test_default_fallback(self):
        """无环境变量无配置时用默认值"""
        os.environ.pop('TDX_VIPDOC_DIR', None)
        self.assertEqual(resolve_path('TDX_VIPDOC_DIR', None,
                                      '/default/dir'), '/default/dir')

    def test_empty_env_ignored(self):
        """空环境变量视为未设置"""
        os.environ['TDX_VIPDOC_DIR'] = '   '
        self.assertEqual(resolve_path('TDX_VIPDOC_DIR', '/cfg/dir'), '/cfg/dir')

    def test_resolve_path_abs(self):
        """相对路径转绝对"""
        os.environ.pop('TDX_VIPDOC_DIR', None)
        p = resolve_path_abs('TDX_VIPDOC_DIR', 'data/tdx_vipdoc',
                             base_dir='/tmp/base')
        self.assertEqual(p, '/tmp/base/data/tdx_vipdoc')

    def test_get_env_or(self):
        """便捷包装"""
        os.environ.pop('TDX_VIPDOC_DIR', None)
        self.assertEqual(get_env_or('TDX_VIPDOC_DIR', 'fallback'), 'fallback')
        os.environ['TDX_VIPDOC_DIR'] = '/env'
        self.assertEqual(get_env_or('TDX_VIPDOC_DIR', 'fallback'), '/env')


if __name__ == '__main__':
    unittest.main()
