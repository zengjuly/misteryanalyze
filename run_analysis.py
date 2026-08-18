#!/usr/bin/env python3
# run_analysis.py - 快速启动脚本
import sys
import os
import argparse

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import StockAnalysisSystem


def _load_watchlist_codes() -> list:
    """从自选股表读取代码列表（sh.600150 → sh600150，与config格式一致）
    依赖 WatchlistManager（data/watchlist_manager.py），MYSTERY_DB_PATH 环境变量指向生产库。
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'))
    try:
        from watchlist_manager import WatchlistManager
        codes = WatchlistManager().codes()
        # watchlist 存带点格式 sh.600150；main 分析流程与 config 一致用无点 sh600150
        return [c.replace('.', '') for c in codes]
    except Exception as e:
        print(f"❌ 读取自选股列表失败: {e}")
        return []

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Mystery趋势交易分析系统 - 快速启动')
    parser.add_argument('--mode', choices=['daily', 'single'], default='daily',
                       help='运行模式: daily(每日分析) 或 single(单只股票分析)')
    parser.add_argument('--stock', type=str, help='股票代码（单只股票分析模式使用）')
    parser.add_argument('--watchlist', action='store_true',
                       help='每日分析使用自选股列表（替代config中的股票列表）')
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
                if args.watchlist:
                    codes = _load_watchlist_codes()
                    if not codes:
                        print("❌ 自选股列表为空，无法分析")
                        return
                    print(f"⭐ 每日分析使用自选股列表（{len(codes)}只）")
                    system.run_daily_analysis(codes)
                else:
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