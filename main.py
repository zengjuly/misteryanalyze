#!/usr/bin/env python3
# main.py - 主执行程序
import sys
import os
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

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
        
        # 确保输出目录存在（支持相对/绝对路径）
        output_dir = self.config['output_dir']
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_dir)
        os.makedirs(output_dir, exist_ok=True)
        self.config['output_dir'] = output_dir
        
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
                
                # 指标回填：将带指标的数据写回processed_data，供报告生成器使用
                for code, df_with_indicators in indicators_data.items():
                    if code in processed_data and 'daily' in processed_data[code]:
                        processed_data[code]['daily'] = df_with_indicators
                
                # 获取行业板块映射（code -> 所属板块）
                self.logger.info("🏢 获取行业板块信息...")
                industry_map = self._build_industry_map(industry_data)
                
                # 获取财务数据（ROE/EPS/PE/PB/股息率）
                self.logger.info("💹 获取财务数据...")
                financial_data_map = self._get_all_financial_data(processed_data)
                
                # 多周期分析（周线/月线趋势）
                self.logger.info("📅 多周期分析（周线/月线）...")
                multi_period_map = self._analyze_multi_period(processed_data)
                
                # 行业趋势分析（同行业样本股票近5日平均涨跌幅）
                self.logger.info("🏭 行业趋势分析...")
                industry_trend_map = {}
                for code in processed_data:
                    trend_info = self._analyze_industry_trend(code, industry_map, processed_data)
                    industry_trend_map[code] = trend_info
                
                # Mystery理论分析
                self.logger.info("🎯 Mystery理论分析...")
                analysis_results = self._perform_mystery_analysis(
                    indicators_data, processed_data, industry_map,
                    financial_data_map, market_data, industry_trend_map, multi_period_map
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
                    summary, recommendations, final_results
                )
                
                # 生成实时仪表板
                dashboard_path = self.html_generator.generate_real_time_dashboard(final_results)
                
                self.logger.info("✅ 股票分析完成！")
                
                # git同步输出目录到远端（若为git仓库）
                git_synced = self._sync_output_to_git(excel_path, html_path, summary_path, dashboard_path)
                
                return {
                    'analysis_results': final_results,
                    'summary': summary,
                    'recommendations': recommendations,
                    'excel_report': excel_path,
                    'html_report': html_path,
                    'summary_report': summary_path,
                    'dashboard': dashboard_path,
                    'git_synced': git_synced
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
    
    def _build_industry_map(self, industry_data: pd.DataFrame) -> Dict:
        """
        构建股票代码到所属板块的映射
        :param industry_data: baostock行业分类数据（含code/industry列）
        :return: {'code_map': {股票代码: 所属板块}, 'industry_codes': {行业: [股票代码]}}
        """
        code_map = {}
        industry_codes = {}
        try:
            if industry_data is not None and not industry_data.empty:
                for _, row in industry_data.iterrows():
                    code = row.get('code', '')
                    industry = row.get('industry', '')
                    if code and industry:
                        code_map[code] = industry
                        industry_codes.setdefault(industry, []).append(code)
                self.logger.info(f"🏢 构建行业映射: {len(code_map)} 只股票, {len(industry_codes)} 个行业")
        except Exception as e:
            self.logger.warning(f"⚠️ 构建行业映射异常: {e}")
        return {'code_map': code_map, 'industry_codes': industry_codes}
    
    def _analyze_industry_trend(self, stock_code: str, industry_map: Dict,
                                processed_data: Dict, max_samples: int = 3) -> Dict:
        """
        分析个股所属行业的板块趋势（同行业样本股票近5日平均涨跌幅）
        :param stock_code: 股票代码
        :param industry_map: 行业映射 {'code_map':..., 'industry_codes':...}
        :param processed_data: 已获取的股票数据（优先使用缓存）
        :param max_samples: 抽样股票数量
        :return: {'趋势': True/False/None, '行业': 行业名, '平均涨跌幅': x, '样本数': n,
                  '板块评级': str, '近5日': x, '近10日': x, '近20日': x, '样本股票': [名称]}
        """
        result = {'趋势': None, '行业': '未知', '平均涨跌幅': None, '样本数': 0,
                  '板块评级': '数据不足', '近5日': None, '近10日': None, '近20日': None,
                  '样本股票': []}
        try:
            code_map = industry_map.get('code_map', {})
            industry_codes = industry_map.get('industry_codes', {})
            
            # 标准化代码
            norm_code = self.baostock_client.normalize_stock_code(stock_code)
            industry = code_map.get(norm_code, '未知')
            result['行业'] = industry
            
            if industry == '未知':
                return result
            
            # 取同行业股票（排除自身），抽样
            peers = [c for c in industry_codes.get(industry, []) if c != norm_code][:max_samples]
            if not peers:
                return result
            
            # 计算同行业样本股票的多周期平均涨跌幅
            pct_5d, pct_10d, pct_20d = [], [], []
            sample_names = []
            for peer in peers:
                # 优先使用已获取的数据
                peer_short = peer.replace('.', '')  # sh.600150 -> sh600150
                peer_data = processed_data.get(peer_short, {})
                daily = peer_data.get('daily') if isinstance(peer_data, dict) else None
                if daily is None or daily.empty:
                    try:
                        # 获取最近30天数据
                        from datetime import timedelta
                        end = datetime.now().strftime('%Y-%m-%d')
                        start = (datetime.now() - timedelta(days=45)).strftime('%Y-%m-%d')
                        daily = self.baostock_client.get_daily_data(peer, start, end)
                    except Exception:
                        daily = None
                
                if daily is not None and not daily.empty and '涨跌幅' in daily.columns:
                    pct_series = daily['涨跌幅'].dropna()
                    if len(pct_series) >= 5:
                        pct_5d.append(pct_series.tail(5).mean())
                    if len(pct_series) >= 10:
                        pct_10d.append(pct_series.tail(10).mean())
                    if len(pct_series) >= 20:
                        pct_20d.append(pct_series.tail(20).mean())
                    # 样本股票名称
                    try:
                        sample_names.append(self.baostock_client.get_stock_name(peer))
                    except Exception:
                        sample_names.append(peer)
            
            if pct_5d:
                avg_5d = float(sum(pct_5d) / len(pct_5d))
                result['平均涨跌幅'] = round(avg_5d, 2)
                result['近5日'] = round(avg_5d, 2)
                result['样本数'] = len(pct_5d)
                result['样本股票'] = sample_names
                if pct_10d:
                    result['近10日'] = round(float(sum(pct_10d) / len(pct_10d)), 2)
                if pct_20d:
                    result['近20日'] = round(float(sum(pct_20d) / len(pct_20d)), 2)
                
                # 板块评级（综合多周期表现）
                result['趋势'] = bool(avg_5d > 0)  # 转为Python bool，避免np.bool_的is比较问题
                trend_10 = (result['近10日'] or 0)
                trend_20 = (result['近20日'] or 0)
                if avg_5d > 0.5 and trend_10 > 0 and trend_20 > 0:
                    result['板块评级'] = '强势上涨'
                elif avg_5d > 0 and trend_10 > 0:
                    result['板块评级'] = '稳步走强'
                elif avg_5d > 0:
                    result['板块评级'] = '短期走强'
                elif avg_5d < -0.5 and trend_10 < 0:
                    result['板块评级'] = '弱势下跌'
                elif avg_5d < 0:
                    result['板块评级'] = '短期走弱'
                else:
                    result['板块评级'] = '震荡整理'
                self.logger.info(
                    f"🏭 {stock_code} 行业[{industry}] 样本{len(pct_5d)}只, 近5日{avg_5d:.2f}%, "
                    f"评级[{result['板块评级']}]")
        except Exception as e:
            self.logger.warning(f"⚠️ 行业趋势分析异常 {stock_code}: {e}")
        return result
    
    def _analyze_multi_period(self, processed_data: Dict) -> Dict:
        """
        多周期分析：计算周线/月线趋势
        :param processed_data: 含daily/weekly/monthly的数据
        :return: {股票代码: {'周线趋势': str, '月线趋势': str, '多周期共振': bool}}
        """
        multi_period = {}
        try:
            for stock_code, data in processed_data.items():
                result = {'周线趋势': '未知', '月线趋势': '未知', '多周期共振': False}
                
                # 周线分析：MA5/MA10/MA20 多头排列
                weekly = data.get('weekly') if isinstance(data, dict) else None
                if weekly is not None and not weekly.empty and '收盘价' in weekly.columns:
                    w = weekly.copy()
                    w['MA5'] = w['收盘价'].rolling(5).mean()
                    w['MA10'] = w['收盘价'].rolling(10).mean()
                    w['MA20'] = w['收盘价'].rolling(20).mean()
                    latest_w = w.iloc[-1]
                    if (pd.notna(latest_w['MA5']) and pd.notna(latest_w['MA10']) and
                        pd.notna(latest_w['MA20'])):
                        if (latest_w['MA5'] > latest_w['MA10'] > latest_w['MA20'] and
                            latest_w['收盘价'] > latest_w['MA20']):
                            result['周线趋势'] = '多头排列'
                        elif latest_w['MA5'] < latest_w['MA10'] < latest_w['MA20']:
                            result['周线趋势'] = '空头排列'
                        else:
                            result['周线趋势'] = '震荡整理'
                        result['周线最新价'] = round(float(latest_w['收盘价']), 2)
                        result['周线MA20'] = round(float(latest_w['MA20']), 2)
                
                # 月线分析：MA5/MA10 多头排列
                monthly = data.get('monthly') if isinstance(data, dict) else None
                if monthly is not None and not monthly.empty and '收盘价' in monthly.columns:
                    m = monthly.copy()
                    m['MA5'] = m['收盘价'].rolling(5).mean()
                    m['MA10'] = m['收盘价'].rolling(10).mean()
                    latest_m = m.iloc[-1]
                    if pd.notna(latest_m['MA5']) and pd.notna(latest_m['MA10']):
                        if latest_m['MA5'] > latest_m['MA10'] and latest_m['收盘价'] > latest_m['MA10']:
                            result['月线趋势'] = '多头排列'
                        elif latest_m['MA5'] < latest_m['MA10']:
                            result['月线趋势'] = '空头排列'
                        else:
                            result['月线趋势'] = '震荡整理'
                        result['月线最新价'] = round(float(latest_m['收盘价']), 2)
                        result['月线MA10'] = round(float(latest_m['MA10']), 2)
                
                # 多周期共振：日线(个股趋势) + 周线多头 + 月线多头
                if (result['周线趋势'] == '多头排列' and result['月线趋势'] == '多头排列'):
                    result['多周期共振'] = True
                
                multi_period[stock_code] = result
        except Exception as e:
            self.logger.error(f"❌ 多周期分析异常: {e}")
        return multi_period
    
    def _sync_output_to_git(self, *report_paths) -> bool:
        """
        将生成的报告同步到输出目录的git仓库并推送远端
        :param report_paths: 生成的报告文件路径
        :return: 是否同步成功
        """
        import subprocess as sp
        output_dir = self.config['output_dir']
        try:
            # 检查是否为git仓库
            check = sp.run(['git', '-C', output_dir, 'rev-parse', '--is-inside-work-tree'],
                          capture_output=True, text=True, timeout=30)
            if check.returncode != 0:
                self.logger.warning(f"⚠️ {output_dir} 不是git仓库，跳过git同步")
                return False
            
            # 检查是否有远端
            remote = sp.run(['git', '-C', output_dir, 'remote'],
                           capture_output=True, text=True, timeout=30)
            has_remote = bool(remote.stdout.strip())
            
            # git add 生成的报告文件
            paths = [os.path.basename(p) for p in report_paths if p]
            if not paths:
                # 没有指定文件则添加全部
                sp.run(['git', '-C', output_dir, 'add', '-A'], capture_output=True, text=True, timeout=30)
            else:
                sp.run(['git', '-C', output_dir, 'add', '--'] + paths,
                      capture_output=True, text=True, timeout=30)
            
            # 检查是否有变更需要提交
            status = sp.run(['git', '-C', output_dir, 'status', '--porcelain'],
                          capture_output=True, text=True, timeout=30)
            if not status.stdout.strip():
                self.logger.info("📦 输出目录无新变更，跳过提交")
                return True
            
            # 提交
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            commit_msg = f"📊 股票分析报告更新 {timestamp}"
            commit = sp.run(['git', '-C', output_dir, 'commit', '-m', commit_msg],
                          capture_output=True, text=True, timeout=60)
            if commit.returncode != 0:
                self.logger.error(f"❌ git提交失败: {commit.stderr.strip()}")
                return False
            
            self.logger.info(f"✅ git提交成功: {commit_msg}")
            
            # 推送到远端
            if has_remote:
                push = sp.run(['git', '-C', output_dir, 'push'],
                            capture_output=True, text=True, timeout=120)
                if push.returncode == 0:
                    self.logger.info("🚀 git推送远端成功")
                else:
                    self.logger.warning(f"⚠️ git推送远端失败: {push.stderr.strip()[:200]}")
            else:
                self.logger.warning("⚠️ 输出目录未配置远端，仅本地提交")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ git同步异常: {e}")
            return False

    def _get_all_financial_data(self, processed_data: Dict) -> Dict:
        """
        获取所有股票的基础财务数据和股票名称
        :param processed_data: 处理后的股票数据
        :return: {股票代码: 财务数据字典(含'股票名称')}
        """
        financial_map = {}
        try:
            for stock_code, data in processed_data.items():
                daily_data = data.get('daily')
                current_price = None
                if daily_data is not None and not daily_data.empty:
                    current_price = float(daily_data.iloc[-1].get('收盘价', 0) or 0)
                
                financial = self.baostock_client.get_financial_data(stock_code, current_price)
                # 一并获取真实股票名称
                financial['股票名称'] = self.baostock_client.get_stock_name(stock_code)
                financial_map[stock_code] = financial
        except Exception as e:
            self.logger.error(f"❌ 获取财务数据异常: {e}")
        return financial_map
    
    def _perform_mystery_analysis(self, indicators_data: Dict, processed_data: Dict,
                                 industry_map: Dict = None, financial_data_map: Dict = None,
                                 market_data: Dict = None, industry_trend_map: Dict = None,
                                 multi_period_map: Dict = None) -> Dict:
        """执行Mystery理论分析"""
        try:
            analysis_results = {}
            industry_map = industry_map or {}
            financial_data_map = financial_data_map or {}
            industry_trend_map = industry_trend_map or {}
            multi_period_map = multi_period_map or {}
            
            for stock_code, indicators in indicators_data.items():
                # 获取对应的数据
                stock_data = processed_data.get(stock_code, {})
                daily_data = stock_data.get('daily')
                
                if daily_data is None or daily_data.empty:
                    self.logger.warning(f"⚠️ {stock_code} 无日线数据，跳过分析")
                    continue
                
                # 基础过滤
                basic_passed, basic_errors = self.mystery_logic.basic_filter(indicators)
                
                # 行业趋势（外部计算的真实板块数据）
                industry_info = industry_trend_map.get(stock_code, {})
                industry_trend = industry_info.get('趋势')  # True/False/None
                industry = industry_info.get('行业', '未知')
                industry_avg_pct = industry_info.get('平均涨跌幅')
                industry_rating = industry_info.get('板块评级', '数据不足')
                industry_pct_10d = industry_info.get('近10日')
                industry_pct_20d = industry_info.get('近20日')
                industry_samples = industry_info.get('样本股票', [])
                
                # 三振共振分析（真实大盘指数 + 真实行业趋势）
                resonance_analysis = self.mystery_logic.three_resonance_analysis(
                    indicators, market_data, industry_trend)
                
                # 主升浪分析
                bull_wave_analysis = self.mystery_logic.main_bull_wave_analysis(indicators)
                
                # 主升浪8项指标对比表
                bull_wave_checklist = self.mystery_logic.main_bull_wave_checklist(
                    indicators, industry_trend)
                
                # 平台突破分析
                platform_breakthrough = self.mystery_logic.platform_breakthrough_analysis(indicators, stock_code)
                
                # 技术细节捕捉（破五反五、筹码集中度）
                technical_detail = self.mystery_logic.technical_detail_capture(indicators)
                
                # 综合评分与建议（复用综合分析逻辑）
                comprehensive = self.mystery_logic.comprehensive_analysis(indicators)
                
                # 提取最新交易日的技术指标值（供报告展示）
                latest = indicators.iloc[-1]
                
                # 财务数据
                financial = financial_data_map.get(stock_code, {})
                
                # 真实股票名称（优先财务数据中获取的名称）
                stock_name = financial.get('股票名称') or stock_data.get('name', stock_code)
                
                # 多周期数据
                multi_period = multi_period_map.get(stock_code, {})
                
                # 汇总分析结果
                analysis_results[stock_code] = {
                    '股票代码': stock_code,
                    '股票名称': stock_name,
                    '综合评分': comprehensive.get('综合评分', 0),
                    '基础过滤': basic_passed,
                    '基础过滤详情': basic_errors,
                    '基础过滤排除原因': basic_errors if not basic_passed else [],  # 排除原因（供报告明确展示）
                    '三振共振': resonance_analysis.get('三级共振', False),
                    '三振共振详情': resonance_analysis.get('详情', []),
                    '个股趋势': resonance_analysis.get('个股趋势', False),
                    '行业趋势': resonance_analysis.get('行业趋势', False),
                    '大盘趋势': resonance_analysis.get('大盘趋势', False),
                    '主升浪状态': bull_wave_analysis.get('主升浪状态', '未知'),
                    '主升浪判定依据': bull_wave_analysis.get('判定依据', []),
                    '主升浪详情': bull_wave_analysis.get('详情', []),
                    '平台状态': platform_breakthrough.get('平台状态', '未知'),
                    '平台范围': platform_breakthrough.get('平台范围'),
                    '平台详情': platform_breakthrough.get('详情', []),
                    '自适应平台': platform_breakthrough.get('自适应平台'),
                    '建议操作': comprehensive.get('建议操作', '观望'),
                    '止损位': comprehensive.get('止损位'),
                    '破五反五': technical_detail.get('破五反五', False),
                    '筹码集中度': technical_detail.get('筹码集中度', '未知'),
                    '筹码集中度数值': technical_detail.get('筹码集中度数值'),
                    '筹码趋势': technical_detail.get('筹码趋势', '未知'),
                    # 所属板块与行业趋势
                    '所属板块': industry,
                    '板块评级': industry_rating,
                    '板块近5日': industry_avg_pct,
                    '板块近10日': industry_pct_10d,
                    '板块近20日': industry_pct_20d,
                    '板块样本': industry_samples,
                    '行业平均涨跌幅': industry_avg_pct,
                    # 主升浪8项指标对比表
                    '主升浪指标对比': bull_wave_checklist,
                    '主升浪满足数量': bull_wave_checklist.get('满足数量', 0),
                    '主升浪综合判断': bull_wave_checklist.get('综合判断', '未知'),
                    # 多周期分析
                    '周线趋势': multi_period.get('周线趋势', '未知'),
                    '月线趋势': multi_period.get('月线趋势', '未知'),
                    '周线最新价': multi_period.get('周线最新价'),
                    '周线MA20': multi_period.get('周线MA20'),
                    '月线最新价': multi_period.get('月线最新价'),
                    '月线MA10': multi_period.get('月线MA10'),
                    '多周期共振': multi_period.get('多周期共振', False),
                    # 技术指标值（最新交易日）
                    '最新价': latest.get('收盘价', 0),
                    'MA5': latest.get('MA5', 0),
                    'MA10': latest.get('MA10', 0),
                    'MA20': latest.get('MA20', 0),
                    'MA60': latest.get('MA60', 0),
                    'MA250': latest.get('MA250', 0),
                    '量比': latest.get('量比', 0),
                    'RSI': latest.get('RSI', 0),
                    'MACD': latest.get('MACD', 0),
                    'MACD_Signal': latest.get('MACD_Signal', 0),
                    'MACD_信号': latest.get('MACD_信号', 0),
                    '动能状态': latest.get('动能状态', '未知'),
                    '量价配合度': latest.get('量价配合度', 0),
                    '均线排列': latest.get('均线排列', 0),
                    '换手率': latest.get('换手率', 0),
                    '成交量': latest.get('成交量', 0),
                    # 财务指标
                    'ROE': financial.get('ROE'),
                    'EPS': financial.get('EPS'),
                    'PE': financial.get('PE'),
                    'PB': financial.get('PB'),
                    '股息率': financial.get('股息率'),
                    '每股股息': financial.get('每股股息'),
                    '财务报告期': financial.get('报告期'),
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
                print(f"🏢 所属板块: {analysis.get('所属板块', '未知')}")
                print(f"🎯 综合评分: {analysis.get('综合评分', 0):.1f}分")
                print(f"💡 建议操作: {analysis.get('建议操作', '未知')}")
                print(f"🛡️ 止损位: {analysis.get('止损位', '无')}")
                print(f"🔄 基础过滤: {'✅ 通过' if analysis.get('基础过滤', False) else '❌ 不通过'}")
                if not analysis.get('基础过滤', False):
                    print("   🚫 排除原因:")
                    for reason in (analysis.get('基础过滤排除原因') or analysis.get('基础过滤详情') or []):
                        print(f"      - {reason}")
                
                print("\n🎯 三振共振:")
                print(f"📈 个股趋势: {'✅ 走强' if analysis.get('个股趋势', False) else '❌ 走弱'}")
                print(f"🏭 行业趋势: {'✅ 走强' if analysis.get('行业趋势', False) else '❌ 走弱'} "
                      f"评级[{analysis.get('板块评级', '数据不足')}]")
                print(f"   📊 板块近5日: {analysis.get('板块近5日', '-')}% | "
                      f"近10日: {analysis.get('板块近10日', '-')}% | 近20日: {analysis.get('板块近20日', '-')}%")
                if analysis.get('板块样本'):
                    print(f"   📋 板块样本: {', '.join(map(str, analysis.get('板块样本', [])[:3]))}")
                print(f"📊 大盘趋势: {'✅ 走强' if analysis.get('大盘趋势', False) else '❌ 走弱'}")
                print(f"🎯 三振共振: {'✅ 成立' if analysis.get('三振共振', False) else '❌ 不成立'}")
                
                print("\n📅 多周期分析:")
                print(f"📊 周线: {analysis.get('周线趋势', '未知')} (最新价: {analysis.get('周线最新价', '-')}, MA20: {analysis.get('周线MA20', '-')})")
                print(f"📅 月线: {analysis.get('月线趋势', '未知')} (最新价: {analysis.get('月线最新价', '-')}, MA10: {analysis.get('月线MA10', '-')})")
                print(f"🔗 多周期共振: {'✅' if analysis.get('多周期共振', False) else '❌'}")
                
                print(f"🚀 主升浪状态: {analysis.get('主升浪状态', '未知')}")
                for basis in analysis.get('主升浪判定依据', []) or []:
                    print(f"   ↳ {basis}")
                print(f"💪 平台状态: {analysis.get('平台状态', '未知')}")
                pr = analysis.get('平台范围')
                if pr:
                    print(f"   📦 平台箱体(近20日): 下沿 {pr.get('下沿', '-')} ~ 上沿 {pr.get('上沿', '-')}")
                ap = analysis.get('自适应平台')
                if ap and ap.get('POC') is not None:
                    print(f"   🔬 自适应VAP-ATR平台: POC {ap.get('POC')} | "
                          f"上轨 {ap.get('自适应上轨')} | 下轨 {ap.get('自适应下轨')} | "
                          f"ATR {ap.get('ATR')}")
                    ap_cycle = ap.get('自适应周期')
                    if ap_cycle:
                        print(f"   ⏱️ 自适应周期(换手率驱动): N={ap_cycle.get('adaptive_n')}日 "
                              f"(日均换手{ap_cycle.get('avg_turnover')}%, 理论N={ap_cycle.get('theoretical_n')}) | "
                              f"快ATR={ap_cycle.get('atr_m')}日 k={ap_cycle.get('k')}")
                print(f"🔍 主要形态: {analysis.get('主要形态', '无')}")
                print(f"📊 形态置信度: {analysis.get('形态置信度', 0):.1f}%")
                print(f"🎯 破五反五: {'✅' if analysis.get('破五反五', False) else '❌'}")
                chip_val = analysis.get('筹码集中度数值')
                chip_str = f"（近20日均换手率 {chip_val}%）" if chip_val is not None else ""
                print(f"🎲 筹码集中度: {analysis.get('筹码集中度', '未知')}{chip_str} "
                      f"趋势: {analysis.get('筹码趋势', '未知')}")
                
                print("\n📋 主升浪8项指标对比表:")
                checklist = analysis.get('主升浪指标对比', {})
                for key in ['长期横盘3个月以上', '60日均线开始向上', '股价突破平台',
                            '放量超20日均量2倍', '回踩不破+MACD零轴金叉', 'RSI>50继续走强',
                            '主力资金连续流入', '行业板块同步走强']:
                    mark = '✅' if checklist.get(key, False) else '❌'
                    print(f"  {mark} {key}")
                print(f"📊 满足 {analysis.get('主升浪满足数量', 0)}/8 项, 综合判断: {analysis.get('主升浪综合判断', '未知')}")
                
                print("\n📈 技术指标（最新交易日）:")
                print(f"💰 最新价: {analysis.get('最新价', 0):.2f}  换手率: {analysis.get('换手率', 0):.2f}%  量比: {analysis.get('量比', 0):.2f}")
                print(f"📊 MA5: {analysis.get('MA5', 0):.2f}  MA10: {analysis.get('MA10', 0):.2f}  MA20: {analysis.get('MA20', 0):.2f}  MA60: {analysis.get('MA60', 0):.2f}  MA250: {analysis.get('MA250', 0):.2f}")
                print(f"📈 RSI: {analysis.get('RSI', 0):.2f}  MACD: {analysis.get('MACD', 0):.2f}  信号: {analysis.get('MACD_信号', '未知')}")
                print(f"⚡ 动能状态: {analysis.get('动能状态', '未知')}  量价配合度: {analysis.get('量价配合度', 0):.2f}")
                
                print("\n💹 财务指标:")
                print(f"🏦 ROE: {analysis.get('ROE', '-')}  EPS: {analysis.get('EPS', '-')}  PE: {analysis.get('PE', '-')}  PB: {analysis.get('PB', '-')}  股息率: {analysis.get('股息率', '-')}%  (报告期: {analysis.get('财务报告期', '-')})")
                
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