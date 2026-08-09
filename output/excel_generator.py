#!/usr/bin/env python3
# excel_generator.py - Excel报告生成器
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from typing import Dict, List, Optional, Any
import os

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
            # 创建Excel写入器
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"股票分析报告_{timestamp}.xlsx"
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
                        '综合评分': result.get('综合评分', 0),
                        '基础过滤': '✅' if result.get('基础过滤', False) else '❌',
                        '三振共振': '✅' if result.get('三振共振', False) else '❌',
                        '主升浪状态': result.get('主升浪状态', '未知'),
                        '平台状态': result.get('平台状态', '未知'),
                        '建议操作': result.get('建议操作', '观望'),
                        '止损位': result.get('止损位', '无'),
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
                    detail_data.append(['综合评分', result.get('综合评分', 0), ''])
                    detail_data.append(['建议操作', result.get('建议操作', '观望'), ''])
                    detail_data.append(['止损位', result.get('止损位', '无'), ''])
                    detail_data.append(['', '', ''])
                    
                    # 基础过滤结果
                    detail_data.append(['基础过滤', '', ''])
                    detail_data.append(['是否通过', '✅' if result.get('基础过滤', False) else '❌', ''])
                    if '详情' in result and isinstance(result['详情'], list):
                        for i, detail in enumerate(result['详情'][:5]):  # 只显示前5个详情
                            detail_data.append([f'详情{i+1}', detail, ''])
                    detail_data.append(['', '', ''])
                    
                    # 三振共振分析
                    detail_data.append(['三振共振分析', '', ''])
                    detail_data.append(['三级共振', '✅' if result.get('三振共振', False) else '❌', ''])
                    if '三振共振' in result and isinstance(result['三振共振'], dict):
                        resonance = result['三振共振']
                        detail_data.append(['个股趋势', '✅' if resonance.get('个股趋势', False) else '❌', ''])
                        detail_data.append(['行业趋势', '✅' if resonance.get('行业趋势', False) else '❌', ''])
                        detail_data.append(['大盘趋势', '✅' if resonance.get('大盘趋势', False) else '❌', ''])
                    detail_data.append(['', '', ''])
                    
                    # 主升浪分析
                    detail_data.append(['主升浪分析', '', ''])
                    detail_data.append(['主升浪状态', result.get('主升浪状态', '未知'), ''])
                    if '主升浪' in result and isinstance(result['主升浪'], dict):
                        bull_wave = result['主升浪']
                        detail_data.append(['持股状态', '✅' if bull_wave.get('持股状态', False) else '❌', ''])
                        detail_data.append(['空中加油', '✅' if bull_wave.get('空中加油', False) else '❌', ''])
                        detail_data.append(['MA5斜率', bull_wave.get('MA5斜率', 0), ''])
                    detail_data.append(['', '', ''])
                    
                    # 平台突破分析
                    detail_data.append(['平台突破分析', '', ''])
                    detail_data.append(['平台状态', result.get('平台状态', '未知'), ''])
                    detail_data.append(['突破信号', '✅' if result.get('突破信号', False) else '❌', ''])
                    detail_data.append(['买横信号', '✅' if result.get('买横信号', False) else '❌', ''])
                    detail_data.append(['', '', ''])
                    
                    # 技术细节
                    detail_data.append(['技术细节', '', ''])
                    detail_data.append(['破五反五', '✅' if result.get('破五反五', False) else '❌', ''])
                    detail_data.append(['筹码集中度', result.get('筹码集中度', '未知'), ''])
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
                    # 获取最新的技术指标数据
                    if stock_code in stock_data:
                        daily_data = stock_data[stock_code].get('daily')
                        if daily_data is not None and not daily_data.empty:
                            latest = daily_data.iloc[-1]
                            
                            # 提取关键技术指标
                            row = {
                                '股票代码': stock_code,
                                '股票名称': result.get('股票名称', '未知'),
                                '最新价': latest.get('收盘价', 0),
                                '成交量': latest.get('成交量', 0),
                                '成交额': latest.get('成交额', 0),
                                '换手率': latest.get('换手率', 0),
                                'MA5': latest.get('MA5', 0),
                                'MA10': latest.get('MA10', 0),
                                'MA20': latest.get('MA20', 0),
                                'MA60': latest.get('MA60', 0),
                                'MA250': latest.get('MA250', 0),
                                '均线排列': latest.get('均线排列', '未知'),
                                '价格距MA20': latest.get('价格距20日均线', 0),
                                '量比': latest.get('量比', 0),
                                'RSI': latest.get('RSI', 0),
                                'MACD': latest.get('MACD', 0),
                                'MACD_Signal': latest.get('MACD_Signal', 0),
                                'MACD_信号': latest.get('MACD_信号', 0),
                                '动能状态': latest.get('动能状态', '未知')
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
            # 创建Excel写入器
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"每日汇总报告_{timestamp}.xlsx"
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