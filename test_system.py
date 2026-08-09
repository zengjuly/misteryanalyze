#!/usr/bin/env python3
# test_system.py - 系统功能测试脚本
import sys
import os
import time
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.exception_handler import ExceptionHandler, exception_handler, retry_on_failure
from config import load_config

class SystemTester:
    """系统测试类"""
    
    def __init__(self):
        self.config = load_config()
        self.exception_handler = ExceptionHandler()
        self.logger = logging.getLogger(__name__)
        
        # 测试结果
        self.test_results = {
            'config_loading': False,
            'exception_handling': False,
            'data_fetching': False,
            'indicator_calculation': False,
            'analysis_logic': False,
            'output_generation': False,
            'performance': False
        }
        
        # 性能测试数据
        self.performance_data = {}
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始系统功能测试...")
        print("=" * 60)
        
        # 1. 配置加载测试
        self.test_config_loading()
        
        # 2. 异常处理测试
        self.test_exception_handling()
        
        # 3. 数据获取测试
        self.test_data_fetching()
        
        # 4. 技术指标计算测试
        self.test_indicator_calculation()
        
        # 5. 分析逻辑测试
        self.test_analysis_logic()
        
        # 6. 输出生成测试
        self.test_output_generation()
        
        # 7. 性能测试
        self.test_performance()
        
        # 生成测试报告
        self.generate_test_report()
        
        return self.test_results
    
    def test_config_loading(self):
        """测试配置加载"""
        print("📋 测试1: 配置加载...")
        start_time = time.time()
        
        try:
            config = load_config()
            if config and isinstance(config, dict):
                self.test_results['config_loading'] = True
                self.performance_data['config_loading'] = time.time() - start_time
                print("✅ 配置加载测试通过")
            else:
                print("❌ 配置加载测试失败: 配置为空或格式错误")
        except Exception as e:
            print(f"❌ 配置加载测试失败: {e}")
    
    def test_exception_handling(self):
        """测试异常处理"""
        print("🚨 测试2: 异常处理...")
        start_time = time.time()
        
        try:
            # 测试正常异常处理
            try:
                raise ValueError("测试异常")
            except Exception as e:
                error_info = self.exception_handler.handle_exception(e, {"test": True})
                if error_info and 'error_type' in error_info:
                    self.test_results['exception_handling'] = True
                    self.performance_data['exception_handling'] = time.time() - start_time
                    print("✅ 异常处理测试通过")
                else:
                    print("❌ 异常处理测试失败: 错误信息格式错误")
        except Exception as e:
            print(f"❌ 异常处理测试失败: {e}")
    
    def test_data_fetching(self):
        """测试数据获取"""
        print("📊 测试3: 数据获取...")
        start_time = time.time()
        
        try:
            from data.baostock_client import BaostockClient
            
            client = BaostockClient()
            
            # 测试获取单个股票数据
            stock_data = client.get_stock_data(["sh600000"])
            if stock_data and "sh600000" in stock_data:
                self.test_results['data_fetching'] = True
                self.performance_data['data_fetching'] = time.time() - start_time
                print("✅ 数据获取测试通过")
            else:
                print("❌ 数据获取测试失败: 未获取到数据")
        except Exception as e:
            print(f"❌ 数据获取测试失败: {e}")
    
    def test_indicator_calculation(self):
        """测试技术指标计算"""
        print("📈 测试4: 技术指标计算...")
        start_time = time.time()
        
        try:
            from data.baostock_client import BaostockClient
            from indicators.ma_indicators import MAIndicators
            
            # 获取测试数据
            client = BaostockClient()
            stock_data = client.get_stock_data(["sh600000"])
            
            if stock_data and "sh600000" in stock_data:
                daily_data = stock_data["sh600000"].get("daily")
                if daily_data is not None and not daily_data.empty:
                    # 测试均线计算
                    ma_indicators = MAIndicators()
                    ma_results = ma_indicators.calculate_all_ma_indicators(daily_data)
                    
                    if ma_results and "MA5" in ma_results:
                        self.test_results['indicator_calculation'] = True
                        self.performance_data['indicator_calculation'] = time.time() - start_time
                        print("✅ 技术指标计算测试通过")
                    else:
                        print("❌ 技术指标计算测试失败: 指标计算结果为空")
                else:
                    print("❌ 技术指标计算测试失败: 数据为空")
            else:
                print("❌ 技术指标计算测试失败: 未获取到数据")
        except Exception as e:
            print(f"❌ 技术指标计算测试失败: {e}")
    
    def test_analysis_logic(self):
        """测试分析逻辑"""
        print("🎯 测试5: 分析逻辑...")
        start_time = time.time()
        
        try:
            from data.baostock_client import BaostockClient
            from analysis.mystery_logic import MysteryLogic
            
            # 获取测试数据
            client = BaostockClient()
            stock_data = client.get_stock_data(["sh600000"])
            
            if stock_data and "sh600000" in stock_data:
                daily_data = stock_data["sh600000"].get("daily")
                if daily_data is not None and not daily_data.empty:
                    # 测试基础过滤
                    mystery_logic = MysteryLogic()
                    basic_filter = mystery_logic.basic_filter({"daily": daily_data})
                    
                    if basic_filter and "通过" in basic_filter:
                        self.test_results['analysis_logic'] = True
                        self.performance_data['analysis_logic'] = time.time() - start_time
                        print("✅ 分析逻辑测试通过")
                    else:
                        print("❌ 分析逻辑测试失败: 基础过滤结果为空")
                else:
                    print("❌ 分析逻辑测试失败: 数据为空")
            else:
                print("❌ 分析逻辑测试失败: 未获取到数据")
        except Exception as e:
            print(f"❌ 分析逻辑测试失败: {e}")
    
    def test_output_generation(self):
        """测试输出生成"""
        print("📄 测试6: 输出生成...")
        start_time = time.time()
        
        try:
            from output.excel_generator import ExcelGenerator
            from output.html_generator import HTMLGenerator
            
            # 创建测试数据
            test_results = {
                "sh600000": {
                    "股票名称": "浦发银行",
                    "综合评分": 75.5,
                    "建议操作": "买入",
                    "止损位": "10.50",
                    "基础过滤": True,
                    "三振共振": True,
                    "主升浪状态": "主升浪",
                    "平台状态": "突破",
                    "破五反五": True,
                    "筹码集中度": "集中"
                }
            }
            
            test_data = {
                "sh600000": {
                    "daily": None  # 简化测试
                }
            }
            
            # 测试Excel生成
            excel_generator = ExcelGenerator()
            excel_path = excel_generator.generate_stock_analysis_report(test_results, test_data)
            
            if excel_path and os.path.exists(excel_path):
                # 测试HTML生成
                html_generator = HTMLGenerator()
                html_path = html_generator.generate_analysis_report(test_results, test_data)
                
                if html_path and os.path.exists(html_path):
                    self.test_results['output_generation'] = True
                    self.performance_data['output_generation'] = time.time() - start_time
                    print("✅ 输出生成测试通过")
                    
                    # 清理测试文件
                    os.remove(excel_path)
                    os.remove(html_path)
                else:
                    print("❌ 输出生成测试失败: HTML文件生成失败")
            else:
                print("❌ 输出生成测试失败: Excel文件生成失败")
        except Exception as e:
            print(f"❌ 输出生成测试失败: {e}")
    
    def test_performance(self):
        """测试性能"""
        print("⚡ 测试7: 性能测试...")
        start_time = time.time()
        
        try:
            # 测试批量数据处理性能
            from data.baostock_client import BaostockClient
            
            client = BaostockClient()
            
            # 测试获取多只股票数据
            test_stocks = ["sh600000", "sz000001", "sh600036"]
            
            start_time = time.time()
            stock_data = client.get_stock_data(test_stocks)
            fetch_time = time.time() - start_time
            
            if stock_data and len(stock_data) == len(test_stocks):
                self.test_results['performance'] = True
                self.performance_data['performance'] = fetch_time
                print(f"✅ 性能测试通过: 获取{len(test_stocks)}只股票数据耗时{fetch_time:.2f}秒")
            else:
                print("❌ 性能测试失败: 数据获取不完整")
        except Exception as e:
            print(f"❌ 性能测试失败: {e}")
    
    def generate_test_report(self):
        """生成测试报告"""
        print("\n📊 测试报告生成...")
        
        # 统计测试结果
        passed_tests = sum(1 for result in self.test_results.values() if result)
        total_tests = len(self.test_results)
        success_rate = (passed_tests / total_tests) * 100
        
        # 生成测试报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"test_report_{timestamp}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("Mystery趋势交易分析系统 - 测试报告\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"📊 测试项目总数: {total_tests}\n")
            f.write(f"✅ 通过测试: {passed_tests}\n")
            f.write(f"❌ 失败测试: {total_tests - passed_tests}\n")
            f.write(f"🎯 成功率: {success_rate:.1f}%\n\n")
            
            f.write("📋 详细测试结果:\n")
            f.write("-" * 30 + "\n")
            
            for test_name, result in self.test_results.items():
                status = "✅ 通过" if result else "❌ 失败"
                f.write(f"{test_name}: {status}\n")
            
            f.write("\n⚡ 性能测试结果:\n")
            f.write("-" * 30 + "\n")
            
            for test_name, duration in self.performance_data.items():
                f.write(f"{test_name}: {duration:.2f}秒\n")
            
            f.write("\n💡 建议:\n")
            f.write("-" * 30 + "\n")
            
            if success_rate < 80:
                f.write("🚨 系统稳定性较差，建议检查配置和依赖\n")
            elif success_rate < 100:
                f.write("⚠️ 系统存在部分问题，建议修复失败的测试项\n")
            else:
                f.write("✅ 系统运行正常，可以投入使用\n")
            
            f.write("\n" + "=" * 60 + "\n")
        
        print(f"📄 测试报告已生成: {report_path}")
        
        # 输出总结
        print("\n" + "=" * 60)
        print("🎯 测试总结")
        print("=" * 60)
        print(f"📊 测试项目总数: {total_tests}")
        print(f"✅ 通过测试: {passed_tests}")
        print(f"❌ 失败测试: {total_tests - passed_tests}")
        print(f"🎯 成功率: {success_rate:.1f}%")
        
        if success_rate == 100:
            print("🎉 系统运行正常，所有测试通过！")
        elif success_rate >= 80:
            print("✅ 系统基本正常，建议修复失败的测试项")
        else:
            print("🚨 系统存在较多问题，建议全面检查")

def main():
    """主函数"""
    try:
        # 创建测试实例
        tester = SystemTester()
        
        # 运行所有测试
        results = tester.run_all_tests()
        
        # 返回测试结果
        return results
        
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断测试")
        return None
    except Exception as e:
        print(f"❌ 测试运行异常: {e}")
        return None

if __name__ == "__main__":
    main()