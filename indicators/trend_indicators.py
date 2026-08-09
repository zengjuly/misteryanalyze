#!/usr/bin/env python3
# trend_indicators.py - 趋势技术指标计算（MACD, RSI等）
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

class TrendIndicators:
    """趋势技术指标计算"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_macd(self, data: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> pd.DataFrame:
        """
        计算MACD指标
        :param data: 包含收盘价的数据
        :param fast_period: 快线周期
        :param slow_period: 慢线周期
        :param signal_period: 信号线周期
        :return: 添加MACD指标的数据
        """
        try:
            result = data.copy()
            
            # 计算EMA
            result['EMA12'] = result['收盘价'].ewm(span=fast_period, adjust=False).mean()
            result['EMA26'] = result['收盘价'].ewm(span=slow_period, adjust=False).mean()
            
            # 计算MACD线
            result['MACD'] = result['EMA12'] - result['EMA26']
            
            # 计算信号线
            result['MACD_Signal'] = result['MACD'].ewm(span=signal_period, adjust=False).mean()
            
            # 计算MACD柱状图
            result['MACD_Histogram'] = result['MACD'] - result['MACD_Signal']
            
            # 计算MACD面积（用于判断背驰）
            result['MACD_Area'] = result['MACD'].cumsum()
            
            # 删除临时列
            result = result.drop(['EMA12', 'EMA26'], axis=1)
            
            self.logger.info(f"✅ MACD指标计算完成 (快线:{fast_period}, 慢线:{slow_period}, 信号:{signal_period})")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算MACD指标异常: {e}")
            return data
    
    def calculate_rsi(self, data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        计算RSI指标
        :param data: 包含收盘价的数据
        :param period: RSI周期
        :return: 添加RSI指标的数据
        """
        try:
            result = data.copy()
            
            # 计算价格变化
            delta = result['收盘价'].diff()
            
            # 分离涨跌
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            # 计算平均涨跌幅
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()
            
            # 计算RS
            rs = avg_gain / avg_loss
            
            # 计算RSI
            result['RSI'] = 100 - (100 / (1 + rs))
            
            # 删除临时列
            result = result.drop(['delta', 'gain', 'loss', 'avg_gain', 'avg_loss', 'rs'], axis=1, errors='ignore')
            
            self.logger.info(f"✅ RSI指标计算完成 (周期:{period})")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算RSI指标异常: {e}")
            return data
    
    def analyze_macd_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        分析MACD信号
        :param data: 包含MACD指标的数据
        :return: 添加MACD信号的数据
        """
        try:
            result = data.copy()
            
            # 检查必要的列
            required_cols = ['MACD', 'MACD_Signal', 'MACD_Histogram']
            missing_cols = [col for col in required_cols if col not in result.columns]
            
            if missing_cols:
                self.logger.warning(f"⚠️ 缺少MACD必要列: {missing_cols}")
                return result
            
            # 初始化信号列
            result['MACD_信号'] = 0  # 0: 无信号, 1: 金叉, -1: 死叉
            
            # 计算金叉死叉信号
            for i in range(1, len(result)):
                # MACD金叉信号线
                if (pd.notna(result.iloc[i-1]['MACD']) and pd.notna(result.iloc[i-1]['MACD_Signal']) and
                    pd.notna(result.iloc[i]['MACD']) and pd.notna(result.iloc[i]['MACD_Signal']) and
                    result.iloc[i-1]['MACD'] <= result.iloc[i-1]['MACD_Signal'] and
                    result.iloc[i]['MACD'] > result.iloc[i]['MACD_Signal']):
                    result.iloc[i, result.columns.get_loc('MACD_信号')] = 1
                
                # MACD死叉信号线
                elif (pd.notna(result.iloc[i-1]['MACD']) and pd.notna(result.iloc[i-1]['MACD_Signal']) and
                      pd.notna(result.iloc[i]['MACD']) and pd.notna(result.iloc[i]['MACD_Signal']) and
                      result.iloc[i-1]['MACD'] >= result.iloc[i-1]['MACD_Signal'] and
                      result.iloc[i]['MACD'] < result.iloc[i]['MACD_Signal']):
                    result.iloc[i, result.columns.get_loc('MACD_信号')] = -1
            
            # 计算零轴突破信号
            result['MACD_零轴信号'] = 0  # 0: 无信号, 1: 上穿零轴, -1: 下穿零轴
            
            for i in range(1, len(result)):
                # MACD上穿零轴
                if (pd.notna(result.iloc[i-1]['MACD']) and pd.notna(result.iloc[i]['MACD']) and
                    result.iloc[i-1]['MACD'] <= 0 and result.iloc[i]['MACD'] > 0):
                    result.iloc[i, result.columns.get_loc('MACD_零轴信号')] = 1
                
                # MACD下穿零轴
                elif (pd.notna(result.iloc[i-1]['MACD']) and pd.notna(result.iloc[i]['MACD']) and
                      result.iloc[i-1]['MACD'] >= 0 and result.iloc[i]['MACD'] < 0):
                    result.iloc[i, result.columns.get_loc('MACD_零轴信号')] = -1
            
            # 计算柱状图信号
            result['MACD_柱状图信号'] = 0  # 0: 无信号, 1: 柱状图由绿转红, -1: 柱状图由红转绿
            
            for i in range(1, len(result)):
                # 柱状图由负转正（绿转红）
                if (pd.notna(result.iloc[i-1]['MACD_Histogram']) and pd.notna(result.iloc[i]['MACD_Histogram']) and
                    result.iloc[i-1]['MACD_Histogram'] <= 0 and result.iloc[i]['MACD_Histogram'] > 0):
                    result.iloc[i, result.columns.get_loc('MACD_柱状图信号')] = 1
                
                # 柱状图由正转负（红转绿）
                elif (pd.notna(result.iloc[i-1]['MACD_Histogram']) and pd.notna(result.iloc[i]['MACD_Histogram']) and
                      result.iloc[i-1]['MACD_Histogram'] >= 0 and result.iloc[i]['MACD_Histogram'] < 0):
                    result.iloc[i, result.columns.get_loc('MACD_柱状图信号')] = -1
            
            self.logger.info("✅ MACD信号分析完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 分析MACD信号异常: {e}")
            return data
    
    def analyze_rsi_signals(self, data: pd.DataFrame, oversold: float = 30, overbought: float = 70) -> pd.DataFrame:
        """
        分析RSI信号
        :param data: 包含RSI指标的数据
        :param oversold: 超卖阈值
        :param overbought: 超买阈值
        :return: 添加RSI信号的数据
        """
        try:
            result = data.copy()
            
            # 检查RSI列是否存在
            if 'RSI' not in result.columns:
                self.logger.warning("⚠️ RSI列不存在，无法分析信号")
                return result
            
            # 初始化信号列
            result['RSI_信号'] = 0  # 0: 无信号, 1: 超卖反弹, -1: 超买回调
            
            # 计算超卖超买信号
            for i in range(1, len(result)):
                # 从超卖区反弹
                if (pd.notna(result.iloc[i-1]['RSI']) and pd.notna(result.iloc[i]['RSI']) and
                    result.iloc[i-1]['RSI'] <= oversold and result.iloc[i]['RSI'] > oversold):
                    result.iloc[i, result.columns.get_loc('RSI_信号')] = 1
                
                # 从超买区回调
                elif (pd.notna(result.iloc[i-1]['RSI']) and pd.notna(result.iloc[i]['RSI']) and
                      result.iloc[i-1]['RSI'] >= overbought and result.iloc[i]['RSI'] < overbought):
                    result.iloc[i, result.columns.get_loc('RSI_信号')] = -1
            
            # 计算RSI趋势信号
            result['RSI_趋势信号'] = 0  # 0: 无信号, 1: RSI上升趋势, -1: RSI下降趋势
            
            for i in range(2, len(result)):
                # RSI上升趋势
                if (pd.notna(result.iloc[i-2]['RSI']) and pd.notna(result.iloc[i-1]['RSI']) and pd.notna(result.iloc[i]['RSI']) and
                    result.iloc[i-2]['RSI'] < result.iloc[i-1]['RSI'] < result.iloc[i]['RSI']):
                    result.iloc[i, result.columns.get_loc('RSI_趋势信号')] = 1
                
                # RSI下降趋势
                elif (pd.notna(result.iloc[i-2]['RSI']) and pd.notna(result.iloc[i-1]['RSI']) and pd.notna(result.iloc[i]['RSI']) and
                      result.iloc[i-2]['RSI'] > result.iloc[i-1]['RSI'] > result.iloc[i]['RSI']):
                    result.iloc[i, result.columns.get_loc('RSI_趋势信号')] = -1
            
            self.logger.info(f"✅ RSI信号分析完成 (超卖:{oversold}, 超买:{overbought})")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 分析RSI信号异常: {e}")
            return data
    
    def calculate_trend_strength(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        计算趋势强度
        :param data: 包含价格和均线的数据
        :return: 添加趋势强度的数据
        """
        try:
            result = data.copy()
            
            # 检查必要的列
            required_cols = ['收盘价', 'MA5', 'MA10', 'MA20', 'MA60']
            missing_cols = [col for col in required_cols if col not in result.columns]
            
            if missing_cols:
                self.logger.warning(f"⚠️ 缺少必要列: {missing_cols}")
                return result
            
            # 计算趋势强度指标（使用float类型避免int赋值溢出）
            result['趋势强度'] = 0.0
            
            for i in range(len(result)):
                # 计算价格与各均线的距离
                distances = []
                for period in [5, 10, 20, 60]:
                    ma_col = f'MA{period}'
                    if ma_col in result.columns and pd.notna(result.loc[i, ma_col]):
                        distance = abs(result.loc[i, '收盘价'] - result.loc[i, ma_col]) / result.loc[i, ma_col] * 100
                        distances.append(distance)
                
                if distances:
                    # 计算平均距离
                    avg_distance = np.mean(distances)
                    
                    # 计算均线排列得分
                    arrangement_score = 0
                    if '均线排列' in result.columns and pd.notna(result.loc[i, '均线排列']):
                        arrangement_score = result.loc[i, '均线排列']
                    
                    # 综合趋势强度
                    trend_strength = avg_distance * 0.7 + arrangement_score * 30
                    result.loc[i, '趋势强度'] = trend_strength
            
            # 标准化趋势强度
            if '趋势强度' in result.columns:
                min_strength = result['趋势强度'].min()
                max_strength = result['趋势强度'].max()
                
                if max_strength > min_strength:
                    result['趋势强度_normalized'] = (result['趋势强度'] - min_strength) / (max_strength - min_strength) * 100
                else:
                    result['趋势强度_normalized'] = 0
            
            self.logger.info("✅ 趋势强度计算完成")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算趋势强度异常: {e}")
            return data