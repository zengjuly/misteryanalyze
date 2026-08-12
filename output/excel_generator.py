#!/usr/bin/env python3
# excel_generator.py - Excel报告生成器
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from typing import Dict, List, Optional, Any
import os
import sys

sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
try:
    from utils import build_report_filename
except ImportError:
    from ..utils import build_report_filename

class ExcelGenerator:
    """Excel报告生成器"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_stock_analysis_report(self, analysis_results: Dict[str, Any], 
                                    stock_data: Dict[str, pd.DataFrame]) -> str:
        """
        生成股票分析报告Excel
        :param analysis_results: 分析结果字典
        :param stock_data: 股票数据字典
        :return: 生成的Excel文件路径
        """
        try:
            # 创建Excel写入器（文件名规则：单只含股票名称，多只加"每日"）
            filename = build_report_filename(analysis_results, "股票分析报告", ".xlsx")
            filepath = os.path.join(self.output_dir, filename)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # 1. 创建汇总工作表
                self._create_summary_sheet(writer, analysis_results)
                
                # 2. 创建个股详细分析工作表
                self._create_detail_sheets(writer, analysis_results, stock_data)
                
                # 3. 创建技术指标工作表
                self._create_indicators_sheet(writer, analysis_results, stock_data)
                
                # 4. 创建形态识别工作表
                self._create_patterns_sheet(writer, analysis_results)
                
                # 5. 创建历史数据工作表
                self._create_history_sheet(writer, stock_data)
            
            self.logger.info(f"✅ Excel报告生成完成: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ 生成Excel报告异常: {e}")
            raise
    
    def _create_summary_sheet(self, writer: pd.ExcelWriter, analysis_results: Dict[str, Any]):
        """创建汇总工作表"""
        try:
            summary_data = []
            
            for stock_code, result in analysis_results.items():
                if isinstance(result, dict) and '综合评分' in result:
                    row = {
                        '股票代码': stock_code,
                        '股票名称': result.get('股票名称', '未知'),
                        '所属板块': result.get('所属板块', '未知'),
                        '综合评分': result.get('综合评分', 0),
                        '基础过滤': '✅' if result.get('基础过滤', False) else '❌',
                        '个股趋势': '✅' if result.get('个股趋势', False) else '❌',
                        '行业趋势': '✅' if result.get('行业趋势', False) else '❌',
                        '大盘趋势': '✅' if result.get('大盘趋势', False) else '❌',
                        '三振共振': '✅' if result.get('三振共振', False) else '❌',
                        '主升浪状态': result.get('主升浪状态', '未知'),
                        '主升浪指标': f"{result.get('主升浪满足数量', 0)}/8",
                        '主升浪判断': result.get('主升浪综合判断', '未知'),
                        '周线趋势': result.get('周线趋势', '未知'),
                        '月线趋势': result.get('月线趋势', '未知'),
                        '多周期共振': '✅' if result.get('多周期共振', False) else '❌',
                        '平台状态': result.get('平台状态', '未知'),
                        '建议操作': result.get('建议操作', '观望'),
                        '止损位': result.get('止损位', '无'),
                        '最新价': result.get('最新价', 0),
                        'PE': result.get('PE'),
                        'PB': result.get('PB'),
                        'ROE': result.get('ROE'),
                        '股息率': result.get('股息率'),
                        '更新时间': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    summary_data.append(row)
            
            # 按综合评分排序（空数据时跳过）
            summary_df = pd.DataFrame(summary_data)
            if not summary_df.empty and '综合评分' in summary_df.columns:
                summary_df = summary_df.sort_values('综合评分', ascending=False)
            
            # 写入Excel
            summary_df.to_excel(writer, sheet_name='汇总报告', index=False)
            
            # 设置列宽
            worksheet = writer.sheets['汇总报告']
            for i, column in enumerate(summary_df.columns, 1):
                column_length = max(len(str(column)), 12)
                worksheet.column_dimensions[chr(64 + i)].width = column_length
            
            self.logger.info("✅ 汇总工作表创建完成")
            
        except Exception as e:
            self.logger.error(f"❌ 创建汇总工作表异常: {e}")
    
    def _create_detail_sheets(self, writer: pd.ExcelWriter, analysis_results: Dict[str, Any], 
                             stock_data: Dict[str, pd.DataFrame]):
        """创建个股详细分析工作表"""
        try:
            for stock_code, result in analysis_results.items():
                if isinstance(result, dict) and '综合评分' in result:
                    sheet_name = f"个股_{stock_code}"
                    
                    # 创建详细分析数据
                    detail_data = []
                    
                    # 基础信息
                    detail_data.append(['基础信息', '', ''])
                    detail_data.append(['股票代码', stock_code, ''])
                    detail_data.append(['股票名称', result.get('股票名称', '未知'), ''])
                    detail_data.append(['所属板块', result.get('所属板块', '未知'), ''])
                    detail_data.append(['综合评分', result.get('综合评分', 0), ''])
                    detail_data.append(['建议操作', result.get('建议操作', '观望'), ''])
                    detail_data.append(['止损位', result.get('止损位', '无'), ''])
                    detail_data.append(['', '', ''])
                    
                    # 技术指标（最新交易日）
                    detail_data.append(['技术指标（最新交易日）', '', ''])
                    detail_data.append(['最新价', result.get('最新价', 0), ''])
                    detail_data.append(['MA5', result.get('MA5', 0), ''])
                    detail_data.append(['MA10', result.get('MA10', 0), ''])
                    detail_data.append(['MA20', result.get('MA20', 0), ''])
                    detail_data.append(['MA60', result.get('MA60', 0), ''])
                    detail_data.append(['MA250', result.get('MA250', 0), ''])
                    detail_data.append(['均线排列', result.get('均线排列', 0), ''])
                    detail_data.append(['量比', result.get('量比', 0), ''])
                    detail_data.append(['RSI', result.get('RSI', 0), ''])
                    detail_data.append(['MACD', result.get('MACD', 0), ''])
                    detail_data.append(['MACD_Signal', result.get('MACD_Signal', 0), ''])
                    detail_data.append(['MACD_信号', result.get('MACD_信号', 0), ''])
                    detail_data.append(['动能状态', result.get('动能状态', '未知'), ''])
                    detail_data.append(['量价配合度', result.get('量价配合度', 0), ''])
                    detail_data.append(['换手率', result.get('换手率', 0), ''])
                    detail_data.append(['成交量', result.get('成交量', 0), ''])
                    detail_data.append(['', '', ''])
                    
                    # 财务指标
                    detail_data.append(['财务指标', '', ''])
                    detail_data.append(['ROE', result.get('ROE'), ''])
                    detail_data.append(['EPS', result.get('EPS'), ''])
                    detail_data.append(['PE', result.get('PE'), ''])
                    detail_data.append(['PB', result.get('PB'), ''])
                    detail_data.append(['股息率', result.get('股息率'), ''])
                    detail_data.append(['每股股息', result.get('每股股息'), ''])
                    detail_data.append(['报告期', result.get('财务报告期', ''), ''])
                    detail_data.append(['', '', ''])
                    
                    # 基础过滤结果
                    detail_data.append(['基础过滤', '', ''])
                    detail_data.append(['是否通过', '✅' if result.get('基础过滤', False) else '❌', ''])
                    if not result.get('基础过滤', False):
                        # 排除原因逐条列出
                        reasons = result.get('基础过滤排除原因') or result.get('基础过滤详情') or []
                        for i, reason in enumerate(reasons, 1):
                            detail_data.append([f'排除原因{i}', reason, ''])
                    detail_data.append(['', '', ''])
                    
                    # 三振共振分析
                    detail_data.append(['三振共振分析', '', ''])
                    detail_data.append(['三级共振', '✅' if result.get('三振共振', False) else '❌', ''])
                    detail_data.append(['个股趋势', '✅' if result.get('个股趋势', False) else '❌', ''])
                    detail_data.append(['行业趋势', '✅' if result.get('行业趋势', False) else '❌', ''])
                    detail_data.append(['板块评级', result.get('板块评级', '数据不足'), ''])
                    detail_data.append(['板块近5日涨跌', result.get('板块近5日'), '%'])
                    detail_data.append(['板块近10日涨跌', result.get('板块近10日'), '%'])
                    detail_data.append(['板块近20日涨跌', result.get('板块近20日'), '%'])
                    detail_data.append(['板块样本股票', ', '.join(map(str, result.get('板块样本', [])[:3])) if result.get('板块样本') else '', ''])
                    detail_data.append(['大盘趋势', '✅' if result.get('大盘趋势', False) else '❌', ''])
                    detail_data.append(['', '', ''])
                    
                    # 多周期分析
                    detail_data.append(['多周期分析', '', ''])
                    detail_data.append(['周线趋势', result.get('周线趋势', '未知'), ''])
                    detail_data.append(['周线最新价', result.get('周线最新价'), ''])
                    detail_data.append(['周线MA20', result.get('周线MA20'), ''])
                    detail_data.append(['月线趋势', result.get('月线趋势', '未知'), ''])
                    detail_data.append(['月线最新价', result.get('月线最新价'), ''])
                    detail_data.append(['月线MA10', result.get('月线MA10'), ''])
                    detail_data.append(['多周期共振', '✅' if result.get('多周期共振', False) else '❌', ''])
                    detail_data.append(['', '', ''])
                    
                    # 主升浪分析
                    detail_data.append(['主升浪分析', '', ''])
                    detail_data.append(['主升浪状态', result.get('主升浪状态', '未知'), ''])
                    for i, basis in enumerate((result.get('主升浪判定依据') or [])[:5], 1):
                        detail_data.append([f'判定依据{i}', basis, ''])
                    detail_data.append(['主升浪指标满足', f"{result.get('主升浪满足数量', 0)}/8", ''])
                    detail_data.append(['主升浪综合判断', result.get('主升浪综合判断', '未知'), ''])
                    if '主升浪' in result and isinstance(result['主升浪'], dict):
                        bull_wave = result['主升浪']
                        detail_data.append(['持股状态', '✅' if bull_wave.get('持股状态', False) else '❌', ''])
                        detail_data.append(['空中加油', '✅' if bull_wave.get('空中加油', False) else '❌', ''])
                        detail_data.append(['MA5斜率', bull_wave.get('MA5斜率', 0), ''])
                    detail_data.append(['', '', ''])
                    
                    # 主升浪8项指标对比表
                    detail_data.append(['主升浪8项指标对比', '', ''])
                    checklist = result.get('主升浪指标对比', {})
                    for key in ['长期横盘3个月以上', '60日均线开始向上', '股价突破平台',
                                '放量超20日均量2倍', '回踩不破+MACD零轴金叉', 'RSI>50继续走强',
                                '主力资金连续流入', '行业板块同步走强']:
                        mark = '✅' if checklist.get(key, False) else '❌'
                        detail_data.append([key, mark, ''])
                    detail_data.append(['', '', ''])
                    
                    # 平台突破分析
                    detail_data.append(['平台突破分析', '', ''])
                    detail_data.append(['平台状态', result.get('平台状态', '未知'), ''])
                    pr = result.get('平台范围')
                    if pr:
                        detail_data.append(['平台箱体(近20日)', 
                                           f"下沿 {pr.get('下沿', '-')} ~ 上沿 {pr.get('上沿', '-')}", ''])
                    ap = result.get('自适应平台')
                    if ap and ap.get('POC') is not None:
                        detail_data.append(['自适应平台方式', '自适应VAP-ATR', ''])
                        detail_data.append(['POC(筹码控制点)', ap.get('POC'), ''])
                        detail_data.append(['自适应上轨', ap.get('自适应上轨'), ''])
                        detail_data.append(['自适应下轨', ap.get('自适应下轨'), ''])
                        detail_data.append(['ATR', ap.get('ATR'), ''])
                        ap_cycle = ap.get('自适应周期')
                        if ap_cycle:
                            detail_data.append(['自适应周期N', f"{ap_cycle.get('adaptive_n')}日 "
                                                             f"(近20日均换手{ap_cycle.get('avg_turnover')}%, "
                                                             f"理论N={ap_cycle.get('theoretical_n')})", ''])
                            detail_data.append(['快窗口ATR', f"{ap_cycle.get('atr_m')}日", ''])
                            detail_data.append(['波动率乘数k', ap_cycle.get('k'), ''])
                    detail_data.append(['突破信号', '✅' if result.get('突破信号', False) else '❌', ''])
                    detail_data.append(['买横信号', '✅' if result.get('买横信号', False) else '❌', ''])
                    detail_data.append(['', '', ''])
                    
                    # 多周期箱体（周线/月线）
                    for box_key, box_name in [('周线箱体', '周线箱体'), ('月线箱体', '月线箱体')]:
                        box = result.get(box_key)
                        if box and box.get('上沿') is not None:
                            detail_data.append([box_name, '', ''])
                            detail_data.append([f'{box_name}上沿', box.get('上沿'), ''])
                            detail_data.append([f'{box_name}下沿', box.get('下沿'), ''])
                            detail_data.append([f'{box_name}当前价', box.get('当前价'), ''])
                            detail_data.append([f'{box_name}状态', box.get('状态'), ''])
                            detail_data.append([f'{box_name}距上沿', f"{box.get('距上沿')}%", ''])
                            detail_data.append([f'{box_name}距下沿', f"{box.get('距下沿')}%", ''])
                    if result.get('多周期箱体状态'):
                        detail_data.append(['多周期箱体状态', result.get('多周期箱体状态'), ''])
                    detail_data.append(['', '', ''])
                    
                    # 技术细节
                    detail_data.append(['技术细节', '', ''])
                    detail_data.append(['破五反五', '✅' if result.get('破五反五', False) else '❌', ''])
                    chip_val = result.get('筹码集中度数值')
                    chip_str = f"（近20日均换手率 {chip_val}%）" if chip_val is not None else ""
                    detail_data.append(['筹码集中度', f"{result.get('筹码集中度', '未知')}{chip_str}", ''])
                    detail_data.append(['筹码趋势', result.get('筹码趋势', '未知'), ''])
                    detail_data.append(['', '', ''])
                    
                    # 转换为DataFrame
                    detail_df = pd.DataFrame(detail_data, columns=['项目', '结果', '备注'])
                    
                    # 写入Excel
                    detail_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    # 设置列宽
                    worksheet = writer.sheets[sheet_name]
                    worksheet.column_dimensions['A'].width = 20
                    worksheet.column_dimensions['B'].width = 15
                    worksheet.column_dimensions['C'].width = 30
            
            self.logger.info("✅ 个股详细分析工作表创建完成")
            
        except Exception as e:
            self.logger.error(f"❌ 创建个股详细分析工作表异常: {e}")
    
    def _create_indicators_sheet(self, writer: pd.ExcelWriter, analysis_results: Dict[str, Any], 
                                stock_data: Dict[str, pd.DataFrame]):
        """创建技术指标工作表"""
        try:
            indicators_data = []
            
            for stock_code, result in analysis_results.items():
                if isinstance(result, dict) and '综合评分' in result:
                    # 优先从analysis_results读取已计算的技术指标（保证数据正确）
                    # 若缺失则回退到stock_data中的最新行
                    latest = None
                    if stock_code in stock_data:
                        daily_data = stock_data[stock_code].get('daily')
                        if daily_data is not None and not daily_data.empty:
                            latest = daily_data.iloc[-1]
                    
                    def _val(key, fallback_key=None):
                        """从result取指标值，缺失时从latest取"""
                        if key in result and result[key] not in (None, ''):
                            return result[key]
                        if latest is not None:
                            return latest.get(fallback_key or key, 0)
                        return 0
                    
                    # 提取关键技术指标
                    row = {
                        '股票代码': stock_code,
                        '股票名称': result.get('股票名称', '未知'),
                        '所属板块': result.get('所属板块', '未知'),
                        '最新价': _val('最新价', '收盘价'),
                        '成交量': _val('成交量'),
                        '成交额': latest.get('成交额', 0) if latest is not None else 0,
                        '换手率': _val('换手率'),
                        'MA5': _val('MA5'),
                        'MA10': _val('MA10'),
                        'MA20': _val('MA20'),
                        'MA60': _val('MA60'),
                        'MA250': _val('MA250'),
                        '均线排列': _val('均线排列'),
                        '量比': _val('量比'),
                        'RSI': _val('RSI'),
                        'MACD': _val('MACD'),
                        'MACD_Signal': _val('MACD_Signal'),
                        'MACD_信号': _val('MACD_信号'),
                        '动能状态': _val('动能状态'),
                        '量价配合度': _val('量价配合度'),
                        'PE': result.get('PE'),
                        'PB': result.get('PB'),
                        'ROE': result.get('ROE'),
                        '股息率': result.get('股息率')
                    }
                    indicators_data.append(row)
            
            # 转换为DataFrame
            indicators_df = pd.DataFrame(indicators_data)
            
            # 写入Excel
            indicators_df.to_excel(writer, sheet_name='技术指标', index=False)
            
            # 设置列宽
            worksheet = writer.sheets['技术指标']
            for i, column in enumerate(indicators_df.columns, 1):
                column_length = max(len(str(column)), 12)
                worksheet.column_dimensions[chr(64 + i)].width = column_length
            
            self.logger.info("✅ 技术指标工作表创建完成")
            
        except Exception as e:
            self.logger.error(f"❌ 创建技术指标工作表异常: {e}")
    
    def _create_patterns_sheet(self, writer: pd.ExcelWriter, analysis_results: Dict[str, Any]):
        """创建形态识别工作表"""
        try:
            patterns_data = []
            
            for stock_code, result in analysis_results.items():
                if isinstance(result, dict) and '综合评分' in result:
                    # 提取形态识别结果
                    patterns_row = {
                        '股票代码': stock_code,
                        '股票名称': result.get('股票名称', '未知'),
                        '主要形态': result.get('主要形态', '无'),
                        '形态置信度': result.get('形态置信度', 0),
                        '头肩形态': result.get('头肩形态', {}).get('形态类型', '无'),
                        '双重形态': result.get('双重形态', {}).get('形态类型', '无'),
                        '三角形形态': result.get('三角形形态', {}).get('形态类型', '无'),
                        '楔形形态': result.get('楔形形态', {}).get('形态类型', '无')
                    }
                    patterns_data.append(patterns_row)
            
            # 转换为DataFrame
            patterns_df = pd.DataFrame(patterns_data)
            
            # 写入Excel
            patterns_df.to_excel(writer, sheet_name='形态识别', index=False)
            
            # 设置列宽
            worksheet = writer.sheets['形态识别']
            for i, column in enumerate(patterns_df.columns, 1):
                column_length = max(len(str(column)), 12)
                worksheet.column_dimensions[chr(64 + i)].width = column_length
            
            self.logger.info("✅ 形态识别工作表创建完成")
            
        except Exception as e:
            self.logger.error(f"❌ 创建形态识别工作表异常: {e}")
    
    def _create_history_sheet(self, writer: pd.ExcelWriter, stock_data: Dict[str, pd.DataFrame]):
        """创建历史数据工作表"""
        try:
            history_data = []
            
            for stock_code, data_dict in stock_data.items():
                if 'daily' in data_dict and not data_dict['daily'].empty:
                    daily_data = data_dict['daily']
                    
                    # 只取最近30天的数据
                    recent_data = daily_data.tail(30)
                    
                    for _, row in recent_data.iterrows():
                        history_row = {
                            '股票代码': stock_code,
                            '日期': row.get('date', ''),
                            '开盘价': row.get('开盘价', 0),
                            '最高价': row.get('最高价', 0),
                            '最低价': row.get('最低价', 0),
                            '收盘价': row.get('收盘价', 0),
                            '成交量': row.get('成交量', 0),
                            '成交额': row.get('成交额', 0),
                            '换手率': row.get('换手率', 0),
                            '涨跌幅': row.get('涨跌幅', 0),
                            'MA5': row.get('MA5', 0),
                            'MA10': row.get('MA10', 0),
                            'MA20': row.get('MA20', 0),
                            'MA60': row.get('MA60', 0)
                        }
                        history_data.append(history_row)
            
            # 转换为DataFrame
            history_df = pd.DataFrame(history_data)
            
            # 写入Excel
            history_df.to_excel(writer, sheet_name='历史数据', index=False)
            
            # 设置列宽
            worksheet = writer.sheets['历史数据']
            for i, column in enumerate(history_df.columns, 1):
                column_length = max(len(str(column)), 12)
                worksheet.column_dimensions[chr(64 + i)].width = column_length
            
            self.logger.info("✅ 历史数据工作表创建完成")
            
        except Exception as e:
            self.logger.error(f"❌ 创建历史数据工作表异常: {e}")
    
    def generate_daily_summary(self, analysis_results: Dict[str, Any]) -> str:
        """
        生成每日汇总报告
        :param analysis_results: 分析结果字典
        :return: 生成的Excel文件路径
        """
        try:
            # 创建Excel写入器（每日汇总：单只含名称，多只加"每日"）
            filename = build_report_filename(analysis_results, "汇总报告", ".xlsx")
            filepath = os.path.join(self.output_dir, filename)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # 创建每日汇总数据
                daily_data = []
                
                strong_buy = []
                buy = []
                watch = []
                avoid = []
                
                for stock_code, result in analysis_results.items():
                    if isinstance(result, dict) and '综合评分' in result:
                        row = {
                            '股票代码': stock_code,
                            '股票名称': result.get('股票名称', '未知'),
                            '综合评分': result.get('综合评分', 0),
                            '基础过滤': '✅' if result.get('基础过滤', False) else '❌',
                            '三振共振': '✅' if result.get('三振共振', False) else '❌',
                            '主升浪状态': result.get('主升浪状态', '未知'),
                            '平台状态': result.get('平台状态', '未知'),
                            '建议操作': result.get('建议操作', '观望'),
                            '止损位': result.get('止损位', '无'),
                            '更新时间': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        daily_data.append(row)
                        
                        # 按建议操作分类
                        if result.get('建议操作') == '强烈买入':
                            strong_buy.append(row)
                        elif result.get('建议操作') == '买入':
                            buy.append(row)
                        elif result.get('建议操作') == '关注':
                            watch.append(row)
                        else:
                            avoid.append(row)
                
                # 创建汇总工作表
                daily_df = pd.DataFrame(daily_data)
                daily_df = daily_df.sort_values('综合评分', ascending=False)
                daily_df.to_excel(writer, sheet_name='汇总', index=False)
                
                # 创建分类工作表
                if strong_buy:
                    strong_buy_df = pd.DataFrame(strong_buy)
                    strong_buy_df.to_excel(writer, sheet_name='强烈买入', index=False)
                
                if buy:
                    buy_df = pd.DataFrame(buy)
                    buy_df.to_excel(writer, sheet_name='买入', index=False)
                
                if watch:
                    watch_df = pd.DataFrame(watch)
                    watch_df.to_excel(writer, sheet_name='关注', index=False)
                
                if avoid:
                    avoid_df = pd.DataFrame(avoid)
                    avoid_df.to_excel(writer, sheet_name='观望', index=False)
                
                # 设置列宽
                for sheet_name in writer.sheetnames:
                    worksheet = writer.sheets[sheet_name]
                    for i, column in enumerate(daily_df.columns, 1):
                        column_length = max(len(str(column)), 12)
                        worksheet.column_dimensions[chr(64 + i)].width = column_length
            
            self.logger.info(f"✅ 每日汇总报告生成完成: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ 生成每日汇总报告异常: {e}")
            raise