#!/usr/bin/env python3
# run_analysis.py - 快速启动脚本
import sys
import os
import argparse

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import StockAnalysisSystem

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Mystery趋势交易分析系统 - 快速启动')
    parser.add_argument('--mode', choices=['daily', 'single'], default='daily',
                       help='运行模式: daily(每日分析) 或 single(单只股票分析)')
    parser.add_argument('--stock', type=str, help='股票代码（单只股票分析模式使用）')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                       help='配置文件路径')
    parser.add_argument('--test', action='store_true', help='运行系统测试')
    
    args = parser.parse_args()
    
    try:
        if args.test:
            # 运行系统测试
            from test_system import main as test_main
            test_results = test_main()
            if test_results:
                print("\n✅ 系统测试完成")
            else:
                print("\n❌ 系统测试失败")
        else:
            # 创建分析系统实例
            system = StockAnalysisSystem(args.config)
            
            if args.mode == 'daily':
                # 每日分析模式
                print("🌅 开始每日分析...")
                system.run_daily_analysis()
            elif args.mode == 'single':
                # 单只股票分析模式
                if not args.stock:
                    print("❌ 单只股票分析模式需要指定 --stock 参数")
                    return
                
                print(f"🎯 开始分析股票: {args.stock}")
                system.analyze_single_stock(args.stock)
            else:
                print("❌ 无效的运行模式")
                return
                
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断程序")
    except Exception as e:
        print(f"❌ 程序运行异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()