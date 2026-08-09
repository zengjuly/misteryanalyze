#!/usr/bin/env python3
# data_processor.py - 数据预处理模块
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
from typing import List, Dict, Optional, Tuple
from .baostock_client import BaostockClient

class DataProcessor:
    """数据处理器"""
    
    def __init__(self, baostock_client: BaostockClient):
        self.client = baostock_client
        self.logger = logging.getLogger(__name__)
        
    def process_stock_data(self, stock_code: str, days: int = 1000) -> Dict[str, pd.DataFrame]:
        """
        处理单个股票的多周期数据
        :param stock_code: 股票代码
        :param days: 获取的天数
        :return: 包含日线、周线、月线数据的字典
        """
        try:
            # 计算日期范围
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # 获取多周期数据
            daily_data = self.client.get_daily_data(stock_code, start_date, end_date)
            weekly_data = self.client.get_weekly_data(stock_code, start_date, end_date)
            monthly_data = self.client.get_monthly_data(stock_code, start_date, end_date)
            
            # 过滤空数据
            result = {}
            if not daily_data.empty:
                result['daily'] = daily_data
            if not weekly_data.empty:
                result['weekly'] = weekly_data
            if not monthly_data.empty:
                result['monthly'] = monthly_data
                
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 处理 {stock_code} 数据异常: {e}")
            return {}
    
    def get_all_stocks_data(self, stock_codes: List[str], max_workers: int = 5) -> Dict[str, Dict]:
        """
        批量获取所有股票数据
        :param stock_codes: 股票代码列表
        :param max_workers: 最大并发数
        :return: 股票代码到数据的映射
        """
        all_data = {}
        
        # 按批次处理以避免请求过于频繁
        batch_size = 50
        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i:i + batch_size]
            self.logger.info(f"🔄 正在处理第 {i//batch_size + 1} 批股票，共 {len(batch)} 只")
            
            for code in batch:
                try:
                    stock_data = self.process_stock_data(code)
                    if stock_data:
                        all_data[code] = stock_data
                        self.logger.info(f"✅ {code} 数据获取成功")
                    else:
                        self.logger.warning(f"⚠️ {code} 无有效数据")
                    
                    # 添加延迟避免请求过于频繁
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.error(f"❌ 处理 {code} 失败: {e}")
                    continue
            
            # 批次间稍作延迟
            if i + batch_size < len(stock_codes):
                time.sleep(2)
        
        self.logger.info(f"🎉 完成 {len(all_data)} 只股票的数据获取")
        return all_data
    
    def get_market_index_data(self) -> Dict[str, pd.DataFrame]:
        """获取主要市场指数数据"""
        indices = {
            'sh000001': '上证指数',  # 上证综指
            'sh000300': '沪深300',  # 沪深300
            'sz399006': '创业板指',  # 创业板指
            'sz399001': '深证成指',  # 深证成指
        }
        
        index_data = {}
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        for code, name in indices.items():
            try:
                data = self.client.get_index_data(code, start_date, end_date)
                if not data.empty:
                    index_data[name] = data
                    self.logger.info(f"✅ 获取 {name} 数据成功")
                else:
                    self.logger.warning(f"⚠️ {name} 无数据")
            except Exception as e:
                self.logger.error(f"❌ 获取 {name} 数据失败: {e}")
        
        return index_data
    
    def calculate_basic_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算基础指标"""
        try:
            if data.empty:
                return data
            
            # 计算均线
            data['MA5'] = data['收盘价'].rolling(window=5).mean()
            data['MA10'] = data['收盘价'].rolling(window=10).mean()
            data['MA20'] = data['收盘价'].rolling(window=20).mean()
            data['MA60'] = data['收盘价'].rolling(window=60).mean()
            data['MA250'] = data['收盘价'].rolling(window=250).mean()
            
            # 计算成交量相关指标
            data['VMA5'] = data['成交量'].rolling(window=5).mean()
            data['VMA10'] = data['成交量'].rolling(window=10).mean()
            data['VMA20'] = data['成交量'].rolling(window=20).mean()
            
            # 计算量比
            data['量比'] = data['成交量'] / data['VMA5']
            
            # 计算换手率相关指标
            data['换手率MA5'] = data['换手率'].rolling(window=5).mean()
            data['换手率MA10'] = data['换手率'].rolling(window=10).mean()
            
            # 计算涨跌幅相关指标
            data['涨跌幅MA5'] = data['涨跌幅'].rolling(window=5).mean()
            
            # 计算振幅
            data['振幅'] = (data['最高价'] - data['最低价']) / data['收盘价'] * 100
            
            # 计算价格相对位置
            data['价格相对MA20'] = (data['收盘价'] - data['MA20']) / data['MA20'] * 100
            data['价格相对MA60'] = (data['收盘价'] - data['MA60']) / data['MA60'] * 100
            
            self.logger.info(f"✅ {len(data)} 条数据基础指标计算完成")
            return data
            
        except Exception as e:
            self.logger.error(f"❌ 计算基础指标异常: {e}")
            return data
    
    def validate_data_quality(self, data: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        验证数据质量
        :return: (是否通过验证, 错误信息列表)
        """
        errors = []
        
        if data.empty:
            errors.append("数据为空")
            return False, errors
        
        # 检查必要列是否存在
        required_columns = ['收盘价', '成交量', '最高价', '最低价', '开盘价']
        missing_cols = [col for col in required_columns if col not in data.columns]
        if missing_cols:
            errors.append(f"缺少必要列: {missing_cols}")
        
        # 检查数据完整性
        for col in required_columns:
            if col in data.columns:
                na_count = data[col].isna().sum()
                if na_count > len(data) * 0.1:  # 超过10%为空
                    errors.append(f"{col} 列缺失数据过多: {na_count}/{len(data)}")
        
        # 检查数据合理性
        if '收盘价' in data.columns:
            invalid_prices = data[(data['收盘价'] <= 0) | (data['收盘价'] > 10000)]
            if not invalid_prices.empty:
                errors.append(f"存在异常价格数据: {len(invalid_prices)} 条")
        
        if '成交量' in data.columns:
            invalid_volume = data[data['成交量'] < 0]
            if not invalid_volume.empty:
                errors.append(f"存在异常成交量数据: {len(invalid_volume)} 条")
        
        return len(errors) == 0, errors
    
    def clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """清理数据"""
        try:
            if data.empty:
                return data
            
            # 移除重复数据
            data = data.drop_duplicates()
            
            # 处理异常值
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            
            for col in numeric_cols:
                # 使用IQR方法处理异常值
                Q1 = data[col].quantile(0.25)
                Q3 = data[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                # 将异常值替换为边界值
                data[col] = np.where(data[col] < lower_bound, lower_bound, data[col])
                data[col] = np.where(data[col] > upper_bound, upper_bound, data[col])
            
            # 填充缺失值
            data = data.fillna(method='ffill')  # 向前填充
            data = data.fillna(method='bfill')  # 向后填充
            
            self.logger.info(f"✅ 数据清理完成，剩余 {len(data)} 条记录")
            return data
            
        except Exception as e:
            self.logger.error(f"❌ 数据清理异常: {e}")
            return data
    
    def get_stock_basic_info(self, stock_code: str) -> Dict:
        """获取股票基本信息"""
        try:
            stock_list = self.client.get_stock_list()
            stock_info = stock_list[stock_list['code'] == stock_code]
            
            if not stock_info.empty:
                info = stock_info.iloc[0].to_dict()
                return info
            else:
                self.logger.warning(f"⚠️ 未找到股票 {stock_code} 的基本信息")
                return {}
                
        except Exception as e:
            self.logger.error(f"❌ 获取股票 {stock_code} 基本信息异常: {e}")
            return {}