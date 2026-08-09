#!/usr/bin/env python3
# simple_test.py - 简化版测试脚本，不依赖外部库
import os
import sys
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_demo_data():
    """创建演示数据"""
    print("🎯 创建演示数据...")
    
    # 生成模拟股票数据
    stocks = {
        'sh600150': {
            'name': '中国船舶',
            'data': generate_stock_data(),
            'analysis': {
                'main_wave': True,
                'resonance_score': 0.85,
                'pattern': '平台突破',
                'recommendation': '强烈买入'
            }
        },
        'sz000001': {
            'name': '平安银行',
            'data': generate_stock_data(),
            'analysis': {
                'main_wave': True,
                'resonance_score': 0.78,
                'pattern': '主升浪',
                'recommendation': '买入'
            }
        }
    }
    
    return stocks

def generate_stock_data():
    """生成模拟股票数据"""
    import random
    
    # 生成252天的数据（约1年）
    data = []
    base_price = random.uniform(20, 80)
    
    for i in range(252):
        date = datetime.now() - timedelta(days=252-i)
        
        # 只保留工作日
        if date.weekday() >= 5:
            continue
            
        # 生成价格数据
        open_price = base_price * (1 + random.uniform(-0.03, 0.03))
        high_price = open_price * (1 + random.uniform(0, 0.02))
        low_price = open_price * (1 - random.uniform(0, 0.02))
        close_price = random.uniform(low_price, high_price)
        
        # 生成成交量
        volume = random.randint(1000000, 10000000)
        
        # 计算简单移动平均
        if i >= 4:
            ma5 = sum([d['close'] for d in data[-4:]]) / 5
        else:
            ma5 = close_price
            
        data.append({
            'date': date.strftime('%Y-%m-%d'),
            'open': round(open_price, 2),
            'high': round(high_price, 2),
            'low': round(low_price, 2),
            'close': round(close_price, 2),
            'volume': volume,
            'ma5': round(ma5, 2)
        })
        
        base_price = close_price
    
    return data

def analyze_stock(stock_data):
    """分析股票数据"""
    print(f"📊 分析股票: {stock_data['name']} ({list(stock_data.keys())[0]})")
    
    # 获取分析结果
    analysis = stock_data['analysis']
    
    # 生成分析报告
    report = f"""
🎯 {stock_data['name']} ({list(stock_data.keys())[0]}) 分析报告
{'=' * 50}

📈 技术分析:
• 主升浪识别: {'✅' if analysis['main_wave'] else '❌'}
• 三振共振评分: {analysis['resonance_score']:.2f}/1.0
• 形态识别: {analysis['pattern']}
• 投资建议: {analysis['recommendation']}

💰 关键指标:
• 当前价格: {stock_data['data'][-1]['close']:.2f}
• MA5均线: {stock_data['data'][-1]['ma5']:.2f}
• 价格位置: {'高于MA5' if stock_data['data'][-1]['close'] > stock_data['data'][-1]['ma5'] else '低于MA5'}

🎯 Mystery理论分析:
• 大盘趋势: 向上 📈
• 行业趋势: 向上 📈
• 个股趋势: 向上 📈
• 共振强度: 强 🔥

⚠️ 风险提示:
• 注意市场波动风险
• 建议控制仓位
• 设置止损位

📋 操作建议:
• {analysis['recommendation']}
• 关注成交量变化
• 注意技术指标信号

---
分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
分析工具: Mystery趋势交易分析系统 v1.0
"""
    
    return report

def save_report(report, stock_code):
    """保存分析报告"""
    # 创建输出目录
    output_dir = 'output'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{output_dir}/analysis_report_{stock_code}_{timestamp}.txt"
    
    # 保存报告
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    return filename

def main():
    """主函数"""
    print("🚀 启动 Mystery趋势交易分析系统...")
    print("=" * 60)
    
    # 创建演示数据
    stocks = create_demo_data()
    
    # 分析每只股票
    all_reports = []
    for stock_code, stock_info in stocks.items():
        print(f"\n🔍 分析 {stock_info['name']} ({stock_code})...")
        
        # 生成分析报告
        report = analyze_stock(stock_info)
        all_reports.append(report)
        
        # 保存报告
        filename = save_report(report, stock_code)
        print(f"✅ 报告已保存: {filename}")
    
    # 生成汇总报告
    print("\n" + "=" * 60)
    print("📋 生成汇总报告...")
    
    summary_report = f"""
🎉 Mystery趋势交易分析系统 - 汇总报告
{'=' * 60}

📊 分析概览:
• 分析股票数量: {len(stocks)}
• 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
• 系统版本: v1.0.0

📈 分析结果:
"""
    
    for stock_code, stock_info in stocks.items():
        analysis = stock_info['analysis']
        summary_report += f"""
• {stock_info['name']} ({stock_code}):
  - 主升浪: {'是' if analysis['main_wave'] else '否'}
  - 共振评分: {analysis['resonance_score']:.2f}
  - 形态: {analysis['pattern']}
  - 建议: {analysis['recommendation']}
"""
    
    summary_report += f"""
🎯 总体建议:
• 市场整体趋势向好
• 关注共振强度较高的股票
• 建议采用分批建仓策略

📋 详细报告:
"""
    
    for i, report in enumerate(all_reports, 1):
        summary_report += f"\n--- 报告 {i} ---\n{report}\n"
    
    # 保存汇总报告
    summary_filename = save_report(summary_report, 'summary')
    print(f"✅ 汇总报告已保存: {summary_filename}")
    
    print("\n" + "=" * 60)
    print("🎉 分析完成！")
    print("📁 输出文件:")
    for stock_code, stock_info in stocks.items():
        filename = f"output/analysis_report_{stock_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        print(f"  • {filename}")
    print(f"  • {summary_filename}")
    print("=" * 60)

if __name__ == "__main__":
    main()