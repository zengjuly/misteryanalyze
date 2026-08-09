#!/usr/bin/env python3
# resonance_analyzer.py - 三振共振分析器
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple

class ResonanceAnalyzer:
    """三振共振分析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_market_trend(self, index_data: pd.DataFrame) -> Dict[str, Any]:
        """
        分析市场趋势
        :param index_data: 指数数据
        :return: 市场趋势分析结果
        """
        try:
            result = {
                '趋势方向': '未知',
                '强度': 0,
                'MA20状态': '未知',
                'MA60状态': '未知',
                '详情': []
            }
            
            if index_data.empty or len(index_data) < 60:
                result['详情'].append("数据不足，无法分析市场趋势")
                return result
            
            # 获取最新数据
            latest = index_data.iloc[-1]
            
            # 计算均线
            if 'MA20' not in index_data.columns:
                index_data['MA20'] = index_data['收盘价'].rolling(window=20).mean()
            if 'MA60' not in index_data.columns:
                index_data['MA60'] = index_data['收盘价'].rolling(window=60).mean()
            
            latest = index_data.iloc[-1]  # 重新获取最新数据
            
            # 判断MA20状态
            if pd.notna(latest['MA20']) and pd.notna(latest['收盘价']):
                if latest['收盘价'] > latest['MA20']:
                    result['MA20状态'] = '上方'
                    result['详情'].append("价格运行在20日均线上方")
                else:
                    result['MA20状态'] = '下方'
                    result['详情'].append("价格运行在20日均线下方")
            
            # 判断MA60状态
            if pd.notna(latest['MA60']) and pd.notna(latest['收盘价']):
                if latest['收盘价'] > latest['MA60']:
                    result['MA60状态'] = '上方'
                    result['详情'].append("价格运行在60日均线上方")
                else:
                    result['MA60状态'] = '下方'
                    result['详情'].append("价格运行在60日均线下方")
            
            # 判断趋势方向
            if result['MA20状态'] == '上方' and result['MA60状态'] == '上方':
                result['趋势方向'] = '向上'
                result['详情'].append("市场趋势向上")
                
                # 计算趋势强度
                recent_20 = index_data.tail(20)
                if len(recent_20) >= 10:
                    price_change = (recent_20['收盘价'].iloc[-1] - recent_20['收盘价'].iloc[0]) / recent_20['收盘价'].iloc[0] * 100
                    result['强度'] = min(abs(price_change), 100)  # 最高100分
                    result['详情'].append(f"趋势强度: {result['强度']:.1f}")
            
            elif result['MA20状态'] == '下方' and result['MA60状态'] == '下方':
                result['趋势方向'] = '向下'
                result['详情'].append("市场趋势向下")
            else:
                result['趋势方向'] = '震荡'
                result['详情'].append("市场趋势震荡")
            
            self.logger.info(f"📊 市场趋势分析: {result['趋势方向']}, 强度={result['强度']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 分析市场趋势异常: {e}")
            return {'趋势方向': '异常', '详情': [f"分析异常: {e}"]}
    
    def analyze_industry_trend(self, industry_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        分析行业趋势
        :param industry_data: 行业数据字典
        :return: 行业趋势分析结果
        """
        try:
            result = {
                '强势行业': [],
                '弱势行业': [],
                '中性行业': [],
                '整体趋势': '未知',
                '详情': []
            }
            
            if not industry_data:
                result['详情'].append("无行业数据")
                return result
            
            for industry_name, industry_df in industry_data.items():
                if industry_df.empty or len(industry_df) < 20:
                    continue
                
                # 计算行业均线
                if 'MA20' not in industry_df.columns:
                    industry_df['MA20'] = industry_df['收盘价'].rolling(window=20).mean()
                
                latest = industry_df.iloc[-1]
                
                if pd.notna(latest['MA20']) and pd.notna(latest['收盘价']):
                    if latest['收盘价'] > latest['MA20'] * 1.05:  # 超出5%
                        result['强势行业'].append(industry_name)
                    elif latest['收盘价'] < latest['MA20'] * 0.95:  # 低于5%
                        result['弱势行业'].append(industry_name)
                    else:
                        result['中性行业'].append(industry_name)
            
            # 判断整体趋势
            if len(result['强势行业']) > len(result['弱势行业']):
                result['整体趋势'] = '向上'
                result['详情'].append(f"强势行业占优: {len(result['强势行业'])}个")
            elif len(result['弱势行业']) > len(result['强势行业']):
                result['整体趋势'] = '向下'
                result['详情'].append(f"弱势行业占优: {len(result['弱势行业'])}个")
            else:
                result['整体趋势'] = '震荡'
                result['详情'].append("行业强弱相当")
            
            self.logger.info(f"🏢 行业趋势分析: {result['整体趋势']}, 强势={len(result['强势行业'])}, 弱势={len(result['弱势行业'])}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 分析行业趋势异常: {e}")
            return {'整体趋势': '异常', '详情': [f"分析异常: {e}"]}
    
    def calculate_resonance_score(self, individual_result: Dict, market_result: Dict, 
                                 industry_result: Dict) -> Dict[str, Any]:
        """
        计算三振共振评分
        :param individual_result: 个股分析结果
        :param market_result: 市场分析结果
        :param industry_result: 行业分析结果
        :return: 共振评分结果
        """
        try:
            result = {
                '个股共振': 0,
                '市场共振': 0,
                '行业共振': 0,
                '总共振评分': 0,
                '共振级别': '无共振',
                '详情': []
            }
            
            # 个股共振评分
            if individual_result.get('基础过滤', False):
                result['个股共振'] = 40
                result['详情'].append("个股基础条件满足")
            else:
                result['详情'].append("个股基础条件不满足")
            
            # 市场共振评分
            if market_result.get('趋势方向') == '向上':
                result['市场共振'] = 30
                result['详情'].append("市场趋势向上")
            else:
                result['详情'].append("市场趋势不向上")
            
            # 行业共振评分
            if industry_result.get('整体趋势') == '向上':
                result['行业共振'] = 30
                result['详情'].append("行业趋势向上")
            else:
                result['详情'].append("行业趋势不向上")
            
            # 计算总共振评分
            result['总共振评分'] = result['个股共振'] + result['市场共振'] + result['行业共振']
            
            # 判断共振级别
            if result['总共振评分'] >= 90:
                result['共振级别'] = '三级共振'
                result['详情'].append("✅ 三级共振成立")
            elif result['总共振评分'] >= 60:
                result['共振级别'] = '二级共振'
                result['详情'].append("✅ 二级共振成立")
            elif result['总共振评分'] >= 30:
                result['共振级别'] = '一级共振'
                result['详情'].append("✅ 一级共振成立")
            else:
                result['共振级别'] = '无共振'
                result['详情'].append("❌ 无共振")
            
            self.logger.info(f"🎯 三振共振评分: {result['总共振评分']}, 级别={result['共振级别']}")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ 计算共振评分异常: {e}")
            return {'总共振评分': 0, '共振级别': '异常', '详情': [f"分析异常: {e}"]}
    
    def generate_resonance_report(self, stock_code: str, individual_result: Dict, 
                                 market_result: Dict, industry_result: Dict, 
                                 resonance_score: Dict) -> Dict[str, Any]:
        """
        生成共振分析报告
        :param stock_code: 股票代码
        :param individual_result: 个股分析结果
        :param market_result: 市场分析结果
        :param industry_result: 行业分析结果
        :param resonance_score: 共振评分结果
        :return: 共振分析报告
        """
        try:
            report = {
                '股票代码': stock_code,
                '分析时间': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                '个股状态': self._format_individual_status(individual_result),
                '市场状态': self._format_market_status(market_result),
                '行业状态': self._format_industry_status(industry_result),
                '共振分析': resonance_score,
                '投资建议': self._generate_investment_advice(resonance_score),
                '风险提示': self._generate_risk_warning(individual_result, market_result, industry_result)
            }
            
            self.logger.info(f"📋 生成共振分析报告: {stock_code}")
            return report
            
        except Exception as e:
            self.logger.error(f"❌ 生成共振报告异常: {e}")
            return {'股票代码': stock_code, '错误': f"生成报告异常: {e}"}
    
    def _format_individual_status(self, individual_result: Dict) -> str:
        """格式化个股状态"""
        if individual_result.get('基础过滤', False):
            return "✅ 基础条件满足"
        else:
            return "❌ 基础条件不满足"
    
    def _format_market_status(self, market_result: Dict) -> str:
        """格式化市场状态"""
        trend = market_result.get('趋势方向', '未知')
        strength = market_result.get('强度', 0)
        return f"📊 {trend} (强度: {strength:.1f})"
    
    def _format_industry_status(self, industry_result: Dict) -> str:
        """格式化行业状态"""
        trend = industry_result.get('整体趋势', '未知')
        strong_count = len(industry_result.get('强势行业', []))
        weak_count = len(industry_result.get('弱势行业', []))
        return f"🏢 {trend} (强势: {strong_count}, 弱势: {weak_count})"
    
    def _generate_investment_advice(self, resonance_score: Dict) -> str:
        """生成投资建议"""
        score = resonance_score.get('总共振评分', 0)
        level = resonance_score.get('共振级别', '无共振')
        
        if level == '三级共振':
            return "强烈建议买入，把握共振机会"
        elif level == '二级共振':
            return "建议买入，关注共振机会"
        elif level == '一级共振':
            return "可以关注，等待更好的共振机会"
        else:
            return "建议观望，等待共振机会"
    
    def _generate_risk_warning(self, individual_result: Dict, market_result: Dict, 
                              industry_result: Dict) -> List[str]:
        """生成风险提示"""
        warnings = []
        
        # 个股风险
        if not individual_result.get('基础过滤', False):
            warnings.append("个股基础条件不满足，存在风险")
        
        # 市场风险
        if market_result.get('趋势方向') == '向下':
            warnings.append("市场趋势向下，系统性风险较高")
        
        # 行业风险
        if industry_result.get('整体趋势') == '向下':
            warnings.append("行业趋势向下，行业风险较高")
        
        if not warnings:
            warnings.append("暂无明显风险提示")
        
        return warnings