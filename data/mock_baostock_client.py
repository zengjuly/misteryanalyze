# 模拟数据获取模块 - 用于演示和测试
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

class MockBaostockClient:
    """模拟 baostock 客户端，用于演示和测试"""
    
    def __init__(self):
        self.is_logged_in = False
        self.mock_data_cache = {}
    
    def login(self):
        """模拟登录"""
        self.is_logged_in = True
        print("模拟登录成功")
        return True
    
    def logout(self):
        """模拟登出"""
        self.is_logged_in = False
        print("模拟登出成功")
        return True
    
    def get_stock_data(self, stock_code, start_date, end_date):
        """获取模拟股票数据"""
        if not self.is_logged_in:
            raise Exception("请先登录")
        
        # 生成模拟数据
        data = self._generate_mock_data(stock_code, start_date, end_date)
        return data
    
    def get_industry_data(self, industry_code):
        """获取模拟行业数据"""
        if not self.is_logged_in:
            raise Exception("请先登录")
        
        # 生成模拟行业数据
        data = self._generate_mock_industry_data(industry_code)
        return data
    
    def _generate_mock_data(self, stock_code, start_date, end_date):
        """生成模拟股票数据"""
        # 解析日期
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        # 生成日期序列
        date_range = pd.date_range(start=start, end=end, freq='D')
        date_range = date_range[date_range.weekday < 5]  # 只保留工作日
        
        # 生成模拟价格数据
        n_days = len(date_range)
        base_price = random.uniform(10, 100)  # 基础价格
        
        # 生成开盘价
        open_prices = [base_price]
        for i in range(1, n_days):
            change = random.uniform(-0.05, 0.05)  # ±5% 的变化
            open_prices.append(open_prices[-1] * (1 + change))
        
        # 生成最高价和最低价
        high_prices = [op * random.uniform(1.0, 1.02) for op in open_prices]
        low_prices = [op * random.uniform(0.98, 1.0) for op in open_prices]
        
        # 生成收盘价
        close_prices = []
        for i in range(n_days):
            # 收盘价在开盘价和最高价之间
            close = random.uniform(low_prices[i], high_prices[i])
            close_prices.append(close)
        
        # 生成成交量
        volumes = [random.randint(1000000, 10000000) for _ in range(n_days)]
        
        # 创建DataFrame
        data = pd.DataFrame({
            'date': date_range,
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'volume': volumes,
            'code': stock_code
        })
        
        # 设置索引
        data.set_index('date', inplace=True)
        
        # 添加一些基本的技术指标
        data['ma5'] = data['close'].rolling(window=5).mean()
        data['ma10'] = data['close'].rolling(window=10).mean()
        data['ma20'] = data['close'].rolling(window=20).mean()
        data['ma60'] = data['close'].rolling(window=60).mean()
        
        return data
    
    def _generate_mock_industry_data(self, industry_code):
        """生成模拟行业数据"""
        # 生成模拟行业指数数据
        n_days = 252  # 一年的交易日
        base_price = 1000
        
        prices = [base_price]
        for i in range(1, n_days):
            change = random.uniform(-0.03, 0.03)  # ±3% 的变化
            prices.append(prices[-1] * (1 + change))
        
        date_range = pd.date_range(start=datetime.now() - timedelta(days=n_days), 
                                 end=datetime.now(), freq='D')
        date_range = date_range[date_range.weekday < 5]  # 只保留工作日
        
        data = pd.DataFrame({
            'date': date_range[:len(prices)],
            'close': prices,
            'industry_code': industry_code
        })
        
        data.set_index('date', inplace=True)
        return data

# 为了兼容性，保留原来的类名
class BaostockClient(MockBaostockClient):
    """保持兼容性"""
    pass