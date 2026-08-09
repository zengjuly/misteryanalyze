#!/usr/bin/env python3
# main.py - 主执行程序
import sys
import os
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data.baostock_client import BaostockClient
from data.data_processor import DataProcessor
from indicators.ma_indicators import MAIndicators
from indicators.trend_indicators import TrendIndicators
from indicators.momentum_indicators import MomentumIndicators
from analysis.mystery_logic import MysteryLogic
from analysis.resonance_analyzer import ResonanceAnalyzer
from analysis.pattern_recognition import PatternRecognition
from summary_analyzer import SummaryAnalyzer
from output.excel_generator import ExcelGenerator
from output.html_generator import HTMLGenerator

class StockAnalysisSystem:
    """股票分析系统主类"""
    
    def __init__(self, config_file: str = "config/config.yaml"):
        self.config_file = config_file
        self.config = self._load_config()
        
        # 初始化日志系统
        self._setup_logging()
        
        # 初始化各个模块
        self.baostock_client = BaostockClient()
        self.data_processor = DataProcessor(self.baostock_client)
        self.ma_indicators = MAIndicators()
        self.trend_indicators = TrendIndicators()
        self.momentum_indicators = MomentumIndicators()
        self.mystery_logic = MysteryLogic()
        self.resonance_analyzer = ResonanceAnalyzer()
        self.pattern_recognition = PatternRecognition()
        self.summary_analyzer = SummaryAnalyzer(self.config['output_dir'])
        self.excel_generator = ExcelGenerator(self.config['output_dir'])
        self.html_generator = HTMLGenerator(self.config['output_dir'])
        
        self.logger = logging.getLogger(__name__)
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            import yaml
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 设置默认值
            if 'output_dir' not in config:
                config['output_dir'] = 'output'
            
            if 'log_level' not in config:
                config['log_level'] = 'INFO'
            
            if 'stocks' not in config:
                config['stocks'] = []
            
            if 'industries' not in config:
                config['industries'] = []
            
            if 'market_indices' not in config:
                config['market_indices'] = ['sh000001', 'sz399001', 'sz399006']
            
            return config
            
        except Exception as e:
            # 如果配置文件不存在，使用默认配置
            return {
                'output_dir': 'output',
                'log_level': 'INFO',
                'stocks': [],
                'industries': [],
                'market_indices': ['sh000001', 'sz399001', 'sz399006']
            }
    
    def _setup_logging(self):
        """设置日志系统"""
        log_level = getattr(logging, self.config['log_level'].upper())
        
        # 创建日志目录
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 文件处理器
        file_handler = logging.FileHandler(
            os.path.join(log_dir, f'stock_analysis_{datetime.now().strftime("%Y%m%d")}.log'),
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        
        # 配置根日志记录器
        logging.basicConfig(
            level=log_level,
            handlers=[file_handler, console_handler]
        )
    
    def analyze_stocks(self, stock_codes: List[str] = None) -> Dict:
        """
        分析股票
        :param stock_codes: 股票代码列表，如果为None则使用配置文件中的股票
        :return: 分析结果字典
        """
        try:
            self.logger.info("🚀 开始股票分析...")
            
            # 如果没有指定股票代码，使用配置文件中的股票
            if stock_codes is None:
                stock_codes = self.config['stocks']
            
            if not stock_codes:
                self.logger.warning("⚠️ 没有指定要分析的股票")
                return {}
            
            # 登录baostock数据源
            if not self.baostock_client.login():
                self.logger.error("❌ Baostock登录失败，无法获取数据")
                return {}
            
            try:
                # 获取股票数据（通过DataProcessor，内部处理baostock调用）
                self.logger.info(f"📊 获取股票数据，共{len(stock_codes)}只股票")
                stock_data = self.data_processor.get_all_stocks_data(stock_codes)
                
                # 获取行业数据
                industry_data = self.baostock_client.get_industry_data()
                
                # 获取大盘数据
                market_data = self.data_processor.get_market_index_data()
                
                # 数据预处理（get_all_stocks_data 已返回 {code: {'daily','weekly','monthly'}} 结构）
                self.logger.info("🔧 数据预处理...")
                processed_data = stock_data
                
                # 计算技术指标
                self.logger.info("📈 计算技术指标...")
                indicators_data = self._calculate_all_indicators(processed_data)
                
                # Mystery理论分析
                self.logger.info("🎯 Mystery理论分析...")
                analysis_results = self._perform_mystery_analysis(
                    indicators_data, processed_data
                )
                
                # 形态识别
                self.logger.info("🔍 形态识别...")
                pattern_results = self._recognize_patterns(processed_data)
                
                # 合并分析结果
                self.logger.info("📋 合并分析结果...")
                final_results = self._merge_analysis_results(
                    analysis_results, pattern_results, processed_data
                )
                
                # 汇总分析
                self.logger.info("📊 汇总分析...")
                summary = self.summary_analyzer.summarize_analysis_results(final_results)
                recommendations = self.summary_analyzer.generate_recommendations(summary)
                
                # 生成报告
                self.logger.info("📄 生成报告...")
                excel_path = self.excel_generator.generate_stock_analysis_report(
                    final_results, processed_data
                )
                html_path = self.html_generator.generate_analysis_report(
                    final_results, processed_data
                )
                summary_path = self.summary_analyzer.export_summary_report(
                    summary, recommendations
                )
                
                # 生成实时仪表板
                dashboard_path = self.html_generator.generate_real_time_dashboard(final_results)
                
                self.logger.info("✅ 股票分析完成！")
                
                return {
                    'analysis_results': final_results,
                    'summary': summary,
                    'recommendations': recommendations,
                    'excel_report': excel_path,
                    'html_report': html_path,
                    'summary_report': summary_path,
                    'dashboard': dashboard_path
                }
                
            finally:
                # 退出baostock登录
                self.baostock_client.logout()
            
        except Exception as e:
            self.logger.error(f"❌ 股票分析异常: {e}")
            raise
    
    def _calculate_all_indicators(self, processed_data: Dict) -> Dict:
        """计算所有技术指标"""
        try:
            indicators_data = {}
            
            for stock_code, data in processed_data.items():
                if 'daily' in data and not data['daily'].empty:
                    daily_data = data['daily'].copy()
                    
                    # 计算均线指标
                    daily_data = self.ma_indicators.calculate_ma(daily_data)
                    daily_data = self.ma_indicators.calculate_ma_arrangement(daily_data)
                    daily_data = self.ma_indicators.calculate_ma_slope(daily_data)
                    daily_data = self.ma_indicators.analyze_ma_signals(daily_data)
                    
                    # 计算趋势指标
                    daily_data = self.trend_indicators.calculate_macd(daily_data)
                    daily_data = self.trend_indicators.calculate_rsi(daily_data)
                    daily_data = self.trend_indicators.calculate_trend_strength(daily_data)
                    daily_data = self.trend_indicators.analyze_macd_signals(daily_data)
                    daily_data = self.trend_indicators.analyze_rsi_signals(daily_data)
                    
                    # 计算动能指标
                    daily_data = self.momentum_indicators.calculate_volume_ratio(daily_data)
                    daily_data = self.momentum_indicators.calculate_turnover_rate(daily_data)
                    daily_data = self.momentum_indicators.calculate_price_momentum(daily_data)
                    daily_data = self.momentum_indicators.calculate_volume_price_relation(daily_data)
                    daily_data = self.momentum_indicators.calculate_volume_signals(daily_data)
                    
                    indicators_data[stock_code] = daily_data
            
            return indicators_data
            
        except Exception as e:
            self.logger.error(f"❌ 计算技术指标异常: {e}")
            raise
    
    def _perform_mystery_analysis(self, indicators_data: Dict, processed_data: Dict) -> Dict:
        """执行Mystery理论分析"""
        try:
            analysis_results = {}
            
            for stock_code, indicators in indicators_data.items():
                # 获取对应的数据
                stock_data = processed_data.get(stock_code, {})
                daily_data = stock_data.get('daily')
                
                if daily_data is None or daily_data.empty:
                    self.logger.warning(f"⚠️ {stock_code} 无日线数据，跳过分析")
                    continue
                
                # 基础过滤
                basic_passed, basic_errors = self.mystery_logic.basic_filter(indicators)
                
                # 三振共振分析（使用MysteryLogic内置方法）
                resonance_analysis = self.mystery_logic.three_resonance_analysis(indicators)
                
                # 主升浪分析
                bull_wave_analysis = self.mystery_logic.main_bull_wave_analysis(indicators)
                
                # 平台突破分析
                platform_breakthrough = self.mystery_logic.platform_breakthrough_analysis(indicators)
                
                # 技术细节捕捉（破五反五、筹码集中度）
                technical_detail = self.mystery_logic.technical_detail_capture(indicators)
                
                # 综合评分与建议（复用综合分析逻辑）
                comprehensive = self.mystery_logic.comprehensive_analysis(indicators)
                
                # 汇总分析结果
                analysis_results[stock_code] = {
                    '股票代码': stock_code,
                    '股票名称': stock_data.get('name', stock_code),
                    '综合评分': comprehensive.get('综合评分', 0),
                    '基础过滤': basic_passed,
                    '基础过滤详情': basic_errors,
                    '三振共振': resonance_analysis.get('三级共振', False),
                    '三振共振详情': resonance_analysis.get('详情', []),
                    '主升浪状态': bull_wave_analysis.get('主升浪状态', '未知'),
                    '主升浪详情': bull_wave_analysis.get('详情', []),
                    '平台状态': platform_breakthrough.get('平台状态', '未知'),
                    '平台详情': platform_breakthrough.get('详情', []),
                    '建议操作': comprehensive.get('建议操作', '观望'),
                    '止损位': comprehensive.get('止损位'),
                    '破五反五': technical_detail.get('破五反五', False),
                    '筹码集中度': technical_detail.get('筹码集中度', '未知')
                }
            
            return analysis_results
            
        except Exception as e:
            self.logger.error(f"❌ Mystery理论分析异常: {e}")
            raise
    
    def _recognize_patterns(self, processed_data: Dict) -> Dict:
        """识别形态"""
        try:
            pattern_results = {}
            
            for stock_code, data in processed_data.items():
                if 'daily' in data and not data['daily'].empty:
                    daily_data = data['daily']
                    
                    # 识别所有形态
                    all_patterns = self.pattern_recognition.recognize_all_patterns(daily_data)
                    
                    pattern_results[stock_code] = all_patterns
            
            return pattern_results
            
        except Exception as e:
            self.logger.error(f"❌ 形态识别异常: {e}")
            raise
    
    def _merge_analysis_results(self, analysis_results: Dict, pattern_results: Dict, 
                              processed_data: Dict) -> Dict:
        """合并分析结果"""
        try:
            merged_results = {}
            
            for stock_code, analysis in analysis_results.items():
                merged_results[stock_code] = analysis
                
                # 添加形态识别结果
                if stock_code in pattern_results:
                    merged_results[stock_code].update(pattern_results[stock_code])
            
            return merged_results
            
        except Exception as e:
            self.logger.error(f"❌ 合并分析结果异常: {e}")
            raise
    
    def run_daily_analysis(self):
        """运行每日分析"""
        try:
            self.logger.info("🌅 开始每日分析...")
            
            # 执行分析
            results = self.analyze_stocks()
            
            if results:
                # 输出结果摘要
                summary = results['summary']
                recommendations = results['recommendations']
                
                print("\n" + "=" * 60)
                print("📊 Mystery趋势交易分析系统 - 每日分析结果")
                print("=" * 60)
                print(f"📅 分析时间: {summary.get('生成时间', '未知')}")
                print(f"📊 分析股票总数: {summary.get('分析股票总数', 0)}只")
                print(f"📈 平均评分: {summary.get('平均评分', 0):.1f}分")
                print(f"🔥 强烈买入: {summary.get('强烈买入', 0)}只")
                print(f"💰 买入: {summary.get('买入', 0)}只")
                print(f"👀 关注: {summary.get('关注', 0)}只")
                print(f"⚠️ 观望: {summary.get('观望', 0)}只")
                print(f"💡 总体建议: {recommendations.get('总体建议', '未知')}")
                print(f"📊 仓位建议: {recommendations.get('仓位建议', '未知')}")
                print(f"🎮 操作策略: {recommendations.get('操作策略', '未知')}")
                print(f"📈 市场判断: {recommendations.get('市场判断', '未知')}")
                
                print("\n🌟 重点关注股票:")
                for stock in recommendations.get('重点关注', [])[:5]:
                    print(f"📈 {stock['股票代码']} {stock['股票名称']} - 评分: {stock['综合评分']:.1f} - 止损: {stock['止损位']}")
                
                print("\n⚠️ 风险提示:")
                for warning in summary.get('风险提示', []):
                    print(f"🚨 {warning}")
                
                print("\n📄 生成的报告:")
                print(f"📊 Excel报告: {results['excel_report']}")
                print(f"🌐 HTML报告: {results['html_report']}")
                print(f"📋 汇总报告: {results['summary_report']}")
                print(f"📊 实时仪表板: {results['dashboard']}")
                
                print("\n✅ 每日分析完成！")
            
        except Exception as e:
            self.logger.error(f"❌ 每日分析异常: {e}")
            print(f"❌ 每日分析异常: {e}")
            raise
    
    def analyze_single_stock(self, stock_code: str) -> Dict:
        """分析单只股票"""
        try:
            self.logger.info(f"🎯 开始分析单只股票: {stock_code}")
            
            # 执行分析
            results = self.analyze_stocks([stock_code])
            
            if results and stock_code in results['analysis_results']:
                analysis = results['analysis_results'][stock_code]
                
                print("\n" + "=" * 60)
                print(f"📊 {stock_code} 详细分析结果")
                print("=" * 60)
                print(f"📈 股票名称: {analysis.get('股票名称', '未知')}")
                print(f"🎯 综合评分: {analysis.get('综合评分', 0):.1f}分")
                print(f"💡 建议操作: {analysis.get('建议操作', '未知')}")
                print(f"🛡️ 止损位: {analysis.get('止损位', '无')}")
                print(f"🔄 基础过滤: {'✅ 通过' if analysis.get('基础过滤', False) else '❌ 不通过'}")
                print(f"🎯 三振共振: {'✅ 成立' if analysis.get('三振共振', False) else '❌ 不成立'}")
                print(f"🚀 主升浪状态: {analysis.get('主升浪状态', '未知')}")
                print(f"💪 平台状态: {analysis.get('平台状态', '未知')}")
                print(f"🔍 主要形态: {analysis.get('主要形态', '无')}")
                print(f"📊 形态置信度: {analysis.get('形态置信度', 0):.1f}%")
                print(f"🎯 破五反五: {'✅' if analysis.get('破五反五', False) else '❌'}")
                print(f"🎲 筹码集中度: {analysis.get('筹码集中度', '未知')}")
                
                print("\n📋 详细分析:")
                if '基础过滤详情' in analysis:
                    for detail in analysis['基础过滤详情']:
                        print(f"• {detail}")
                
                if '三振共振详情' in analysis:
                    for detail in analysis['三振共振详情']:
                        print(f"• {detail}")
                
                if '主升浪详情' in analysis:
                    for detail in analysis['主升浪详情']:
                        print(f"• {detail}")
                
                if '平台详情' in analysis:
                    for detail in analysis['平台详情']:
                        print(f"• {detail}")
                
                return results
            
        except Exception as e:
            self.logger.error(f"❌ 单只股票分析异常: {e}")
            print(f"❌ 单只股票分析异常: {e}")
            raise

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Mystery趋势交易分析系统')
    parser.add_argument('--mode', choices=['daily', 'single'], default='daily',
                       help='运行模式: daily(每日分析) 或 single(单只股票分析)')
    parser.add_argument('--stock', type=str, help='股票代码（单只股票分析模式使用）')
    parser.add_argument('--stocks', type=str, help='股票代码列表，逗号分隔')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                       help='配置文件路径')
    
    args = parser.parse_args()
    
    try:
        # 创建分析系统实例
        system = StockAnalysisSystem(args.config)
        
        if args.mode == 'daily':
            # 每日分析模式
            system.run_daily_analysis()
        elif args.mode == 'single':
            # 单只股票分析模式
            if not args.stock:
                print("❌ 单只股票分析模式需要指定 --stock 参数")
                return
            
            results = system.analyze_single_stock(args.stock)
            
        else:
            print("❌ 无效的运行模式")
            return
            
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断程序")
    except Exception as e:
        print(f"❌ 程序运行异常: {e}")
        logging.error(f"程序运行异常: {e}")

if __name__ == "__main__":
    main()