#!/usr/bin/env python3
# test_financial_retry.py - 财务查询登录重试与 ROE_年化 键缺失回归测试
"""测试: 会话失效自动重登 / ROE缺失不抛KeyError / 正常财务链路 (v1.18.1)

2026-08-19 真实 bug: baostock 会话中途失效时 get_financial_data 无重登保护，
64 只自选股财务查询全部静默失败 → 报表 ROE/EPS/PE/PB/股息率全 None；
且 ROE 为 None/0 时 financial_data['ROE_年化'] 直接 KeyError 中断整个财务函数。
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'data'))

import pandas as pd

import baostock_client
from baostock_client import BaostockClient


class FakeResult:
    """模拟 baostock 查询结果"""

    def __init__(self, error_code='0', error_msg='success', df=None):
        self.error_code = error_code
        self.error_msg = error_msg
        self._df = df if df is not None else pd.DataFrame()

    def get_data(self):
        return self._df


def make_profit_df(roe='0.032989', eps='1.502394', stat='2026-03-31'):
    return pd.DataFrame([{'code': 'sh.600150', 'statDate': stat,
                          'roeAvg': roe, 'epsTTM': eps}])


class FakeBS:
    """模拟 baostock 模块（含会话失效场景）"""

    def __init__(self, profit_df=None, profit_fail_first=False,
                 fail_msg='用户未登录'):
        self.login_calls = 0
        self.logout_calls = 0
        self.profit_df = profit_df if profit_df is not None else make_profit_df()
        self.profit_fail_first = profit_fail_first
        self.fail_msg = fail_msg

    def login(self):
        self.login_calls += 1
        return FakeResult('0', 'success')

    def logout(self):
        self.logout_calls += 1

    def query_profit_data(self, code=None, year=None, quarter=None):
        if self.profit_fail_first:
            self.profit_fail_first = False
            return FakeResult('1', self.fail_msg, None)
        return FakeResult('0', 'success', self.profit_df)

    def query_dividend_data(self, code=None, year=None, yearType=None):
        return FakeResult('0', 'success',
                          pd.DataFrame([{'dividCashPsBeforeTax': '0.75'}]))


class TestFinancialQueryRetry(unittest.TestCase):
    """财务查询会话失效自动重登（2026-08-19 真实 bug 回归）"""

    def setUp(self):
        self.client = BaostockClient()
        self.fake_bs = FakeBS()

    def test_session_dead_auto_relogin(self):
        """会话失效(用户未登录) → 自动 logout+login → 重试成功 → 财务数据完整"""
        self.fake_bs.profit_fail_first = True
        with mock.patch.object(baostock_client, 'bs', self.fake_bs):
            fd = self.client.get_financial_data('sh.600150', current_price=40.0)
        # 重试链路: 首次失败 → logout(1) + login(1) → 第二次成功
        self.assertEqual(self.fake_bs.logout_calls, 1)
        self.assertEqual(self.fake_bs.login_calls, 1)
        self.assertIsNotNone(fd['ROE'])
        self.assertIsNotNone(fd['EPS'])
        self.assertAlmostEqual(fd['ROE'], 0.032989, places=6)
        # Q1 累计 ROE 年化 ×4: 0.032989*4 = 0.131956 → 0.132
        self.assertAlmostEqual(fd['PB'], 40.0 / (1.502394 / 0.132), places=2)
        self.assertAlmostEqual(fd['PE'], round(40.0 / 1.502394, 2), places=2)
        # 股息率 = 0.75/40*100 = 1.88%
        self.assertAlmostEqual(fd['股息率'], 1.88, places=2)

    def test_network_error_msg_also_relogin(self):
        """error_msg 含'接收数据异常'（网络类）同样触发重登"""
        self.fake_bs.profit_fail_first = True
        self.fake_bs.fail_msg = '接收数据异常，请稍后再试。'
        with mock.patch.object(baostock_client, 'bs', self.fake_bs):
            fd = self.client.get_financial_data('sh.600150', current_price=40.0)
        self.assertEqual(self.fake_bs.login_calls, 1)
        self.assertIsNotNone(fd['ROE'])

    def test_roe_none_no_keyerror(self):
        """profit 查询全空 → ROE=None → 不得抛 KeyError('ROE_年化')"""
        self.fake_bs.profit_df = pd.DataFrame()  # 所有季度都空
        with mock.patch.object(baostock_client, 'bs', self.fake_bs):
            fd = self.client.get_financial_data('sh.600150', current_price=40.0)
        self.assertIsNone(fd['ROE'])
        self.assertIsNone(fd['PE'])
        self.assertIsNone(fd['PB'])
        # 股息数据与利润数据独立：ROE 缺失不影响股息率计算
        self.assertAlmostEqual(fd['股息率'], 1.88, places=2)

    def test_roe_zero_no_keyerror(self):
        """roeAvg='0' → ROE=0.0（falsy）→ ROE_年化 未设置 → 不得 KeyError"""
        self.fake_bs.profit_df = make_profit_df(roe='0', eps='1.0')
        with mock.patch.object(baostock_client, 'bs', self.fake_bs):
            fd = self.client.get_financial_data('sh.600150', current_price=40.0)
        self.assertEqual(fd['ROE'], 0.0)
        self.assertIsNotNone(fd['PE'])
        self.assertIsNone(fd['PB'])

    def test_normal_path_full_financials(self):
        """正常链路: 财务数据完整（PE/PB/股息率 均按当前价计算）"""
        with mock.patch.object(baostock_client, 'bs', self.fake_bs):
            fd = self.client.get_financial_data('sh.600150', current_price=40.0)
        self.assertEqual(self.fake_bs.login_calls, 0)  # 无需重登
        self.assertAlmostEqual(fd['ROE'], 0.032989, places=6)
        self.assertAlmostEqual(fd['EPS'], 1.502394, places=6)
        self.assertEqual(fd['报告期'], '2026-03-31')
        self.assertAlmostEqual(fd['每股股息'], 0.75, places=2)
        self.assertAlmostEqual(fd['股息率'], 1.88, places=2)

    def test_retry_exhausted_returns_none_dict(self):
        """重试一次后仍失败 → 返回全 None 字典（不抛异常）"""
        class AlwaysFail(FakeBS):
            def query_profit_data(self, code=None, year=None, quarter=None):
                return FakeResult('1', '用户未登录', None)
        fake = AlwaysFail()
        with mock.patch.object(baostock_client, 'bs', fake):
            fd = self.client.get_financial_data('sh.600150', current_price=40.0)
        self.assertIsNone(fd['ROE'])
        self.assertEqual(fake.login_calls, 3)  # 3 个季度各重登一次


if __name__ == '__main__':
    unittest.main()
