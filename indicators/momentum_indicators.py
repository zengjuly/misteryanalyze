#!/usr/bin/env python3
# momentum_indicators.py - 动能技术指标计算
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

class MomentumIndicators:
    """动能技术指标计算"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_volume_ratio(self, data: pd.DataFrame, period: int = 5) -> pd.DataFrame:
        """
        计算量比
        :param data: 包含成交量的数据
        :param period: 量比计算周期
        :return: 添加量比的数据
        """
        try:
            result = data.copy()
            
            # 计算平均成交量
            result['VMA'] = result['成交量'].rolling(window=period).mean()
            
            # 计算量比
            result['量比'] = result['成交量'] / result['VMA']
            
            # 删除临时列
            result = result.drop(['VMA'], axis=1)
            
            self.logger.info(f"✅ 量比计算完成 (周期:{period})")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算量比异常: {e}")
            return data
    
    def calculate_turnover_rate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算换手率相关指标
        :param data: 包含换手率的数据
        :return: 添加换手率指标的数据
        """
        try:
            result = data.copy()
            
            # 计算换手率均线
            result['换手率MA5'] = result['换手率'].rolling(window=5).mean()
            result['换手率MA10'] = result['换手率'].rolling(window=10).mean()
            result['换手率MA20'] = result['换手率'].rolling(window=20).mean()
            
            # 计算换手率变化率
            result['换手率变化率'] = result['换手率'].pct_change() * 100
            
            # 计算换手率相对位置
            result['换手率相对位置'] = (result['换手率'] - result['换手率MA20']) / result['换手率MA20'] * 100
            
            # 标记换手率区域
            result['换手率区域'] = '未知'
            
            for i in range(len(result)):
                turnover = result.loc[i, '换手率']
                
                if pd.notna(turnover):
                    if turnover < 1:
                        result.loc[i, '换手率区域'] = '低迷'
                    elif turnover < 3:
                        result.loc[i, '换手率区域'] = '温和'
                    elif turnover < 5:
                        result.loc[i, '换手率区域'] = '吸筹'
                    elif turnover < 8:
                        result.loc[i, '换手率区域'] = '活跃'
                    else:
                        result.loc[i, '换手率区域'] = '放量'
                else:
                    result.loc[i, '换手率区域'] = '未知'
            
            self.logger.info("✅ 换手率指标计算完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算换手率指标异常: {e}")
            return data
    
    def calculate_volume_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算成交量信号
        :param data: 包含成交量数据
        :return: 添加成交量信号的数据
        """
        try:
            result = data.copy()
            
            # 检查必要的列
            required_cols = ['成交量', '量比', '换手率']
            missing_cols = [col for col in required_cols if col not in result.columns]
            
            if missing_cols:
                self.logger.warning(f"⚠️ 缺少必要列: {missing_cols}")
                return result
            
            # 初始化信号列
            result['成交量信号'] = 0  # 0: 无信号, 1: 放量信号, -1: 缩量信号
            
            # 计算放量缩量信号
            for i in range(1, len(result)):
                # 量比大于1.5视为放量
                if (pd.notna(result.iloc[i]['量比']) and result.iloc[i]['量比'] > 1.5):
                    result.iloc[i, result.columns.get_loc('成交量信号')] = 1
                
                # 量比小于0.5视为缩量
                elif (pd.notna(result.iloc[i]['量比']) and result.iloc[i]['量比'] < 0.5):
                    result.iloc[i, result.columns.get_loc('成交量信号')] = -1
            
            # 计算成交量突破信号
            result['成交量突破信号'] = 0  # 0: 无信号, 1: 向上突破, -1: 向下突破
            
            # 计算成交量均线
            result['成交量MA20'] = result['成交量'].rolling(window=20).mean()
            
            for i in range(1, len(result)):
                # 成交量突破20日均量1.5倍
                if (pd.notna(result.iloc[i-1]['成交量']) and pd.notna(result.iloc[i-1]['成交量MA20']) and
                    pd.notna(result.iloc[i]['成交量']) and pd.notna(result.iloc[i]['成交量MA20']) and
                    result.iloc[i-1]['成交量'] <= 1.5 * result.iloc[i-1]['成交量MA20'] and
                    result.iloc[i]['成交量'] > 1.5 * result.iloc[i]['成交量MA20']):
                    result.iloc[i, result.columns.get_loc('成交量突破信号')] = 1
                
                # 成交量跌破20日均量0.5倍
                elif (pd.notna(result.iloc[i-1]['成交量']) and pd.notna(result.iloc[i-1]['成交量MA20']) and
                      pd.notna(result.iloc[i]['成交量']) and pd.notna(result.iloc[i]['成交量MA20']) and
                      result.iloc[i-1]['成交量'] >= 0.5 * result.iloc[i-1]['成交量MA20'] and
                      result.iloc[i]['成交量'] < 0.5 * result.iloc[i-1]['成交量MA20']):
                    result.iloc[i, result.columns.get_loc('成交量突破信号')] = -1
            
            # 删除临时列
            result = result.drop(['成交量MA20'], axis=1)
            
            self.logger.info("✅ 成交量信号分析完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 分析成交量信号异常: {e}")
            return data
    
    def calculate_price_momentum(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算价格动能指标
        :param data: 包含价格数据
        :return: 添加价格动能指标的数据
        """
        try:
            result = data.copy()
            
            # 计算价格变化率
            result['价格变化率1日'] = result['收盘价'].pct_change() * 100
            result['价格变化率5日'] = result['收盘价'].pct_change(periods=5) * 100
            result['价格变化率10日'] = result['收盘价'].pct_change(periods=10) * 100
            result['价格变化率20日'] = result['收盘价'].pct_change(periods=20) * 100
            
            # 计算加速度（变化率的变化率）
            result['价格加速度5日'] = result['价格变化率5日'].diff()
            result['价格加速度10日'] = result['价格变化率10日'].diff()
            
            # 计算动能指标
            result['价格动能'] = result['价格变化率5日'] * 0.6 + result['价格变化率10日'] * 0.4
            
            # 计算相对强度
            if 'MA20' in result.columns:
                result['相对强度'] = (result['收盘价'] - result['MA20']) / result['MA20'] * 100
            
            # 计算价格波动率
            result['价格波动率'] = result['收盘价'].rolling(window=20).std() / result['收盘价'].rolling(window=20).mean() * 100
            
            # 标记价格动能状态
            result['动能状态'] = '未知'
            
            for i in range(len(result)):
                momentum = result.loc[i, '价格动能'] if '价格动能' in result.columns and pd.notna(result.loc[i, '价格动能']) else 0
                
                if pd.notna(momentum):
                    if momentum > 5:
                        result.loc[i, '动能状态'] = '强势'
                    elif momentum > 0:
                        result.loc[i, '动能状态'] = '温和'
                    elif momentum > -5:
                        result.loc[i, '动能状态'] = '弱势'
                    else:
                        result.loc[i, '动能状态'] = '低迷'
                else:
                    result.loc[i, '动能状态'] = '未知'
            
            self.logger.info("✅ 价格动能指标计算完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算价格动能指标异常: {e}")
            return data
    
    def calculate_volume_price_relation(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算量价关系指标
        :param data: 包含价格和成交量的数据
        :return: 添加量价关系指标的数据
        """
        try:
            result = data.copy()
            
            # 检查必要的列
            required_cols = ['收盘价', '成交量', '最高价', '最低价']
            missing_cols = [col for col in required_cols if col not in result.columns]
            
            if missing_cols:
                self.logger.warning(f"⚠️ 缺少必要列: {missing_cols}")
                return result
            
            # 计算价格变化
            price_change = result['收盘价'].diff()
            
            # 计算成交量变化
            volume_change = result['成交量'].diff()
            
            # 计算量价配合度
            result['量价配合度'] = 0
            
            for i in range(1, len(result)):
                # 上涨日成交量增加
                if (pd.notna(price_change.iloc[i]) and pd.notna(volume_change.iloc[i])):
                    if price_change.iloc[i] > 0 and volume_change.iloc[i] > 0:
                        result.loc[i, '量价配合度'] = 1  # 量价齐升
                    elif price_change.iloc[i] > 0 and volume_change.iloc[i] <= 0:
                        result.loc[i, '量价配合度'] = -1  # 上涨缩量
                    elif price_change.iloc[i] <= 0 and volume_change.iloc[i] > 0:
                        result.loc[i, '量价配合度'] = -1  # 下跌放量
                    else:
                        result.loc[i, '量价配合度'] = 0  # 量价齐跌
            
            # 计算OBV指标（On-Balance Volume）
            result['OBV'] = 0
            result['OBV_MA'] = 0
            
            for i in range(1, len(result)):
                if pd.notna(price_change.iloc[i]):
                    if price_change.iloc[i] > 0:
                        result.loc[i, 'OBV'] = result.loc[i-1, 'OBV'] + result.loc[i, '成交量']
                    elif price_change.iloc[i] < 0:
                        result.loc[i, 'OBV'] = result.loc[i-1, 'OBV'] - result.loc[i, '成交量']
                    else:
                        result.loc[i, 'OBV'] = result.loc[i-1, 'OBV']
            
            # 计算OBV均线
            result['OBV_MA'] = result['OBV'].rolling(window=20).mean()
            
            # 计算OBV信号
            result['OBV信号'] = 0  # 0: 无信号, 1: OBV突破均线, -1: OBV跌破均线
            
            for i in range(1, len(result)):
                if (pd.notna(result.iloc[i-1]['OBV_MA']) and pd.notna(result.iloc[i]['OBV_MA']) and
                    pd.notna(result.iloc[i-1]['OBV']) and pd.notna(result.iloc[i]['OBV'])):
                    
                    # OBV突破均线
                    if (result.iloc[i-1]['OBV'] <= result.iloc[i-1]['OBV_MA'] and 
                        result.iloc[i]['OBV'] > result.iloc[i]['OBV_MA']):
                        result.iloc[i, result.columns.get_loc('OBV信号')] = 1
                    
                    # OBV跌破均线
                    elif (result.iloc[i-1]['OBV'] >= result.iloc[i-1]['OBV_MA'] and 
                          result.iloc[i]['OBV'] < result.iloc[i]['OBV_MA']):
                        result.iloc[i, result.columns.get_loc('OBV信号')] = -1
            
            # 删除临时列
            result = result.drop(['price_change', 'volume_change'], axis=1, errors='ignore')
            
            self.logger.info("✅ 量价关系指标计算完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算量价关系指标异常: {e}")
            return data