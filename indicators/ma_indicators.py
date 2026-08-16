#!/usr/bin/env python3
# ma_indicators.py - 均线系统技术指标计算
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

class MAIndicators:
    """均线系统技术指标计算"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_ma(self, data: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
        """
        计算均线
        :param data: 包含收盘价的数据
        :param periods: 均线周期列表，默认[5, 10, 20, 60, 250, 377, 610]（docs/081601.md）
        :return: 添加均线列的数据
        """
        if periods is None:
            periods = [5, 10, 20, 60, 250, 377, 610]
        
        try:
            result = data.copy()
            
            for period in periods:
                ma_col = f'MA{period}'
                result[ma_col] = result['收盘价'].rolling(window=period).mean()
                
                self.logger.debug(f"计算 {ma_col}: {result[ma_col].notna().sum()} 个有效值")
            
            self.logger.info(f"✅ 完成 {len(periods)} 条均线的计算")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算均线异常: {e}")
            return data
    
    def calculate_ema(self, data: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
        """计算指数移动平均 EMA（默认 EMA20，docs/081601.md）
        :param data: 包含收盘价的数据
        :param periods: EMA 周期列表，默认[20]
        :return: 添加 EMA{p} 列的数据
        """
        if periods is None:
            periods = [20]
        try:
            result = data.copy()
            close_col = '收盘价' if '收盘价' in result.columns else 'close'
            for p in periods:
                result[f'EMA{p}'] = result[close_col].ewm(span=p, adjust=False).mean()
            self.logger.info(f"✅ 完成 EMA 计算: {periods}")
            return result
        except Exception as e:
            self.logger.error(f"❌ 计算 EMA 异常: {e}")
            return data
    
    def calculate_ma_slope(self, data: pd.DataFrame, period: int = 5, slope_period: int = 5) -> pd.DataFrame:
        """
        计算均线斜率
        :param data: 包含均线的数据
        :param period: 目标均线周期
        :param slope_period: 斜率计算周期
        :return: 添加斜率列的数据
        """
        try:
            result = data.copy()
            ma_col = f'MA{period}'
            slope_col = f'{ma_col}_斜率'
            
            if ma_col in result.columns:
                # 计算斜率
                result[slope_col] = result[ma_col].diff(periods=slope_period) / slope_period
                
                self.logger.info(f"✅ 计算 {ma_col} 斜率完成")
            else:
                self.logger.warning(f"⚠️ {ma_col} 列不存在，无法计算斜率")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算均线斜率异常: {e}")
            return data
    
    def calculate_ma_arrangement(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算均线排列状态
        :param data: 包含多条均线的数据
        :return: 添加排列状态的数据
        """
        try:
            result = data.copy()
            
            # 检查必要的均线列是否存在
            ma_periods = [5, 10, 20, 60]
            ma_cols = [f'MA{p}' for p in ma_periods]
            
            missing_cols = [col for col in ma_cols if col not in result.columns]
            if missing_cols:
                self.logger.warning(f"⚠️ 缺少均线列: {missing_cols}")
                return result
            
            # 计算排列状态
            # 1: 多头排列 (MA5 > MA10 > MA20 > MA60)
            # 0: 混合排列
            # -1: 空头排列 (MA5 < MA10 < MA20 < MA60)
            arrangement = []
            
            for i in range(len(result)):
                ma_values = [result.loc[i, col] for col in ma_cols]
                
                # 过滤掉NaN值
                valid_values = [val for val in ma_values if pd.notna(val)]
                
                if len(valid_values) >= 3:  # 至少需要3条均线判断
                    is_bullish = True
                    is_bearish = True
                    
                    for j in range(len(valid_values) - 1):
                        if valid_values[j] <= valid_values[j + 1]:
                            is_bullish = False
                        if valid_values[j] >= valid_values[j + 1]:
                            is_bearish = False
                    
                    if is_bullish:
                        arrangement.append(1)  # 多头排列
                    elif is_bearish:
                        arrangement.append(-1)  # 空头排列
                    else:
                        arrangement.append(0)  # 混合排列
                else:
                    arrangement.append(np.nan)
            
            result['均线排列'] = arrangement
            
            # 计算排列强度（多头排列的均线数量）
            bullish_count = []
            for i in range(len(result)):
                if pd.notna(result.loc[i, '均线排列']):
                    if result.loc[i, '均线排列'] == 1:
                        # 统计当前周期有多少条均线满足多头排列
                        current_ma_values = [result.loc[i, col] for col in ma_cols]
                        valid_count = sum(1 for j in range(len(current_ma_values) - 1) 
                                        if pd.notna(current_ma_values[j]) and pd.notna(current_ma_values[j + 1])
                                        and current_ma_values[j] > current_ma_values[j + 1])
                        bullish_count.append(valid_count)
                    else:
                        bullish_count.append(0)
                else:
                    bullish_count.append(np.nan)
            
            result['多头排列强度'] = bullish_count
            
            self.logger.info("✅ 均线排列状态计算完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算均线排列状态异常: {e}")
            return data
    
    def calculate_ma_distance(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算价格与均线的距离
        :param data: 包含价格和均线的数据
        :return: 添加距离指标的数据
        """
        try:
            result = data.copy()
            
            # 计算价格相对于各条均线的距离百分比
            ma_periods = [5, 10, 20, 60, 250]
            
            for period in ma_periods:
                ma_col = f'MA{period}'
                distance_col = f'价格距{period}日均线'
                
                if ma_col in result.columns:
                    result[distance_col] = (result['收盘价'] - result[ma_col]) / result[ma_col] * 100
            
            # 计算价格与最近均线的距离
            result['价格距最近均线'] = np.nan
            
            for i in range(len(result)):
                # 找到最近的均线
                ma_distances = []
                for period in ma_periods:
                    ma_col = f'MA{period}'
                    if ma_col in result.columns and pd.notna(result.loc[i, ma_col]):
                        distance = abs(result.loc[i, '收盘价'] - result.loc[i, ma_col]) / result.loc[i, ma_col] * 100
                        ma_distances.append((distance, period))
                
                if ma_distances:
                    min_distance, min_period = min(ma_distances)
                    result.loc[i, '价格距最近均线'] = min_distance
            
            self.logger.info("✅ 价格与均线距离计算完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算均线距离异常: {e}")
            return data
    
    def analyze_ma_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        分析均线信号
        :param data: 包含均线的数据
        :return: 添加信号列的数据
        """
        try:
            result = data.copy()
            
            # 检查必要的均线列
            required_cols = ['收盘价', 'MA5', 'MA10', 'MA20', 'MA60', 'MA250']
            missing_cols = [col for col in required_cols if col not in result.columns]
            
            if missing_cols:
                self.logger.warning(f"⚠️ 缺少必要列: {missing_cols}")
                return result
            
            # 初始化信号列
            result['均线信号'] = 0  # 0: 无信号, 1: 金叉信号, -1: 死叉信号
            
            # 计算金叉死叉信号
            for i in range(1, len(result)):
                # MA5金叉MA10
                if (pd.notna(result.iloc[i-1]['MA5']) and pd.notna(result.iloc[i-1]['MA10']) and
                    pd.notna(result.iloc[i]['MA5']) and pd.notna(result.iloc[i]['MA10']) and
                    result.iloc[i-1]['MA5'] <= result.iloc[i-1]['MA10'] and
                    result.iloc[i]['MA5'] > result.iloc[i]['MA10']):
                    result.iloc[i, result.columns.get_loc('均线信号')] = 1
                
                # MA5死叉MA10
                elif (pd.notna(result.iloc[i-1]['MA5']) and pd.notna(result.iloc[i-1]['MA10']) and
                      pd.notna(result.iloc[i]['MA5']) and pd.notna(result.iloc[i]['MA10']) and
                      result.iloc[i-1]['MA5'] >= result.iloc[i-1]['MA10'] and
                      result.iloc[i]['MA5'] < result.iloc[i]['MA10']):
                    result.iloc[i, result.columns.get_loc('均线信号')] = -1
            
            # 计算突破信号
            result['突破信号'] = 0  # 0: 无信号, 1: 向上突破, -1: 向下突破
            
            for i in range(1, len(result)):
                # 向上突破MA20
                if (pd.notna(result.iloc[i-1]['收盘价']) and pd.notna(result.iloc[i-1]['MA20']) and
                    pd.notna(result.iloc[i]['收盘价']) and pd.notna(result.iloc[i]['MA20']) and
                    result.iloc[i-1]['收盘价'] <= result.iloc[i-1]['MA20'] and
                    result.iloc[i]['收盘价'] > result.iloc[i]['MA20']):
                    result.iloc[i, result.columns.get_loc('突破信号')] = 1
                
                # 向下突破MA20
                elif (pd.notna(result.iloc[i-1]['收盘价']) and pd.notna(result.iloc[i-1]['MA20']) and
                      pd.notna(result.iloc[i]['收盘价']) and pd.notna(result.iloc[i]['MA20']) and
                      result.iloc[i-1]['收盘价'] >= result.iloc[i-1]['MA20'] and
                      result.iloc[i]['收盘价'] < result.iloc[i]['MA20']):
                    result.iloc[i, result.columns.get_loc('突破信号')] = -1
            
            self.logger.info("✅ 均线信号分析完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 分析均线信号异常: {e}")
            return data