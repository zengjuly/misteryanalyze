#!/usr/bin/env python3
# mystery_logic.py - Mystery趋势交易论核心分析逻辑
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from indicators.ma_indicators import MAIndicators
from indicators.trend_indicators import TrendIndicators
from indicators.momentum_indicators import MomentumIndicators

class MysteryLogic:
    """Mystery趋势交易论核心分析逻辑"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ma_indicators = MAIndicators()
        self.trend_indicators = TrendIndicators()
        self.momentum_indicators = MomentumIndicators()
    
    def basic_filter(self, data: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        基础过滤器（一票否决制）
        :param data: 包含技术指标的数据
        :return: (是否通过, 错误信息列表)
        """
        errors = []
        passed = True
        
        try:
            # 检查必要的列
            required_cols = ['收盘价', 'MA5', 'MA10', 'MA20', 'MA60', 'MA250']
            missing_cols = [col for col in required_cols if col not in data.columns]
            
            if missing_cols:
                errors.append(f"缺少必要技术指标列: {missing_cols}")
                passed = False
                return passed, errors
            
            # 获取最新数据点
            latest_data = data.iloc[-1]
            
            # 1. 年线过滤：股价必须运行在250日均线之上
            if pd.notna(latest_data['MA250']) and pd.notna(latest_data['收盘价']):
                if latest_data['收盘价'] < latest_data['MA250']:
                    errors.append("股价未运行在250日均线上方")
                    passed = False
            else:
                errors.append("年线数据缺失")
                passed = False
            
            # 2. 周线过滤：检查周线级别是否运行在60周均线之上且处于上升趋势
            # 这里简化处理，使用日线数据近似判断
            if pd.notna(latest_data['MA60']) and pd.notna(latest_data['收盘价']):
                if latest_data['收盘价'] < latest_data['MA60']:
                    errors.append("股价未运行在60日均线上方")
                    passed = False
            
            # 3. 排列要求：均线需呈现多头顺次排列（MA5 > MA10 > MA20 > MA60）
            if '均线排列' in data.columns and pd.notna(latest_data['均线排列']):
                if latest_data['均线排列'] != 1:  # 1表示多头排列
                    errors.append("均线未呈现多头顺次排列")
                    passed = False
            else:
                # 手动检查均线排列
                ma_check = True
                for i, period in enumerate([5, 10, 20, 60]):
                    if i < 3:  # 检查相邻均线
                        ma_col1 = f'MA{period}'
                        ma_col2 = f'MA{period+5}'
                        if (pd.notna(latest_data[ma_col1]) and pd.notna(latest_data[ma_col2]) and
                            latest_data[ma_col1] <= latest_data[ma_col2]):
                            ma_check = False
                            break
                
                if not ma_check:
                    errors.append("均线未呈现多头顺次排列")
                    passed = False
            
            self.logger.info(f"{'✅' if passed else '❌'} 基础过滤 {'通过' if passed else '失败'}: {len(errors)} 个错误")
            return passed, errors
            
        except Exception as e:
            self.logger.error(f"❌ 基础过滤异常: {e}")
            errors.append(f"基础过滤异常: {e}")
            return False, errors
    
    def three_resonance_analysis(self, data: pd.DataFrame, market_data: Dict = None,
                                 industry_trend: bool = None) -> Dict[str, Any]:
        """
        三振共振选股法（个股 + 行业 + 大盘）
        :param data: 个股数据（含技术指标）
        :param market_data: 大盘指数数据字典 {指数名: DataFrame}（可选）
        :param industry_trend: 行业趋势判断结果 True/False/None（可选，由外部计算）
        :return: 共振分析结果
        """
        try:
            result = {
                '个股趋势': False,
                '行业趋势': False,
                '大盘趋势': False,
                '三级共振': False,
                '详情': []
            }
            
            # 1. 个股趋势判断
            if '均线排列' in data.columns and pd.notna(data.iloc[-1]['均线排列']):
                if data.iloc[-1]['均线排列'] == 1:
                    result['个股趋势'] = True
                    result['详情'].append("个股均线多头排列")
            
            # 检查价格位置
            if 'MA20' in data.columns and '收盘价' in data.columns:
                if pd.notna(data.iloc[-1]['MA20']) and pd.notna(data.iloc[-1]['收盘价']):
                    if data.iloc[-1]['收盘价'] > data.iloc[-1]['MA20']:
                        result['个股趋势'] = True
                        result['详情'].append("股价运行在20日均线上方")
            
            if not result['个股趋势']:
                result['详情'].append("个股趋势：均线未多头排列或股价在20日线下方")
            
            # 2. 行业趋势判断（使用外部传入的真实行业数据）
            if industry_trend is True:
                result['行业趋势'] = True
                result['详情'].append("行业板块同步走强")
            elif industry_trend is False:
                result['行业趋势'] = False
                result['详情'].append("行业板块走弱")
            else:
                result['行业趋势'] = False
                result['详情'].append("行业趋势数据缺失")
            
            # 3. 大盘趋势判断（使用真实指数数据）
            if market_data:
                # 优先使用上证指数
                index_name = '上证指数' if '上证指数' in market_data else (list(market_data.keys())[0] if market_data else None)
                if index_name:
                    index_data = market_data[index_name]
                    if index_data is not None and not index_data.empty:
                        # 计算指数MA20（若不存在）
                        if 'MA20' not in index_data.columns and '收盘价' in index_data.columns:
                            index_data = index_data.copy()
                            index_data['MA20'] = index_data['收盘价'].rolling(20).mean()
                            index_data['MA60'] = index_data['收盘价'].rolling(60).mean()
                        
                        latest_index = index_data.iloc[-1]
                        if 'MA20' in index_data.columns and '收盘价' in index_data.columns:
                            if (pd.notna(latest_index['MA20']) and pd.notna(latest_index['收盘价'])):
                                if latest_index['收盘价'] > latest_index['MA20']:
                                    result['大盘趋势'] = True
                                    result['详情'].append(f"大盘({index_name})运行在20日均线上方")
                                else:
                                    result['详情'].append(f"大盘({index_name})运行在20日均线下方")
                            else:
                                result['详情'].append("大盘MA20数据不足")
            else:
                result['大盘趋势'] = False
                result['详情'].append("大盘趋势数据缺失")
            
            # 4. 三级共振判断
            if result['个股趋势'] and result['行业趋势'] and result['大盘趋势']:
                result['三级共振'] = True
                result['详情'].append("✅ 三级共振成立")
            else:
                result['详情'].append("❌ 三级共振不成立")
            
            self.logger.info(f"{'✅' if result['三级共振'] else '❌'} 三振共振分析: {result['详情']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 三振共振分析异常: {e}")
            return {'三级共振': False, '详情': [f"分析异常: {e}"]}
    
    def main_bull_wave_analysis(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        强势主升浪/空中加油逻辑
        :param data: 包含技术指标的数据
        :return: 主升浪分析结果
        """
        try:
            result = {
                '主升浪状态': '未知',
                '持股状态': False,
                '空中加油': False,
                'MA5斜率': 0,
                '详情': []
            }
            
            # 检查必要的列
            required_cols = ['收盘价', 'MA5', 'MA20', '量比', '换手率']
            missing_cols = [col for col in required_cols if col not in data.columns]
            
            if missing_cols:
                result['详情'].append(f"缺少必要列: {missing_cols}")
                return result
            
            # 获取最新数据点
            latest_data = data.iloc[-1]
            
            # 1. 计算MA5斜率
            if len(data) >= 5:
                ma5_values = data['MA5'].tail(5).dropna()
                if len(ma5_values) >= 2:
                    slope = (ma5_values.iloc[-1] - ma5_values.iloc[0]) / 4
                    result['MA5斜率'] = slope
                    
                    # 判断斜率强度
                    if slope > 0.5:
                        result['详情'].append("MA5斜率强劲，处于加速段")
                    elif slope > 0:
                        result['详情'].append("MA5斜率温和，处于上升段")
                    else:
                        result['详情'].append("MA5斜率平缓或下降")
            
            # 2. 持股状态判断：股价沿MA5上涨，不破MA5则标记为"主升持股期"
            if (pd.notna(latest_data['收盘价']) and pd.notna(latest_data['MA5']) and
                latest_data['收盘价'] > latest_data['MA5']):
                
                # 检查最近5天是否都在MA5上方
                recent_5_days = data.tail(5)
                above_ma5_count = sum(1 for i in range(len(recent_5_days)) 
                                    if pd.notna(recent_5_days.iloc[i]['收盘价']) and 
                                    pd.notna(recent_5_days.iloc[i]['MA5']) and
                                    recent_5_days.iloc[i]['收盘价'] > recent_5_days.iloc[i]['MA5'])
                
                if above_ma5_count >= 3:  # 至少3天在MA5上方
                    result['持股状态'] = True
                    result['主升浪状态'] = '主升持股期'
                    result['详情'].append("✅ 主升持股期：股价沿MA5上涨")
            
            # 3. 空中加油识别：前期强势上涨后，缩量横盘整理（不破MA20），且筹码峰在低位不动
            if (pd.notna(latest_data['收盘价']) and pd.notna(latest_data['MA20']) and
                latest_data['收盘价'] > latest_data['MA20']):
                
                # 检查最近20天的振幅
                recent_20_days = data.tail(20)
                if len(recent_20_days) >= 10:
                    # 计算振幅
                    amplitude = (recent_20_days['最高价'].max() - recent_20_days['最低价'].min()) / recent_20_days['收盘价'].mean() * 100
                    
                    if amplitude < 15:  # 振幅小于15%
                        # 检查成交量是否缩量
                        if '量比' in data.columns and pd.notna(latest_data['量比']):
                            if latest_data['量比'] < 1.0:  # 量比小于1
                                result['空中加油'] = True
                                result['主升浪状态'] = '空中加油'
                                result['详情'].append("✅ 空中加油形态：缩量横盘整理")
            
            # 4. 综合判断
            if result['持股状态']:
                result['主升浪状态'] = '主升持股期'
            elif result['空中加油']:
                result['主升浪状态'] = '空中加油'
            elif result['MA5斜率'] > 0:
                result['主升浪状态'] = '强势上升'
            else:
                result['主升浪状态'] = '观望'
            
            self.logger.info(f"📈 主升浪分析: {result['主升浪状态']}, {result['详情']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 主升浪分析异常: {e}")
            return {'主升浪状态': '异常', '详情': [f"分析异常: {e}"]}
    
    def platform_breakthrough_analysis(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        平台突破与"买横"战法
        :param data: 包含技术指标的数据
        :return: 平台突破分析结果
        """
        try:
            result = {
                '平台状态': '未知',
                '突破信号': False,
                '买横信号': False,
                '详情': []
            }
            
            # 检查必要的列
            required_cols = ['收盘价', 'MA20', '成交量', '量比', 'MACD', 'MACD_Signal']
            missing_cols = [col for col in required_cols if col not in data.columns]
            
            if missing_cols:
                result['详情'].append(f"缺少必要列: {missing_cols}")
                return result
            
            # 获取最近20天数据
            recent_20_days = data.tail(20)
            
            # 1. 横盘识别：识别股价在20日内振幅小于15%的"长期横盘"区间
            if len(recent_20_days) >= 10:
                # 计算振幅
                high_price = recent_20_days['最高价'].max()
                low_price = recent_20_days['最低价'].min()
                avg_price = recent_20_days['收盘价'].mean()
                
                if pd.notna(high_price) and pd.notna(low_price) and pd.notna(avg_price) and avg_price > 0:
                    amplitude = (high_price - low_price) / avg_price * 100
                    
                    if amplitude < 15:  # 振幅小于15%
                        result['平台状态'] = '横盘整理'
                        result['详情'].append(f"横盘整理：振幅{amplitude:.1f}%")
                        
                        # 检查是否在MA20上方
                        latest_data = data.iloc[-1]
                        if (pd.notna(latest_data['收盘价']) and pd.notna(latest_data['MA20']) and
                            latest_data['收盘价'] > latest_data['MA20']):
                            
                            # 2. 突破判断：放量突破箱体上沿（成交量需高于前均量1.5倍），MACD零轴上金叉
                            if '量比' in data.columns and pd.notna(latest_data['量比']):
                                if latest_data['量比'] > 1.5:
                                    result['详情'].append("放量突破：量比>1.5")
                                    
                                    # 检查MACD金叉
                                    if ('MACD_信号' in data.columns and pd.notna(latest_data['MACD_信号']) and
                                        latest_data['MACD_信号'] == 1):
                                        
                                        result['突破信号'] = True
                                        result['平台状态'] = '突破确认'
                                        result['详情'].append("✅ MACD零轴上金叉，突破确认")
                            
                            # 3. 买横信号：横盘期间逢低买入
                            if not result['突破信号']:
                                # 检查是否接近平台下沿
                                platform_low = recent_20_days['最低价'].min()
                                current_price = latest_data['收盘价']
                                
                                if pd.notna(platform_low) and pd.notna(current_price):
                                    distance_from_low = (current_price - platform_low) / platform_low * 100
                                    
                                    if distance_from_low < 5:  # 距离平台下沿不到5%
                                        result['买横信号'] = True
                                        result['平台状态'] = '买横机会'
                                        result['详情'].append("✅ 买横信号：接近平台下沿")
            
            self.logger.info(f"📊 平台突破分析: {result['平台状态']}, {result['详情']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 平台突破分析异常: {e}")
            return {'平台状态': '异常', '详情': [f"分析异常: {e}"]}
    
    def main_bull_wave_checklist(self, data: pd.DataFrame, industry_trend: bool = None) -> Dict[str, Any]:
        """
        强势主升浪选股指标对比表（8项）
        1. 长期横盘3个月以上
        2. 60日均线开始向上
        3. 股价突破平台
        4. 放量超过近20日平均成交量的2倍
        5. 回踩平台不破，MACD在零轴附近金叉
        6. RSI在50以上继续走强
        7. 主力资金连续流入
        8. 行业板块同步走强
        :param data: 含技术指标的日线数据
        :param industry_trend: 行业趋势（True/False/None）
        :return: 各项指标满足情况 + 满足数量
        """
        try:
            checklist = {
                '长期横盘3个月以上': False,
                '60日均线开始向上': False,
                '股价突破平台': False,
                '放量超20日均量2倍': False,
                '回踩不破+MACD零轴金叉': False,
                'RSI>50继续走强': False,
                '主力资金连续流入': False,
                '行业板块同步走强': False,
                '详情': [],
            }
            
            if data is None or data.empty:
                checklist['详情'].append("数据为空")
                checklist['满足数量'] = 0
                return checklist
            
            latest = data.iloc[-1]
            
            # 1. 长期横盘3个月以上（约60个交易日）：60日内振幅小于25%
            if len(data) >= 60:
                recent_60 = data.tail(60)
                high_60 = recent_60['最高价'].max()
                low_60 = recent_60['最低价'].min()
                avg_60 = recent_60['收盘价'].mean()
                if pd.notna(high_60) and pd.notna(low_60) and pd.notna(avg_60) and avg_60 > 0:
                    amplitude_60 = (high_60 - low_60) / avg_60 * 100
                    if amplitude_60 < 25:
                        checklist['长期横盘3个月以上'] = True
                        checklist['详情'].append(f"60日振幅{amplitude_60:.1f}%（<25%）")
                    else:
                        checklist['详情'].append(f"60日振幅{amplitude_60:.1f}%（>=25%，未横盘）")
            else:
                checklist['详情'].append("数据不足60日，无法判断横盘")
            
            # 2. 60日均线开始向上：MA60斜率 > 0
            if 'MA60' in data.columns and len(data) >= 65:
                ma60_series = data['MA60'].dropna()
                if len(ma60_series) >= 6:
                    ma60_slope = ma60_series.iloc[-1] - ma60_series.iloc[-6]
                    if ma60_slope > 0:
                        checklist['60日均线开始向上'] = True
                        checklist['详情'].append(f"MA60近5日上行{ma60_slope:.2f}")
                    else:
                        checklist['详情'].append(f"MA60近5日{ma60_slope:.2f}（未向上）")
            else:
                checklist['详情'].append("MA60数据不足")
            
            # 3. 股价突破平台：收盘价创近20日新高
            if len(data) >= 21:
                recent_20_high = data['最高价'].tail(20).max()
                if pd.notna(recent_20_high) and pd.notna(latest['收盘价']):
                    if latest['收盘价'] >= recent_20_high:
                        checklist['股价突破平台'] = True
                        checklist['详情'].append(f"收盘价{latest['收盘价']:.2f}突破近20日高点{recent_20_high:.2f}")
                    else:
                        checklist['详情'].append(f"未突破近20日高点{recent_20_high:.2f}")
            else:
                checklist['详情'].append("数据不足20日")
            
            # 4. 放量超过近20日平均成交量的2倍
            if '成交量' in data.columns and len(data) >= 21:
                avg_vol_20 = data['成交量'].tail(20).mean()
                if pd.notna(avg_vol_20) and avg_vol_20 > 0 and pd.notna(latest['成交量']):
                    vol_ratio_20 = latest['成交量'] / avg_vol_20
                    if vol_ratio_20 >= 2.0:
                        checklist['放量超20日均量2倍'] = True
                        checklist['详情'].append(f"当日量/20日均量={vol_ratio_20:.2f}（>=2倍）")
                    else:
                        checklist['详情'].append(f"当日量/20日均量={vol_ratio_20:.2f}（<2倍）")
            else:
                checklist['详情'].append("成交量数据不足")
            
            # 5. 回踩平台不破 + MACD在零轴附近金叉
            if len(data) >= 2:
                yesterday = data.iloc[-2]
                # 回踩不破：前一日低点未破近20日平台低点
                platform_low = data['最低价'].tail(20).min() if len(data) >= 20 else data['最低价'].min()
                pullback_ok = True
                if pd.notna(yesterday['最低价']) and pd.notna(platform_low):
                    pullback_ok = yesterday['最低价'] >= platform_low * 0.98  # 允许2%误差
                
                # MACD零轴附近金叉
                macd_golden = False
                if all(col in data.columns for col in ['MACD', 'MACD_Signal']):
                    macd_now = latest.get('MACD', 0)
                    signal_now = latest.get('MACD_Signal', 0)
                    macd_prev = yesterday.get('MACD', 0)
                    signal_prev = yesterday.get('MACD_Signal', 0)
                    # 金叉：MACD上穿信号线；零轴附近：|MACD| < 1.0（简化，按价格比例）
                    near_zero = abs(macd_now) < (latest['收盘价'] * 0.01) if pd.notna(latest['收盘价']) else False
                    golden_cross = (macd_now > signal_now) and (macd_prev <= signal_prev)
                    if golden_cross or (macd_now > signal_now and near_zero):
                        macd_golden = True
                
                if pullback_ok and macd_golden:
                    checklist['回踩不破+MACD零轴金叉'] = True
                    checklist['详情'].append("回踩平台未破，MACD零轴附近金叉")
                else:
                    checklist['详情'].append(
                        f"回踩{'未破' if pullback_ok else '破位'}/MACD{'金叉' if macd_golden else '未金叉'}")
            else:
                checklist['详情'].append("数据不足2日")
            
            # 6. RSI在50以上继续走强
            if 'RSI' in data.columns and len(data) >= 6:
                rsi_now = latest.get('RSI', 0)
                rsi_5ago = data['RSI'].iloc[-6] if len(data) >= 6 else rsi_now
                if pd.notna(rsi_now) and pd.notna(rsi_5ago):
                    if rsi_now > 50 and rsi_now >= rsi_5ago:
                        checklist['RSI>50继续走强'] = True
                        checklist['详情'].append(f"RSI={rsi_now:.1f}（>50且上行）")
                    else:
                        checklist['详情'].append(f"RSI={rsi_now:.1f}（{'<50' if rsi_now <= 50 else '走弱'}）")
            else:
                checklist['详情'].append("RSI数据不足")
            
            # 7. 主力资金连续流入：连续3日收盘上涨且放量（近似判断）
            if len(data) >= 4 and '成交量' in data.columns and '涨跌幅' in data.columns:
                recent_3 = data.tail(3)
                inflows = 0
                for i in range(len(recent_3)):
                    row = recent_3.iloc[i]
                    prev_vol = data['成交量'].iloc[-4] if len(data) >= 4 else row['成交量']
                    pct_chg = row.get('涨跌幅', 0)
                    if pd.notna(pct_chg) and pct_chg > 0:
                        inflows += 1
                if inflows >= 2:  # 3日中至少2日上涨，视为资金流入
                    checklist['主力资金连续流入'] = True
                    checklist['详情'].append(f"近3日{inflows}日上涨")
                else:
                    checklist['详情'].append(f"近3日仅{inflows}日上涨")
            else:
                checklist['详情'].append("涨跌幅数据不足")
            
            # 8. 行业板块同步走强
            if industry_trend is True:
                checklist['行业板块同步走强'] = True
                checklist['详情'].append("行业板块走强")
            elif industry_trend is False:
                checklist['详情'].append("行业板块走弱")
            else:
                checklist['详情'].append("行业趋势数据缺失")
            
            # 统计满足数量
            items = [k for k in checklist if k != '详情']
            satisfied = sum(1 for k in items if checklist[k])
            checklist['满足数量'] = satisfied
            checklist['满足占比'] = satisfied / len(items) if items else 0
            
            # 综合判断
            if satisfied >= 6:
                checklist['综合判断'] = '主升浪高概率'
            elif satisfied >= 4:
                checklist['综合判断'] = '主升浪中概率'
            elif satisfied >= 2:
                checklist['综合判断'] = '关注观察'
            else:
                checklist['综合判断'] = '暂不参与'
            
            self.logger.info(f"📋 主升浪指标对比: 满足{satisfied}/8项, {checklist['综合判断']}")
            return checklist
            
        except Exception as e:
            self.logger.error(f"❌ 主升浪指标对比异常: {e}")
            return {'满足数量': 0, '综合判断': '异常', '详情': [f"分析异常: {e}"]}
    
    def technical_detail_capture(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        技术细节捕捉
        :param data: 包含技术指标的数据
        :return: 技术细节分析结果
        """
        try:
            result = {
                '破五反五': False,
                '筹码集中度': '未知',
                '详情': []
            }
            
            # 检查必要的列
            required_cols = ['收盘价', 'MA5', '成交量', '换手率']
            missing_cols = [col for col in required_cols if col not in data.columns]
            
            if missing_cols:
                result['详情'].append(f"缺少必要列: {missing_cols}")
                return result
            
            # 1. 破五反五：监测股价跌破MA5后，次日迅速放量收回的洗盘信号
            if len(data) >= 2:
                yesterday = data.iloc[-2]
                today = data.iloc[-1]
                
                # 检查昨日是否跌破MA5
                if (pd.notna(yesterday['收盘价']) and pd.notna(yesterday['MA5']) and
                    yesterday['收盘价'] < yesterday['MA5']):
                    
                    # 检查今日是否收回MA5且放量
                    if (pd.notna(today['收盘价']) and pd.notna(today['MA5']) and
                        today['收盘价'] > today['MA5'] and
                        pd.notna(today['量比']) and today['量比'] > 1.5):
                        
                        result['破五反五'] = True
                        result['详情'].append("✅ 破五反五：洗盘信号确认")
            
            # 2. 筹码集中度：模拟计算筹码分布（或通过换手率估算），识别筹码由分散转向集中的"筹码归编"过程
            if '换手率' in data.columns:
                # 计算最近20天的平均换手率
                recent_20_days = data.tail(20)
                avg_turnover = recent_20_days['换手率'].mean()
                
                if pd.notna(avg_turnover):
                    # 简化的筹码集中度判断
                    if avg_turnover < 2:
                        result['筹码集中度'] = '高度集中'
                        result['详情'].append("筹码高度集中")
                    elif avg_turnover < 5:
                        result['筹码集中度'] = '相对集中'
                        result['详情'].append("筹码相对集中")
                    elif avg_turnover < 10:
                        result['筹码集中度'] = '分散'
                        result['详情'].append("筹码分散")
                    else:
                        result['筹码集中度'] = '高度分散'
                        result['详情'].append("筹码高度分散")
                
                # 检查筹码集中度变化趋势
                if len(recent_20_days) >= 10:
                    recent_10_turnover = recent_20_days.tail(10)['换手率'].mean()
                    early_10_turnover = recent_20_days.head(10)['换手率'].mean()
                    
                    if (pd.notna(recent_10_turnover) and pd.notna(early_10_turnover) and
                        recent_10_turnover < early_10_turnover):
                        result['详情'].append("筹码呈集中趋势")
            
            self.logger.info(f"🔍 技术细节分析: 破五反五={result['破五反五']}, 筹码集中度={result['筹码集中度']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 技术细节捕捉异常: {e}")
            return {'破五反五': False, '筹码集中度': '异常', '详情': [f"分析异常: {e}"]}
    
    def comprehensive_analysis(self, data: pd.DataFrame, market_data: pd.DataFrame = None) -> Dict[str, Any]:
        """
        综合分析
        :param data: 个股数据
        :param market_data: 市场指数数据
        :return: 综合分析结果
        """
        try:
            result = {
                '股票代码': data.iloc[-1]['代码'] if '代码' in data.columns else '未知',
                '基础过滤': False,
                '三振共振': False,
                '主升浪状态': '未知',
                '平台状态': '未知',
                '技术细节': {},
                '综合评分': 0,
                '建议操作': '观望',
                '止损位': None,
                '详情': []
            }
            
            # 1. 基础过滤
            basic_passed, basic_errors = self.basic_filter(data)
            result['基础过滤'] = basic_passed
            if basic_passed:
                result['详情'].append("✅ 基础过滤通过")
            else:
                result['详情'].extend([f"❌ {error}" for error in basic_errors])
                return result  # 基础过滤不通过，直接返回
            
            # 2. 三振共振分析
            # 兼容 market_data 为 DataFrame 或 Dict 两种形式
            if isinstance(market_data, dict):
                resonance_result = self.three_resonance_analysis(data, market_data)
            else:
                resonance_result = self.three_resonance_analysis(data)
            result['三振共振'] = resonance_result['三级共振']
            result['详情'].extend(resonance_result['详情'])
            
            # 3. 主升浪分析
            bull_wave_result = self.main_bull_wave_analysis(data)
            result['主升浪状态'] = bull_wave_result['主升浪状态']
            result['详情'].extend(bull_wave_result['详情'])
            
            # 4. 平台突破分析
            platform_result = self.platform_breakthrough_analysis(data)
            result['平台状态'] = platform_result['平台状态']
            result['详情'].extend(platform_result['详情'])
            
            # 5. 技术细节捕捉
            technical_result = self.technical_detail_capture(data)
            result['技术细节'] = technical_result
            result['详情'].extend(technical_result['详情'])
            
            # 6. 计算综合评分
            score = 0
            if result['基础过滤']:
                score += 20
            if result['三振共振']:
                score += 30
            if result['主升浪状态'] in ['主升持股期', '空中加油', '强势上升']:
                score += 25
            if result['平台状态'] in ['突破确认', '买横机会']:
                score += 15
            if technical_result['破五反五']:
                score += 10
            
            result['综合评分'] = min(score, 100)  # 最高100分
            
            # 7. 生成建议操作
            if result['综合评分'] >= 80:
                result['建议操作'] = '强烈买入'
            elif result['综合评分'] >= 60:
                result['建议操作'] = '买入'
            elif result['综合评分'] >= 40:
                result['建议操作'] = '关注'
            else:
                result['建议操作'] = '观望'
            
            # 8. 计算止损位
            if 'MA20' in data.columns:
                latest_ma20 = data.iloc[-1]['MA20']
                if pd.notna(latest_ma20):
                    result['止损位'] = latest_ma20 * 0.95  # 设在MA20的95%位置
            
            self.logger.info(f"🎯 综合分析完成: 评分={result['综合评分']}, 建议={result['建议操作']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 综合分析异常: {e}")
            return {'综合评分': 0, '建议操作': '异常', '详情': [f"分析异常: {e}"]}
