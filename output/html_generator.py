#!/usr/bin/env python3
# html_generator.py - HTML可视化报告生成器
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from typing import Dict, List, Optional, Any
import os
import json

class HTMLGenerator:
    """HTML可视化报告生成器"""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 创建CSS样式
        self.css_styles = """
        <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
        }
        .section {
            margin-bottom: 30px;
        }
        .section h2 {
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .stock-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }
        .stock-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .stock-info h3 {
            margin: 0;
            color: #333;
            font-size: 1.5em;
        }
        .stock-code {
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .score-badge {
            background: #667eea;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 1.1em;
        }
        .score-badge.high { background: #4CAF50; }
        .score-badge.medium { background: #FF9800; }
        .score-badge.low { background: #f44336; }
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }
        .metric {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }
        .metric-label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
        }
        .status {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .status.positive { background: #d4edda; color: #155724; }
        .status.negative { background: #f8d7da; color: #721c24; }
        .status.neutral { background: #e2e3e5; color: #383d41; }
        .details {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
        }
        .details h4 {
            margin: 0 0 10px 0;
            color: #333;
        }
        .details ul {
            margin: 0;
            padding-left: 20px;
        }
        .details li {
            margin-bottom: 5px;
            color: #666;
        }
        .chart-container {
            margin: 20px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        .stat-label {
            color: #666;
            font-size: 0.9em;
        }
        .recommendation {
            text-align: center;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            font-size: 1.2em;
            font-weight: bold;
        }
        .recommendation.strong-buy {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .recommendation.buy {
            background: #cce5ff;
            color: #004085;
            border: 1px solid #99d3ff;
        }
        .recommendation.watch {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        .recommendation.avoid {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        </style>
        """
    
    def generate_analysis_report(self, analysis_results: Dict[str, Any], 
                                stock_data: Dict[str, pd.DataFrame]) -> str:
        """
        生成分析报告HTML
        :param analysis_results: 分析结果字典
        :param stock_data: 股票数据字典
        :return: 生成的HTML文件路径
        """
        try:
            # 创建HTML文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"股票分析报告_{timestamp}.html"
            filepath = os.path.join(self.output_dir, filename)
            
            # 生成HTML内容
            html_content = self._generate_html_content(analysis_results, stock_data)
            
            # 写入HTML文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"✅ HTML报告生成完成: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ 生成HTML报告异常: {e}")
            raise
    
    def _generate_html_content(self, analysis_results: Dict[str, Any], 
                             stock_data: Dict[str, pd.DataFrame]) -> str:
        """生成HTML内容"""
        try:
            # 统计数据
            total_stocks = len(analysis_results)
            strong_buy_count = sum(1 for r in analysis_results.values() 
                                 if isinstance(r, dict) and r.get('建议操作') == '强烈买入')
            buy_count = sum(1 for r in analysis_results.values() 
                          if isinstance(r, dict) and r.get('建议操作') == '买入')
            watch_count = sum(1 for r in analysis_results.values() 
                            if isinstance(r, dict) and r.get('建议操作') == '关注')
            avoid_count = sum(1 for r in analysis_results.values() 
                            if isinstance(r, dict) and r.get('建议操作') == '观望')
            
            # 生成HTML内容
            html = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Mystery趋势交易分析报告</title>
                {self.css_styles}
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎯 Mystery趋势交易分析报告</h1>
                        <p>基于《Mistery趋势交易论》的智能选股系统</p>
                        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                    
                    <div class="section">
                        <h2>📊 总体统计</h2>
                        <div class="summary-stats">
                            <div class="stat-card">
                                <div class="stat-number">{total_stocks}</div>
                                <div class="stat-label">分析股票数</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">{strong_buy_count}</div>
                                <div class="stat-label">强烈买入</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">{buy_count}</div>
                                <div class="stat-label">买入</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">{watch_count}</div>
                                <div class="stat-label">关注</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">{avoid_count}</div>
                                <div class="stat-label">观望</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>📈 个股详细分析</h2>
            """
            
            # 按综合评分排序
            sorted_results = sorted(analysis_results.items(), 
                                  key=lambda x: x[1].get('综合评分', 0) if isinstance(x[1], dict) else 0, 
                                  reverse=True)
            
            for stock_code, result in sorted_results:
                if isinstance(result, dict) and '综合评分' in result:
                    html += self._generate_stock_card(stock_code, result, stock_data)
            
            html += """
                    </div>
                    
                    <div class="section">
                        <h2>📋 投资建议汇总</h2>
                        <div class="recommendation strong-buy">
                            🚀 强烈买入 ({strong_buy_count}只)
                        </div>
                        <div class="recommendation buy">
                            💰 买入 ({buy_count}只)
                        </div>
                        <div class="recommendation watch">
                            👀 关注 ({watch_count}只)
                        </div>
                        <div class="recommendation avoid">
                            ⚠️ 观望 ({avoid_count}只)
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>🔗 使用说明</h2>
                        <div class="details">
                            <h4>Mystery趋势交易论核心原则：</h4>
                            <ul>
                                <li><strong>顺大势逆小势</strong>：关注多周期共振（大盘+板块+个股）</li>
                                <li><strong>均线排列</strong>：MA5 > MA10 > MA20 > MA60 的多头排列</li>
                                <li><strong>三振共振</strong>：大盘趋势向上 + 行业趋势向上 + 个股趋势向上</li>
                                <li><strong>主升浪</strong>：股价沿MA5上涨，不破MA5则标记为"主升持股期"</li>
                                <li><strong>空中加油</strong>：缩量横盘整理（不破MA20），筹码峰在低位不动</li>
                                <li><strong>平台突破</strong>：放量突破箱体上沿（成交量需高于前均量1.5倍），MACD零轴上金叉</li>
                            </ul>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>⚠️ 风险提示</h2>
                        <div class="details">
                            <ul>
                                <li>本系统仅供参考，不构成投资建议</li>
                                <li>投资有风险，入市需谨慎</li>
                                <li>请结合市场实际情况和自身风险承受能力做出投资决策</li>
                                <li>建议设置止损位，控制风险</li>
                                <li>定期关注市场变化，及时调整投资策略</li>
                            </ul>
                        </div>
                    </div>
                    
                    <div class="footer">
                        <p style="text-align: center; color: #666; margin-top: 30px;">
                            © 2026 Mystery趋势交易分析系统 | 基于Python和Baostock构建
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return html
            
        except Exception as e:
            self.logger.error(f"❌ 生成HTML内容异常: {e}")
            return f"<html><body><h1>生成报告异常: {e}</h1></body></html>"
    
    def _generate_stock_card(self, stock_code: str, result: Dict[str, Any], 
                           stock_data: Dict[str, pd.DataFrame]) -> str:
        """生成个股卡片HTML"""
        try:
            # 获取股票基本信息
            stock_name = result.get('股票名称', '未知')
            score = result.get('综合评分', 0)
            recommendation = result.get('建议操作', '观望')
            stop_loss = result.get('止损位', '无')
            
            # 评分等级
            score_class = 'high' if score >= 80 else 'medium' if score >= 60 else 'low'
            
            # 状态样式
            status_class = 'positive' if recommendation in ['强烈买入', '买入'] else 'neutral' if recommendation == '关注' else 'negative'
            
            # 获取技术指标
            metrics = {}
            if stock_code in stock_data and 'daily' in stock_data[stock_code]:
                daily_data = stock_data[stock_code]['daily']
                if not daily_data.empty:
                    latest = daily_data.iloc[-1]
                    metrics = {
                        '最新价': latest.get('收盘价', 0),
                        '成交量': latest.get('成交量', 0),
                        '换手率': latest.get('换手率', 0),
                        'MA5': latest.get('MA5', 0),
                        'MA10': latest.get('MA10', 0),
                        'MA20': latest.get('MA20', 0),
                        'MA60': latest.get('MA60', 0),
                        '量比': latest.get('量比', 0),
                        'RSI': latest.get('RSI', 0),
                        'MACD': latest.get('MACD', 0)
                    }
            
            # 生成卡片HTML
            card_html = f"""
            <div class="stock-card">
                <div class="stock-header">
                    <div class="stock-info">
                        <h3>{stock_name}</h3>
                        <div class="stock-code">{stock_code}</div>
                    </div>
                    <div class="score-badge {score_class}">{score:.1f}分</div>
                </div>
                
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-label">最新价</div>
                        <div class="metric-value">{metrics.get('最新价', 0):.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">成交量</div>
                        <div class="metric-value">{metrics.get('成交量', 0):.0f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">换手率</div>
                        <div class="metric-value">{metrics.get('换手率', 0):.2f}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">MA5</div>
                        <div class="metric-value">{metrics.get('MA5', 0):.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">MA20</div>
                        <div class="metric-value">{metrics.get('MA20', 0):.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">MA60</div>
                        <div class="metric-value">{metrics.get('MA60', 0):.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">量比</div>
                        <div class="metric-value">{metrics.get('量比', 0):.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">RSI</div>
                        <div class="metric-value">{metrics.get('RSI', 0):.2f}</div>
                    </div>
                </div>
                
                <div style="margin: 15px 0;">
                    <span class="status {status_class}">建议操作: {recommendation}</span>
                    <span style="margin-left: 20px;">止损位: {stop_loss}</span>
                </div>
                
                <div class="details">
                    <h4>分析详情</h4>
                    <ul>
                        <li>基础过滤: {'✅ 通过' if result.get('基础过滤', False) else '❌ 不通过'}</li>
                        <li>三振共振: {'✅ 成立' if result.get('三振共振', False) else '❌ 不成立'}</li>
                        <li>主升浪状态: {result.get('主升浪状态', '未知')}</li>
                        <li>平台状态: {result.get('平台状态', '未知')}</li>
                        <li>破五反五: {'✅' if result.get('破五反五', False) else '❌'}</li>
                        <li>筹码集中度: {result.get('筹码集中度', '未知')}</li>
                    </ul>
                </div>
            </div>
            """
            
            return card_html
            
        except Exception as e:
            self.logger.error(f"❌ 生成个股卡片异常: {e}")
            return f"<div class='stock-card'><h3>生成卡片异常: {e}</h3></div>"
    
    def generate_real_time_dashboard(self, analysis_results: Dict[str, Any]) -> str:
        """
        生成实时仪表板HTML
        :param analysis_results: 分析结果字典
        :return: 生成的HTML文件路径
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"实时仪表板_{timestamp}.html"
            filepath = os.path.join(self.output_dir, filename)
            
            # 生成实时仪表板HTML
            html_content = self._generate_dashboard_content(analysis_results)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"✅ 实时仪表板生成完成: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"❌ 生成实时仪表板异常: {e}")
            raise
    
    def _generate_dashboard_content(self, analysis_results: Dict[str, Any]) -> str:
        """生成仪表板HTML内容"""
        try:
            # 统计数据
            total_stocks = len(analysis_results)
            strong_buy = [r for r in analysis_results.values() 
                         if isinstance(r, dict) and r.get('建议操作') == '强烈买入']
            buy = [r for r in analysis_results.values() 
                   if isinstance(r, dict) and r.get('建议操作') == '买入']
            watch = [r for r in analysis_results.values() 
                    if isinstance(r, dict) and r.get('建议操作') == '关注']
            avoid = [r for r in analysis_results.values() 
                    if isinstance(r, dict) and r.get('建议操作') == '观望']
            
            # 计算平均评分
            scores = [r.get('综合评分', 0) for r in analysis_results.values() if isinstance(r, dict)]
            avg_score = sum(scores) / len(scores) if scores else 0
            
            html = f"""
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>实时仪表板 - Mystery趋势交易系统</title>
                {self.css_styles}
                <script>
                    // 自动刷新
                    setTimeout(function() {{
                        location.reload();
                    }}, 30000); // 30秒刷新一次
                </script>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🚀 实时仪表板</h1>
                        <p>Mystery趋势交易系统 - 实时监控</p>
                        <p>更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    </div>
                    
                    <div class="section">
                        <h2>📈 实时统计</h2>
                        <div class="summary-stats">
                            <div class="stat-card">
                                <div class="stat-number">{total_stocks}</div>
                                <div class="stat-label">监控股票</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">{avg_score:.1f}</div>
                                <div class="stat-label">平均评分</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">{len(strong_buy)}</div>
                                <div class="stat-label">强烈买入</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">{len(buy)}</div>
                                <div class="stat-label">买入</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">{len(watch)}</div>
                                <div class="stat-label">关注</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-number">{len(avoid)}</div>
                                <div class="stat-label">观望</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>🎯 强烈买入股票</h2>
            """
            
            # 显示强烈买入的股票
            for result in strong_buy[:10]:  # 最多显示10只
                stock_code = list(analysis_results.keys())[list(analysis_results.values()).index(result)]
                html += self._generate_stock_card(stock_code, result, {})
            
            html += """
                    </div>
                    
                    <div class="section">
                        <h2>💰 买入股票</h2>
            """
            
            # 显示买入的股票
            for result in buy[:10]:  # 最多显示10只
                stock_code = list(analysis_results.keys())[list(analysis_results.values()).index(result)]
                html += self._generate_stock_card(stock_code, result, {})
            
            html += """
                    </div>
                    
                    <div class="section">
                        <h2>🔗 系统状态</h2>
                        <div class="details">
                            <h4>系统运行状态</h4>
                            <ul>
                                <li>✅ 数据获取: 正常</li>
                                <li>✅ 技术指标计算: 正常</li>
                                <li>✅ Mystery理论分析: 正常</li>
                                <li>✅ 形态识别: 正常</li>
                                <li>✅ 实时监控: 正常</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return html
            
        except Exception as e:
            self.logger.error(f"❌ 生成仪表板内容异常: {e}")
            return f"<html><body><h1>生成仪表板异常: {e}</h1></body></html>"