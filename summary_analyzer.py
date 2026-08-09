#!/usr/bin/env python3
# summary_analyzer.py - 汇总分析器
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from typing import Dict, List, Optional, Any
import os
import sys

sys_path = os.path.dirname(os.path.abspath(__file__))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
try:
    from utils import build_report_filename
except ImportError:
    from utils import build_report_filename

class SummaryAnalyzer:
    """汇总分析器"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
    
    def summarize_analysis_results(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        汇总分析结果
        :param analysis_results: 分析结果字典
        :return: 汇总结果
        """
        try:
            summary = {
                '生成时间': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                '分析股票总数': len(analysis_results),
                '通过基础过滤': 0,
                '三振共振成立': 0,
                '主升浪状态': 0,
                '平台突破': 0,
                '强烈买入': 0,
                '买入': 0,
                '关注': 0,
                '观望': 0,
                '平均评分': 0,
                '最高评分': 0,
                '最低评分': 100,
                '股票列表': [],
                '统计详情': {},
                '重点关注': [],
                '风险提示': []
            }
            
            scores = []
            strong_buy_stocks = []
            buy_stocks = []
            watch_stocks = []
            avoid_stocks = []
            
            for stock_code, result in analysis_results.items():
                if isinstance(result, dict) and '综合评分' in result:
                    # 基本统计
                    scores.append(result.get('综合评分', 0))
                    summary['股票列表'].append({
                        '股票代码': stock_code,
                        '股票名称': result.get('股票名称', '未知'),
                        '综合评分': result.get('综合评分', 0),
                        '建议操作': result.get('建议操作', '观望')
                    })
                    
                    # 分类统计
                    if result.get('基础过滤', False):
                        summary['通过基础过滤'] += 1
                    
                    if result.get('三振共振', False):
                        summary['三振共振成立'] += 1
                    
                    if result.get('主升浪状态') == '主升浪':
                        summary['主升浪状态'] += 1
                    
                    if result.get('突破信号', False):
                        summary['平台突破'] += 1
                    
                    # 操作建议统计
                    recommendation = result.get('建议操作', '观望')
                    if recommendation == '强烈买入':
                        summary['强烈买入'] += 1
                        strong_buy_stocks.append({
                            '股票代码': stock_code,
                            '股票名称': result.get('股票名称', '未知'),
                            '综合评分': result.get('综合评分', 0),
                            '止损位': result.get('止损位', '无')
                        })
                    elif recommendation == '买入':
                        summary['买入'] += 1
                        buy_stocks.append({
                            '股票代码': stock_code,
                            '股票名称': result.get('股票名称', '未知'),
                            '综合评分': result.get('综合评分', 0),
                            '止损位': result.get('止损位', '无')
                        })
                    elif recommendation == '关注':
                        summary['关注'] += 1
                        watch_stocks.append({
                            '股票代码': stock_code,
                            '股票名称': result.get('股票名称', '未知'),
                            '综合评分': result.get('综合评分', 0),
                            '止损位': result.get('止损位', '无')
                        })
                    else:
                        summary['观望'] += 1
                        avoid_stocks.append({
                            '股票代码': stock_code,
                            '股票名称': result.get('股票名称', '未知'),
                            '综合评分': result.get('综合评分', 0),
                            '止损位': result.get('止损位', '无')
                        })
            
            # 计算评分统计
            if scores:
                summary['平均评分'] = sum(scores) / len(scores)
                summary['最高评分'] = max(scores)
                summary['最低评分'] = min(scores)
            
            # 设置重点关注股票
            summary['重点关注'] = strong_buy_stocks + buy_stocks
            
            # 生成风险提示
            summary['风险提示'] = self._generate_risk_warnings(analysis_results)
            
            # 生成统计详情
            summary['统计详情'] = self._generate_statistics_details(analysis_results)
            
            self.logger.info(f"✅ 汇总分析完成: 分析{len(analysis_results)}只股票")
            return summary
            
        except Exception as e:
            self.logger.error(f"❌ 汇总分析异常: {e}")
            return {'错误': f"汇总分析异常: {e}"}
    
    def _generate_statistics_details(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """生成统计详情"""
        try:
            details = {
                '评分分布': {'80分以上': 0, '60-80分': 0, '40-60分': 0, '40分以下': 0},
                '行业分布': {},
                '市值分布': {'大盘': 0, '中盘': 0, '小盘': 0},
                '技术指标统计': {
                    '均线多头排列': 0,
                    'MACD金叉': 0,
                    'RSI超买': 0,
                    '成交量放大': 0
                }
            }
            
            for stock_code, result in analysis_results.items():
                if isinstance(result, dict) and '综合评分' in result:
                    # 评分分布
                    score = result.get('综合评分', 0) or 0
                    if score >= 80:
                        details['评分分布']['80分以上'] += 1
                    elif score >= 60:
                        details['评分分布']['60-80分'] += 1
                    elif score >= 40:
                        details['评分分布']['40-60分'] += 1
                    else:
                        details['评分分布']['40分以下'] += 1
                    
                    # 行业分布（模拟数据）
                    industry = result.get('行业', '未知')
                    if industry in details['行业分布']:
                        details['行业分布'][industry] += 1
                    else:
                        details['行业分布'][industry] = 1
                    
                    # 市值分布（模拟数据）
                    market_cap = result.get('市值类型', '未知')
                    if market_cap == '大盘':
                        details['市值分布']['大盘'] += 1
                    elif market_cap == '中盘':
                        details['市值分布']['中盘'] += 1
                    elif market_cap == '小盘':
                        details['市值分布']['小盘'] += 1
                    
                    # 技术指标统计
                    if result.get('均线排列') == '多头':
                        details['技术指标统计']['均线多头排列'] += 1
                    
                    if result.get('MACD_信号') == '金叉':
                        details['技术指标统计']['MACD金叉'] += 1
                    
                    if (result.get('RSI') or 0) > 70:
                        details['技术指标统计']['RSI超买'] += 1
                    
                    if (result.get('量比') or 0) > 1.5:
                        details['技术指标统计']['成交量放大'] += 1
            
            return details
            
        except Exception as e:
            self.logger.error(f"❌ 生成统计详情异常: {e}")
            return {'错误': f"生成统计详情异常: {e}"}
    
    def _generate_risk_warnings(self, analysis_results: Dict[str, Any]) -> List[str]:
        """生成风险提示"""
        try:
            warnings = []
            
            # 检查高风险股票
            high_risk_count = 0
            for stock_code, result in analysis_results.items():
                if isinstance(result, dict):
                    # 检查多个风险因素
                    risk_factors = 0
                    
                    if result.get('综合评分', 0) < 30:
                        risk_factors += 1
                    
                    if result.get('主升浪状态') == '下跌':
                        risk_factors += 1
                    
                    if result.get('平台状态') == '下跌':
                        risk_factors += 1
                    
                    if result.get('建议操作') == '观望' and risk_factors >= 2:
                        high_risk_count += 1
            
            if high_risk_count > 0:
                warnings.append(f"⚠️ 发现{high_risk_count}只高风险股票，建议谨慎操作")
            
            # 检查市场整体风险
            total_stocks = len(analysis_results)
            if total_stocks > 0:
                strong_buy_ratio = sum(1 for r in analysis_results.values() 
                                    if isinstance(r, dict) and r.get('建议操作') == '强烈买入') / total_stocks
                if strong_buy_ratio < 0.1:  # 强烈买入比例低于10%
                    warnings.append("📊 当前市场机会较少，建议降低仓位")
                
                avoid_ratio = sum(1 for r in analysis_results.values() 
                                if isinstance(r, dict) and r.get('建议操作') == '观望') / total_stocks
                if avoid_ratio > 0.7:  # 观望比例高于70%
                    warnings.append("📉 市场观望情绪浓厚，建议等待更好的入场时机")
            
            # 检查技术指标风险
            macd_divergence = 0
            for stock_code, result in analysis_results.items():
                if isinstance(result, dict):
                    if result.get('MACD', 0) < 0 and result.get('MACD_Signal', 0) > 0:
                        macd_divergence += 1
            
            if macd_divergence > total_stocks * 0.3:  # MACD背离超过30%
                warnings.append("📈 MACD指标出现较多背离信号，注意市场风险")
            
            # 如果没有风险提示，添加中性提示
            if not warnings:
                warnings.append("✅ 当前市场风险相对可控，建议按计划操作")
            
            return warnings
            
        except Exception as e:
            self.logger.error(f"❌ 生成风险提示异常: {e}")
            return [f"生成风险提示异常: {e}"]
    
    def generate_recommendations(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """生成投资建议"""
        try:
            recommendations = {
                '总体建议': '观望',
                '仓位建议': '正常',
                '操作策略': '稳健',
                '重点关注': [],
                '风险控制': [],
                '市场判断': '中性'
            }
            
            # 基于统计数据生成建议
            total_stocks = summary.get('分析股票总数', 0)
            if total_stocks > 0:
                strong_buy_ratio = summary.get('强烈买入', 0) / total_stocks
                buy_ratio = summary.get('买入', 0) / total_stocks
                watch_ratio = summary.get('关注', 0) / total_stocks
                avoid_ratio = summary.get('观望', 0) / total_stocks
                
                # 判断市场环境
                if strong_buy_ratio > 0.2:  # 强烈买入超过20%
                    recommendations['总体建议'] = '积极做多'
                    recommendations['仓位建议'] = '加仓'
                    recommendations['操作策略'] = '激进'
                    recommendations['市场判断'] = '强势'
                elif strong_buy_ratio + buy_ratio > 0.4:  # 买入机会较多
                    recommendations['总体建议'] = '适度做多'
                    recommendations['仓位建议'] = '正常'
                    recommendations['操作策略'] = '稳健'
                    recommendations['市场判断'] = '温和'
                elif avoid_ratio > 0.7:  # 观望超过70%
                    recommendations['总体建议'] = '谨慎观望'
                    recommendations['仓位建议'] = '减仓'
                    recommendations['操作策略'] = '保守'
                    recommendations['市场判断'] = '弱势'
                else:
                    recommendations['总体建议'] = '中性操作'
                    recommendations['仓位建议'] = '正常'
                    recommendations['操作策略'] = '平衡'
                    recommendations['市场判断'] = '震荡'
                
                # 生成重点关注股票
                recommendations['重点关注'] = summary.get('重点关注', [])[:5]  # 最多5只
                
                # 生成风险控制建议
                if summary.get('平均评分', 0) < 50:
                    recommendations['风险控制'].append('当前市场整体评分较低，建议降低仓位')
                
                if summary.get('三振共振成立', 0) < total_stocks * 0.3:  # 三振共振成立少于30%
                    recommendations['风险控制'].append('三振共振成立率较低，建议等待更好的时机')
                
                if summary.get('平台突破', 0) < total_stocks * 0.2:  # 平台突破少于20%
                    recommendations['风险控制'].append('平台突破信号较少，建议耐心等待')
            
            self.logger.info(f"✅ 投资建议生成完成: {recommendations['总体建议']}")
            return recommendations
            
        except Exception as e:
            self.logger.error(f"❌ 生成投资建议异常: {e}")
            return {'错误': f"生成投资建议异常: {e}"}
    
    def export_summary_report(self, summary: Dict[str, Any], recommendations: Dict[str, Any],
                              analysis_results: Dict[str, Any] = None) -> str:
        """
        导出汇总报告
        :param summary: 汇总结果
        :param recommendations: 投资建议
        :param analysis_results: 分析结果（可选，用于文件名命名）
        :return: 报告文件路径
        """
        try:
            # 创建汇总报告（文件名规则：单只含股票名称，多只加"每日"）
            if analysis_results is not None:
                filename = build_report_filename(analysis_results, "汇总分析报告", ".txt")
            else:
                # 无分析结果时根据股票总数判断
                total = summary.get('分析股票总数', 0)
                if total == 1:
                    filename = f"汇总分析报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                else:
                    filename = f"每日汇总分析报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("Mystery趋势交易分析系统 - 汇总报告\n")
                f.write("=" * 60 + "\n\n")
                
                # 基本信息
                f.write(f"📅 生成时间: {summary.get('生成时间', '未知')}\n")
                f.write(f"📊 分析股票总数: {summary.get('分析股票总数', 0)}只\n\n")
                
                # 统计概览
                f.write("📈 统计概览\n")
                f.write("-" * 30 + "\n")
                f.write(f"✅ 通过基础过滤: {summary.get('通过基础过滤', 0)}只\n")
                f.write(f"🎯 三振共振成立: {summary.get('三振共振成立', 0)}只\n")
                f.write(f"🚀 主升浪状态: {summary.get('主升浪状态', 0)}只\n")
                f.write(f"💪 平台突破: {summary.get('平台突破', 0)}只\n\n")
                
                # 评分统计
                f.write("📊 评分统计\n")
                f.write("-" * 30 + "\n")
                f.write(f"📈 平均评分: {summary.get('平均评分', 0):.1f}分\n")
                f.write(f"🏆 最高评分: {summary.get('最高评分', 0):.1f}分\n")
                f.write(f"📉 最低评分: {summary.get('最低评分', 0):.1f}分\n\n")
                
                # 操作建议分布
                f.write("🎯 操作建议分布\n")
                f.write("-" * 30 + "\n")
                f.write(f"🔥 强烈买入: {summary.get('强烈买入', 0)}只\n")
                f.write(f"💰 买入: {summary.get('买入', 0)}只\n")
                f.write(f"👀 关注: {summary.get('关注', 0)}只\n")
                f.write(f"⚠️ 观望: {summary.get('观望', 0)}只\n\n")
                
                # 投资建议
                f.write("💡 投资建议\n")
                f.write("-" * 30 + "\n")
                f.write(f"🎯 总体建议: {recommendations.get('总体建议', '未知')}\n")
                f.write(f"📊 仓位建议: {recommendations.get('仓位建议', '未知')}\n")
                f.write(f"🎮 操作策略: {recommendations.get('操作策略', '未知')}\n")
                f.write(f"📈 市场判断: {recommendations.get('市场判断', '未知')}\n\n")
                
                # 重点关注股票
                f.write("🌟 重点关注股票\n")
                f.write("-" * 30 + "\n")
                for stock in recommendations.get('重点关注', [])[:5]:
                    f.write(f"📈 {stock['股票代码']} {stock['股票名称']} - 评分: {stock['综合评分']:.1f} - 止损: {stock['止损位']}\n")
                f.write("\n")
                
                # 风险提示
                f.write("⚠️ 风险提示\n")
                f.write("-" * 30 + "\n")
                for warning in summary.get('风险提示', []):
                    f.write(f"🚨 {warning}\n")
                f.write("\n")
                
                # 统计详情
                f.write("📊 详细统计\n")
                f.write("-" * 30 + "\n")
                details = summary.get('统计详情', {})
                
                if '评分分布' in details:
                    f.write("评分分布:\n")
                    for level, count in details['评分分布'].items():
                        f.write(f"  {level}: {count}只\n")
                
                if '行业分布' in details:
                    f.write("\n行业分布:\n")
                    for industry, count in details['行业分布'].items():
                        f.write(f"  {industry}: {count}只\n")
                
                if '技术指标统计' in details:
                    f.write("\n技术指标统计:\n")
                    for indicator, count in details['技术指标统计'].items():
                        f.write(f"  {indicator}: {count}只\n")
                f.write("\n")
                
                f.write("=" * 60 + "\n")
                f.write("报告生成完成，请结合市场实际情况做出投资决策\n")
                f.write("投资有风险，入市需谨慎\n")
                f.write("=" * 60 + "\n")
            
            self.logger.info(f"✅ 汇总报告导出完成: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ 导出汇总报告异常: {e}")
            raise