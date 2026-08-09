#!/usr/bin/env python3
# pattern_recognition.py - 形态识别模块
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

class PatternRecognition:
    """形态识别模块"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def recognize_head_and_shoulders(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        识别头肩顶/头肩底形态
        :param data: K线数据
        :return: 形态识别结果
        """
        try:
            result = {
                '形态类型': '无',
                '形态状态': '未知',
                '左肩位置': None,
                '头部位置': None,
                '右肩位置': None,
                '颈线位置': None,
                '可靠性': 0,
                '目标价位': None,
                '详情': []
            }
            
            if len(data) < 60:  # 需要足够的数据
                result['详情'].append("数据不足，无法识别头肩形态")
                return result
            
            # 获取最近60天的数据
            recent_data = data.tail(60)
            
            # 简化的头肩形态识别算法
            # 寻找三个明显的波峰和波谷
            
            # 计算局部极值
            highs = []
            lows = []
            
            for i in range(2, len(recent_data) - 2):
                # 检查是否是局部高点
                if (recent_data.iloc[i]['最高价'] > recent_data.iloc[i-1]['最高价'] and
                    recent_data.iloc[i]['最高价'] > recent_data.iloc[i+1]['最高价'] and
                    recent_data.iloc[i]['最高价'] > recent_data.iloc[i-2]['最高价'] and
                    recent_data.iloc[i]['最高价'] > recent_data.iloc[i+2]['最高价']):
                    highs.append(i)
                
                # 检查是否是局部低点
                if (recent_data.iloc[i]['最低价'] < recent_data.iloc[i-1]['最低价'] and
                    recent_data.iloc[i]['最低价'] < recent_data.iloc[i+1]['最低价'] and
                    recent_data.iloc[i]['最低价'] < recent_data.iloc[i-2]['最低价'] and
                    recent_data.iloc[i]['最低价'] < recent_data.iloc[i+2]['最低价']):
                    lows.append(i)
            
            # 寻找头肩形态
            if len(highs) >= 3:
                # 按时间排序
                highs_sorted = sorted(highs)
                
                # 检查是否有三个波峰形成头肩形态
                for i in range(len(highs_sorted) - 2):
                    left_shoulder = highs_sorted[i]
                    head = highs_sorted[i + 1]
                    right_shoulder = highs_sorted[i + 2]
                    
                    # 检查时间间隔
                    if head - left_shoulder > 5 and right_shoulder - head > 5:
                        # 检查高度关系
                        left_shoulder_high = recent_data.iloc[left_shoulder]['最高价']
                        head_high = recent_data.iloc[head]['最高价']
                        right_shoulder_high = recent_data.iloc[right_shoulder]['最高价']
                        
                        # 头部最高，左右肩较低
                        if head_high > left_shoulder_high and head_high > right_shoulder_high:
                            # 寻找颈线（两个低点的连线）
                            if i + 1 < len(lows):
                                neck_line_idx = lows[i + 1]
                                neck_line_price = recent_data.iloc[neck_line_idx]['最低价']
                                
                                result['形态类型'] = '头肩顶'
                                result['形态状态'] = '形成中'
                                result['左肩位置'] = left_shoulder
                                result['头部位置'] = head
                                result['右肩位置'] = right_shoulder
                                result['颈线位置'] = neck_line_price
                                result['可靠性'] = 70
                                
                                # 计算目标价位
                                head_to_neck = head_high - neck_line_price
                                target_price = neck_line_price - head_to_neck
                                result['目标价位'] = target_price
                                
                                result['详情'].append(f"头肩顶形态形成: 左肩={left_shoulder}, 头部={head}, 右肩={right_shoulder}")
                                result['详情'].append(f"颈线位置: {neck_line_price:.2f}, 目标价位: {target_price:.2f}")
                                break
            
            if len(lows) >= 3:
                # 按时间排序
                lows_sorted = sorted(lows)
                
                # 检查是否有三个波谷形成倒头肩形态
                for i in range(len(lows_sorted) - 2):
                    left_shoulder = lows_sorted[i]
                    head = lows_sorted[i + 1]
                    right_shoulder = lows_sorted[i + 2]
                    
                    # 检查时间间隔
                    if head - left_shoulder > 5 and right_shoulder - head > 5:
                        # 检查深度关系
                        left_shoulder_low = recent_data.iloc[left_shoulder]['最低价']
                        head_low = recent_data.iloc[head]['最低价']
                        right_shoulder_low = recent_data.iloc[right_shoulder]['最低价']
                        
                        # 头部最低，左右肩较高
                        if head_low < left_shoulder_low and head_low < right_shoulder_low:
                            # 寻找颈线（两个高点的连线）
                            if i + 1 < len(highs):
                                neck_line_idx = highs[i + 1]
                                neck_line_price = recent_data.iloc[neck_line_idx]['最高价']
                                
                                result['形态类型'] = '头肩底'
                                result['形态状态'] = '形成中'
                                result['左肩位置'] = left_shoulder
                                result['头部位置'] = head
                                result['右肩位置'] = right_shoulder
                                result['颈线位置'] = neck_line_price
                                result['可靠性'] = 70
                                
                                # 计算目标价位
                                neck_to_head = neck_line_price - head_low
                                target_price = neck_line_price + neck_to_head
                                result['目标价位'] = target_price
                                
                                result['详情'].append(f"头肩底形态形成: 左肩={left_shoulder}, 头部={head}, 右肩={right_shoulder}")
                                result['详情'].append(f"颈线位置: {neck_line_price:.2f}, 目标价位: {target_price:.2f}")
                                break
            
            self.logger.info(f"🔄 头肩形态识别: {result['形态类型']}, 可靠性={result['可靠性']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 识别头肩形态异常: {e}")
            return {'形态类型': '异常', '详情': [f"识别异常: {e}"]}
    
    def recognize_double_top_bottom(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        识别双重顶/双重底形态
        :param data: K线数据
        :return: 形态识别结果
        """
        try:
            result = {
                '形态类型': '无',
                '形态状态': '未知',
                '第一个顶/底位置': None,
                '第二个顶/底位置': None,
                '颈线位置': None,
                '可靠性': 0,
                '目标价位': None,
                '详情': []
            }
            
            if len(data) < 40:  # 需要足够的数据
                result['详情'].append("数据不足，无法识别双重形态")
                return result
            
            # 获取最近40天的数据
            recent_data = data.tail(40)
            
            # 寻找双重顶形态
            highs = []
            for i in range(2, len(recent_data) - 2):
                if (recent_data.iloc[i]['最高价'] > recent_data.iloc[i-1]['最高价'] and
                    recent_data.iloc[i]['最高价'] > recent_data.iloc[i+1]['最高价']):
                    highs.append(i)
            
            if len(highs) >= 2:
                # 检查是否有两个相近的高点
                for i in range(len(highs) - 1):
                    first_high = highs[i]
                    second_high = highs[i + 1]
                    
                    # 检查时间间隔
                    if 5 <= second_high - first_high <= 15:
                        # 检查价格差异
                        first_price = recent_data.iloc[first_high]['最高价']
                        second_price = recent_data.iloc[second_high]['最高价']
                        
                        # 价格差异小于5%
                        price_diff = abs(first_price - second_price) / first_price * 100
                        if price_diff < 5:
                            # 寻找颈线（两个高点之间的低点）
                            low_idx = (first_high + second_high) // 2
                            if low_idx < len(recent_data):
                                neck_price = recent_data.iloc[low_idx]['最低价']
                                
                                result['形态类型'] = '双重顶'
                                result['形态状态'] = '形成中'
                                result['第一个顶/底位置'] = first_high
                                result['第二个顶/底位置'] = second_high
                                result['颈线位置'] = neck_price
                                result['可靠性'] = 75
                                
                                # 计算目标价位
                                height = first_price - neck_price
                                target_price = neck_price - height
                                result['目标价位'] = target_price
                                
                                result['详情'].append(f"双重顶形态形成: 第一个顶={first_high}, 第二个顶={second_high}")
                                result['详情'].append(f"颈线位置: {neck_price:.2f}, 目标价位: {target_price:.2f}")
                                break
            
            # 寻找双重底形态
            lows = []
            for i in range(2, len(recent_data) - 2):
                if (recent_data.iloc[i]['最低价'] < recent_data.iloc[i-1]['最低价'] and
                    recent_data.iloc[i]['最低价'] < recent_data.iloc[i+1]['最低价']):
                    lows.append(i)
            
            if len(lows) >= 2:
                # 检查是否有两个相近的低点
                for i in range(len(lows) - 1):
                    first_low = lows[i]
                    second_low = lows[i + 1]
                    
                    # 检查时间间隔
                    if 5 <= second_low - first_low <= 15:
                        # 检查价格差异
                        first_price = recent_data.iloc[first_low]['最低价']
                        second_price = recent_data.iloc[second_low]['最低价']
                        
                        # 价格差异小于5%
                        price_diff = abs(first_price - second_price) / first_price * 100
                        if price_diff < 5:
                            # 寻找颈线（两个低点之间的高点）
                            high_idx = (first_low + second_low) // 2
                            if high_idx < len(recent_data):
                                neck_price = recent_data.iloc[high_idx]['最高价']
                                
                                result['形态类型'] = '双重底'
                                result['形态状态'] = '形成中'
                                result['第一个顶/底位置'] = first_low
                                result['第二个顶/底位置'] = second_low
                                result['颈线位置'] = neck_price
                                result['可靠性'] = 75
                                
                                # 计算目标价位
                                depth = neck_price - first_price
                                target_price = neck_price + depth
                                result['目标价位'] = target_price
                                
                                result['详情'].append(f"双重底形态形成: 第一个底={first_low}, 第二个底={second_low}")
                                result['详情'].append(f"颈线位置: {neck_price:.2f}, 目标价位: {target_price:.2f}")
                                break
            
            self.logger.info(f"🔄 双重形态识别: {result['形态类型']}, 可靠性={result['可靠性']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 识别双重形态异常: {e}")
            return {'形态类型': '异常', '详情': [f"识别异常: {e}"]}
    
    def recognize_triangle_pattern(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        识别三角形整理形态
        :param data: K线数据
        :return: 形态识别结果
        """
        try:
            result = {
                '形态类型': '无',
                '形态状态': '未知',
                '收敛程度': 0,
                '突破方向': '未知',
                '可靠性': 0,
                '目标价位': None,
                '详情': []
            }
            
            if len(data) < 30:  # 需要足够的数据
                result['详情'].append("数据不足，无法识别三角形形态")
                return result
            
            # 获取最近30天的数据
            recent_data = data.tail(30)
            
            # 计算价格波动范围
            price_range = recent_data['最高价'].max() - recent_data['最低价'].min()
            avg_price = recent_data['收盘价'].mean()
            
            # 计算波动率
            volatility = price_range / avg_price * 100
            
            # 如果波动率逐渐减小，可能是三角形整理
            if volatility < 15:  # 波动率小于15%
                # 检查是否是收敛的
                first_half_volatility = recent_data.head(15)['最高价'].max() - recent_data.head(15)['最低价'].min()
                second_half_volatility = recent_data.tail(15)['最高价'].max() - recent_data.tail(15)['最低价'].min()
                
                if second_half_volatility < first_half_volatility:
                    # 识别三角形类型
                    first_high = recent_data.iloc[0]['最高价']
                    last_high = recent_data.iloc[-1]['最高价']
                    first_low = recent_data.iloc[0]['最低价']
                    last_low = recent_data.iloc[-1]['最低价']
                    
                    if last_high < first_high and last_low > first_low:
                        result['形态类型'] = '对称三角形'
                    elif last_high < first_high and last_low < first_low:
                        result['形态类型'] = '下降三角形'
                    elif last_high > first_high and last_low > first_low:
                        result['形态类型'] = '上升三角形'
                    else:
                        result['形态类型'] = '三角形整理'
                    
                    result['形态状态'] = '整理中'
                    result['收敛程度'] = (first_half_volatility - second_half_volatility) / first_half_volatility * 100
                    result['可靠性'] = 60
                    
                    # 预测突破方向
                    if result['形态类型'] == '上升三角形':
                        result['突破方向'] = '向上'
                    elif result['形态类型'] == '下降三角形':
                        result['突破方向'] = '向下'
                    else:
                        # 对称三角形，根据最近趋势判断
                        if recent_data.iloc[-1]['收盘价'] > recent_data.iloc[-5]['收盘价']:
                            result['突破方向'] = '向上'
                        else:
                            result['突破方向'] = '向下'
                    
                    result['详情'].append(f"三角形整理形态: {result['形态类型']}")
                    result['详情'].append(f"收敛程度: {result['收敛程度']:.1f}%")
                    result['详情'].append(f"预期突破方向: {result['突破方向']}")
            
            self.logger.info(f"🔄 三角形形态识别: {result['形态类型']}, 可靠性={result['可靠性']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 识别三角形形态异常: {e}")
            return {'形态类型': '异常', '详情': [f"识别异常: {e}"]}
    
    def recognize_wedge_pattern(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        识别楔形整理形态
        :param data: K线数据
        :return: 形态识别结果
        """
        try:
            result = {
                '形态类型': '无',
                '形态状态': '未知',
                '倾斜方向': '未知',
                '可靠性': 0,
                '目标价位': None,
                '详情': []
            }
            
            if len(data) < 25:  # 需要足够的数据
                result['详情'].append("数据不足，无法识别楔形形态")
                return result
            
            # 获取最近25天的数据
            recent_data = data.tail(25)
            
            # 计算趋势线
            highs = []
            lows = []
            
            for i in range(len(recent_data)):
                highs.append(recent_data.iloc[i]['最高价'])
                lows.append(recent_data.iloc[i]['最低价'])
            
            # 计算高点和低点的线性趋势
            x = np.arange(len(recent_data))
            
            # 高点趋势线
            high_slope = np.polyfit(x, highs, 1)[0]
            # 低点趋势线
            low_slope = np.polyfit(x, lows, 1)[0]
            
            # 判断楔形形态
            if abs(high_slope) > 0.01 or abs(low_slope) > 0.01:  # 有明显倾斜
                if high_slope > 0 and low_slope > 0:
                    # 上升楔形
                    result['形态类型'] = '上升楔形'
                    result['倾斜方向'] = '向上'
                    result['形态状态'] = '看跌'
                elif high_slope < 0 and low_slope < 0:
                    # 下降楔形
                    result['形态类型'] = '下降楔形'
                    result['倾斜方向'] = '向下'
                    result['形态状态'] = '看涨'
                else:
                    # 混合楔形
                    result['形态类型'] = '混合楔形'
                    result['倾斜方向'] = '混合'
                    result['形态状态'] = '观望'
                
                # 计算可靠性
                convergence = abs(high_slope - low_slope)
                result['可靠性'] = min(convergence * 1000, 80)  # 最高80分
                
                result['详情'].append(f"楔形形态识别: {result['形态类型']}")
                result['详情'].append(f"高点斜率: {high_slope:.4f}, 低点斜率: {low_slope:.4f}")
                result['详情'].append(f"可靠性: {result['可靠性']:.1f}%")
            
            self.logger.info(f"🔄 楔形形态识别: {result['形态类型']}, 可靠性={result['可靠性']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 识别楔形形态异常: {e}")
            return {'形态类型': '异常', '详情': [f"识别异常: {e}"]}
    
    def recognize_all_patterns(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        识别所有形态
        :param data: K线数据
        :return: 所有形态识别结果
        """
        try:
            result = {
                '头肩形态': self.recognize_head_and_shoulders(data),
                '双重形态': self.recognize_double_top_bottom(data),
                '三角形形态': self.recognize_triangle_pattern(data),
                '楔形形态': self.recognize_wedge_pattern(data),
                '主要形态': '无',
                '形态置信度': 0,
                '详情': []
            }
            
            # 确定主要形态和置信度
            patterns = ['头肩形态', '双重形态', '三角形形态', '楔形形态']
            max_confidence = 0
            main_pattern = '无'
            
            for pattern in patterns:
                pattern_result = result[pattern]
                if pattern_result['可靠性'] > max_confidence:
                    max_confidence = pattern_result['可靠性']
                    main_pattern = pattern_result['形态类型']
            
            result['主要形态'] = main_pattern
            result['形态置信度'] = max_confidence
            
            if max_confidence > 50:
                result['详情'].append(f"主要形态: {main_pattern} (置信度: {max_confidence:.1f}%)")
            else:
                result['详情'].append("未发现明确的形态")
            
            self.logger.info(f"🎯 形态识别完成: 主要形态={main_pattern}, 置信度={max_confidence}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 识别所有形态异常: {e}")
            return {'主要形态': '异常', '详情': [f"识别异常: {e}"]}