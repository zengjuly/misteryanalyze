#!/usr/bin/env python3
# baostock_client.py - 基于Baostock的股票数据获取模块
import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
from typing import List, Dict, Optional, Tuple

class BaostockClient:
    """Baostock数据获取客户端"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.login_success = False
        
    def login(self) -> bool:
        """登录Baostock"""
        try:
            lg = bs.login()
            if lg.error_code == '0':
                self.login_success = True
                self.logger.info("✅ Baostock登录成功")
                return True
            else:
                self.logger.error(f"❌ Baostock登录失败: {lg.error_msg}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Baostock登录异常: {e}")
            return False
    
    def logout(self):
        """退出Baostock"""
        if self.login_success:
            bs.logout()
            self.logger.info("👋 Baostock已退出登录")
    
    def get_stock_list(self) -> pd.DataFrame:
        """获取A股股票列表"""
        try:
            result = bs.query_stock_basic()
            if result.error_code == '0':
                stock_list = result.get_data()
                self.logger.info(f"📋 获取到 {len(stock_list)} 只A股")
                return stock_list
            else:
                self.logger.error(f"❌ 获取股票列表失败: {result.error_msg}")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"❌ 获取股票列表异常: {e}")
            return pd.DataFrame()
    
    def get_daily_data(self, stock_code: str, start_date: str, end_date: str, 
                     adjustflag: str = '3') -> pd.DataFrame:
        """
        获取日线数据
        :param stock_code: 股票代码，格式如sh.600000或sz.000001
        :param start_date: 开始日期，格式如'2023-01-01'
        :param end_date: 结束日期，格式如'2023-12-31'
        :param adjustflag: 复权类型，默认'3'为后复权
        :return: 日线数据DataFrame
        """
        try:
            result = bs.query_history_k_data_plus(
                stock_code, 
                "date,code,open,high,low,close,volume,amount,turn,tradestatus,pctChg,isST",
                start_date=start_date, 
                end_date=end_date,
                frequency="d",
                adjustflag=adjustflag
            )
            
            if result.error_code == '0':
                data = result.get_data()
                if not data.empty:
                    # 数据类型转换
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
                    for col in numeric_cols:
                        if col in data.columns:
                            data[col] = pd.to_numeric(data[col], errors='coerce')
                    
                    # 标准化列名
                    data = data.rename(columns={
                        'code': '代码',
                        'open': '开盘价',
                        'high': '最高价', 
                        'low': '最低价',
                        'close': '收盘价',
                        'volume': '成交量',
                        'amount': '成交额',
                        'turn': '换手率',
                        'pctChg': '涨跌幅',
                        'isST': '是否ST'
                    })
                    
                    # 过滤ST股票
                    data = data[data['是否ST'] != 'ST']
                    
                    self.logger.info(f"📈 获取 {stock_code} 日线数据: {len(data)} 条记录")
                    return data
                else:
                    self.logger.warning(f"⚠️ {stock_code} 无日线数据")
                    return pd.DataFrame()
            else:
                self.logger.error(f"❌ 获取 {stock_code} 日线数据失败: {result.error_msg}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"❌ 获取 {stock_code} 日线数据异常: {e}")
            return pd.DataFrame()
    
    def get_weekly_data(self, stock_code: str, start_date: str, end_date: str,
                       adjustflag: str = '3') -> pd.DataFrame:
        """获取周线数据"""
        try:
            result = bs.query_history_k_data_plus(
                stock_code,
                "date,code,open,high,low,close,volume,amount,turn,tradestatus,pctChg,isST",
                start_date=start_date,
                end_date=end_date,
                frequency="w",
                adjustflag=adjustflag
            )
            
            if result.error_code == '0':
                data = result.get_data()
                if not data.empty:
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
                    for col in numeric_cols:
                        if col in data.columns:
                            data[col] = pd.to_numeric(data[col], errors='coerce')
                    
                    data = data.rename(columns={
                        'code': '代码',
                        'open': '开盘价',
                        'high': '最高价',
                        'low': '最低价', 
                        'close': '收盘价',
                        'volume': '成交量',
                        'amount': '成交额',
                        'turn': '换手率',
                        'pctChg': '涨跌幅',
                        'isST': '是否ST'
                    })
                    
                    data = data[data['是否ST'] != 'ST']
                    
                    self.logger.info(f"📊 获取 {stock_code} 周线数据: {len(data)} 条记录")
                    return data
                else:
                    self.logger.warning(f"⚠️ {stock_code} 无周线数据")
                    return pd.DataFrame()
            else:
                self.logger.error(f"❌ 获取 {stock_code} 周线数据失败: {result.error_msg}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"❌ 获取 {stock_code} 周线数据异常: {e}")
            return pd.DataFrame()
    
    def get_monthly_data(self, stock_code: str, start_date: str, end_date: str,
                        adjustflag: str = '3') -> pd.DataFrame:
        """获取月线数据"""
        try:
            result = bs.query_history_k_data_plus(
                stock_code,
                "date,code,open,high,low,close,volume,amount,turn,tradestatus,pctChg,isST",
                start_date=start_date,
                end_date=end_date,
                frequency="m",
                adjustflag=adjustflag
            )
            
            if result.error_code == '0':
                data = result.get_data()
                if not data.empty:
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
                    for col in numeric_cols:
                        if col in data.columns:
                            data[col] = pd.to_numeric(data[col], errors='coerce')
                    
                    data = data.rename(columns={
                        'code': '代码',
                        'open': '开盘价',
                        'high': '最高价',
                        'low': '最低价',
                        'close': '收盘价',
                        'volume': '成交量',
                        'amount': '成交额',
                        'turn': '换手率',
                        'pctChg': '涨跌幅',
                        'isST': '是否ST'
                    })
                    
                    data = data[data['是否ST'] != 'ST']
                    
                    self.logger.info(f"📅 获取 {stock_code} 月线数据: {len(data)} 条记录")
                    return data
                else:
                    self.logger.warning(f"⚠️ {stock_code} 无月线数据")
                    return pd.DataFrame()
            else:
                self.logger.error(f"❌ 获取 {stock_code} 月线数据失败: {result.error_msg}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"❌ 获取 {stock_code} 月线数据异常: {e}")
            return pd.DataFrame()
    
    def get_financial_data(self, stock_code: str) -> Dict:
        """获取财务数据"""
        try:
            # 获取盈利能力指标
            profit_data = bs.query_profit_data(code=stock_code, year=2024, quarter=3)
            if profit_data.error_code == '0':
                profit_df = profit_data.get_data()
            else:
                profit_df = pd.DataFrame()
            
            # 获取估值指标
            valuation_data = bs.query_valuation_data(code=stock_code, year=2024, quarter=3)
            if valuation_data.error_code == '0':
                valuation_df = valuation_data.get_data()
            else:
                valuation_df = pd.DataFrame()
            
            # 获取成长指标
            growth_data = bs.query_growth_data(code=stock_code, year=2024, quarter=3)
            if growth_data.error_code == '0':
                growth_df = growth_data.get_data()
            else:
                growth_df = pd.DataFrame()
            
            # 合并财务数据
            financial_data = {}
            for df, category in [(profit_df, '盈利能力'), (valuation_df, '估值指标'), (growth_df, '成长指标')]:
                if not df.empty:
                    financial_data[category] = df.set_index('statName').to_dict()
            
            return financial_data
            
        except Exception as e:
            self.logger.error(f"❌ 获取 {stock_code} 财务数据异常: {e}")
            return {}
    
    def get_industry_data(self) -> pd.DataFrame:
        """获取行业板块数据"""
        try:
            result = bs.query_stock_industry()
            if result.error_code == '0':
                industry_data = result.get_data()
                self.logger.info(f"🏢 获取到 {len(industry_data)} 个行业板块")
                return industry_data
            else:
                self.logger.error(f"❌ 获取行业板块数据失败: {result.error_msg}")
                return pd.DataFrame()
        except Exception as e:
            self.logger.error(f"❌ 获取行业板块数据异常: {e}")
            return pd.DataFrame()
    
    def get_index_data(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数数据（用于大盘分析）"""
        try:
            result = bs.query_history_k_data_plus(
                index_code,
                "date,code,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3"
            )
            
            if result.error_code == '0':
                data = result.get_data()
                if not data.empty:
                    numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
                    for col in numeric_cols:
                        if col in data.columns:
                            data[col] = pd.to_numeric(data[col], errors='coerce')
                    
                    data = data.rename(columns={
                        'code': '代码',
                        'open': '开盘价',
                        'high': '最高价',
                        'low': '最低价',
                        'close': '收盘价',
                        'volume': '成交量',
                        'amount': '成交额',
                        'turn': '换手率',
                        'pctChg': '涨跌幅'
                    })
                    
                    self.logger.info(f"📊 获取 {index_code} 指数数据: {len(data)} 条记录")
                    return data
                else:
                    self.logger.warning(f"⚠️ {index_code} 无指数数据")
                    return pd.DataFrame()
            else:
                self.logger.error(f"❌ 获取 {index_code} 指数数据失败: {result.error_msg}")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"❌ 获取 {index_code} 指数数据异常: {e}")
            return pd.DataFrame()