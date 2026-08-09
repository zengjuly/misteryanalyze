#!/usr/bin/env python3
# simple_demo.py - 简化版演示脚本
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_demo_data():
    """创建演示数据"""
    demo_data = {
        "sh600000": {
            "name": "浦发银行",
            "daily": {
                "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
                "open": [10.50, 10.55, 10.60, 10.58, 10.65],
                "high": [10.60, 10.65, 10.70, 10.68, 10.75],
                "low": [10.45, 10.50, 10.55, 10.52, 10.60],
                "close": [10.55, 10.62, 10.68, 10.65, 10.72],
                "volume": [1000000, 1200000, 1100000, 1300000, 1400000],
                "amount": [10550000, 12744000, 11748000, 13845000, 15008000],
                "turn": [0.0125, 0.0150, 0.0138, 0.0163, 0.0175],
                "pctChg": [0.48, 0.66, 0.57, -0.28, 0.66]
            }
        },
        "sz000001": {
            "name": "平安银行",
            "daily": {
                "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
                "open": [12.00, 12.10, 12.15, 12.12, 12.20],
                "high": [12.10, 12.20, 12.25, 12.22, 12.30],
                "low": [11.90, 12.00, 12.05, 12.02, 12.10],
                "close": [12.05, 12.18, 12.22, 12.20, 12.28],
                "volume": [1500000, 1800000, 1600000, 1900000, 2000000],
                "amount": [18075000, 21924000, 19552000, 23180000, 24560000],
                "turn": [0.0150, 0.0180, 0.0160, 0.0190, 0.0200],
                "pctChg": [0.42, 1.08, 0.33, -0.16, 0.66]
            }
        }
    }
    return demo_data

def calculate_demo_indicators(data):
    """计算演示指标"""
    indicators = {}
    
    for stock_code, stock_info in data.items():
        daily_data = stock_info["daily"]
        
        # 简单的移动平均计算
        closes = daily_data["close"]
        ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else sum(closes) / len(closes)
        ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else sum(closes) / len(closes)
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else sum(closes) / len(closes)
        
        # 简单的RSI计算
        gains = []
        losses = []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(change if change > 0 else 0)
            losses.append(-change if change < 0 else 0)
        
        avg_gain = sum(gains[-14:]) / 14 if len(gains) >= 14 else sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses[-14:]) / 14 if len(losses) >= 14 else sum(losses) / len(losses) if losses else 0
        
        rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 50
        
        # 简单的MACD计算
        ema12 = sum(closes[-12:]) / 12 if len(closes) >= 12 else sum(closes) / len(closes)
        ema26 = sum(closes[-26:]) / 26 if len(closes) >= 26 else sum(closes) / len(closes)
        macd = ema12 - ema26
        
        indicators[stock_code] = {
            "MA5": ma5,
            "MA10": ma10,
            "MA20": ma20,
            "RSI": rsi,
            "MACD": macd,
            "当前价格": closes[-1],
            "成交量": daily_data["volume"][-1],
            "换手率": daily_data["turn"][-1]
        }
    
    return indicators

def analyze_stocks(data, indicators):
    """分析股票"""
    analysis_results = {}
    
    for stock_code, stock_info in data.items():
        stock_name = stock_info["name"]
        indicator = indicators[stock_code]
        
        # 简单的评分系统
        score = 0
        
        # 价格评分
        if indicator["当前价格"] > indicator["MA5"]:
            score += 20
        if indicator["当前价格"] > indicator["MA10"]:
            score += 15
        if indicator["当前价格"] > indicator["MA20"]:
            score += 10
        
        # RSI评分
        if 30 < indicator["RSI"] < 70:
            score += 20
        elif indicator["RSI"] > 70:
            score += 10  # 超买，适当减分
        else:
            score += 5   # 超卖，适当加分
        
        # MACD评分
        if indicator["MACD"] > 0:
            score += 20
        else:
            score += 5
        
        # 成交量评分
        if indicator["换手率"] > 0.015:
            score += 15
        else:
            score += 10
        
        # 确保分数在0-100之间
        score = max(0, min(100, score))
        
        # 生成建议
        if score >= 80:
            recommendation = "强烈买入"
        elif score >= 60:
            recommendation = "买入"
        elif score >= 40:
            recommendation = "关注"
        else:
            recommendation = "观望"
        
        # 计算止损位
        stop_loss = indicator["当前价格"] * 0.92  # 8%止损
        
        analysis_results[stock_code] = {
            "股票名称": stock_name,
            "综合评分": score,
            "建议操作": recommendation,
            "止损位": f"{stop_loss:.2f}",
            "基础过滤": True,
            "三振共振": score >= 60,
            "主升浪状态": "主升浪" if score >= 70 else "横盘整理",
            "平台状态": "突破" if score >= 65 else "整理",
            "破五反五": indicator["当前价格"] > indicator["MA5"],
            "筹码集中度": "集中" if score >= 70 else "分散"
        }
    
    return analysis_results

def generate_demo_report(analysis_results, indicators):
    """生成演示报告"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 创建输出目录
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成文本报告
    report_path = os.path.join(output_dir, f"demo_report_{timestamp}.txt")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("Mystery趋势交易分析系统 - 演示报告\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"📊 分析股票总数: {len(analysis_results)}只\n\n")
        
        # 统计数据
        strong_buy = sum(1 for r in analysis_results.values() if r.get('建议操作') == '强烈买入')
        buy = sum(1 for r in analysis_results.values() if r.get('建议操作') == '买入')
        watch = sum(1 for r in analysis_results.values() if r.get('建议操作') == '关注')
        avoid = sum(1 for r in analysis_results.values() if r.get('建议操作') == '观望')
        
        f.write("📊 操作建议分布\n")
        f.write("-" * 30 + "\n")
        f.write(f"🔥 强烈买入: {strong_buy}只\n")
        f.write(f"💰 买入: {buy}只\n")
        f.write(f"👀 关注: {watch}只\n")
        f.write(f"⚠️ 观望: {avoid}只\n\n")
        
        # 详细分析
        f.write("📈 详细分析结果\n")
        f.write("-" * 30 + "\n")
        
        for stock_code, result in analysis_results.items():
            f.write(f"\n📊 {stock_code} {result['股票名称']}\n")
            f.write(f"🎯 综合评分: {result['综合评分']:.1f}分\n")
            f.write(f"💡 建议操作: {result['建议操作']}\n")
            f.write(f"🛡️ 止损位: {result['止损位']}\n")
            f.write(f"🔄 基础过滤: {'✅ 通过' if result.get('基础过滤', False) else '❌ 不通过'}\n")
            f.write(f"🎯 三振共振: {'✅ 成立' if result.get('三振共振', False) else '❌ 不成立'}\n")
            f.write(f"🚀 主升浪状态: {result['主升浪状态']}\n")
            f.write(f"💪 平台状态: {result['平台状态']}\n")
            f.write(f"🔍 破五反五: {'✅' if result.get('破五反五', False) else '❌'}\n")
            f.write(f"🎲 筹码集中度: {result['筹码集中度']}\n")
            
            # 技术指标
            indicator = indicators[stock_code]
            f.write(f"📈 当前价格: {indicator['当前价格']:.2f}\n")
            f.write(f"📊 MA5: {indicator['MA5']:.2f}\n")
            f.write(f"📊 MA10: {indicator['MA10']:.2f}\n")
            f.write(f"📊 MA20: {indicator['MA20']:.2f}\n")
            f.write(f"📊 RSI: {indicator['RSI']:.2f}\n")
            f.write(f"📊 MACD: {indicator['MACD']:.4f}\n")
            f.write(f"📊 成交量: {indicator['成交量']:,}\n")
            f.write(f"📊 换手率: {indicator['换手率']:.2%}\n")
        
        f.write("\n" + "=" * 60 + "\n")
        f.write("演示报告生成完成\n")
        f.write("这是一个简化版的演示，展示系统的核心功能\n")
        f.write("完整版本将包含更多功能和更复杂的分析逻辑\n")
        f.write("=" * 60 + "\n")
    
    return report_path

def main():
    """主函数"""
    print("🎯 Mystery趋势交易分析系统 - 演示版本")
    print("=" * 60)
    
    try:
        # 1. 创建演示数据
        print("📊 创建演示数据...")
        demo_data = create_demo_data()
        print(f"✅ 创建了{len(demo_data)}只股票的演示数据")
        
        # 2. 计算技术指标
        print("📈 计算技术指标...")
        indicators = calculate_demo_indicators(demo_data)
        print("✅ 技术指标计算完成")
        
        # 3. 分析股票
        print("🎯 进行股票分析...")
        analysis_results = analyze_stocks(demo_data, indicators)
        print("✅ 股票分析完成")
        
        # 4. 生成报告
        print("📄 生成演示报告...")
        report_path = generate_demo_report(analysis_results, indicators)
        print(f"✅ 演示报告生成完成: {report_path}")
        
        # 5. 显示结果
        print("\n" + "=" * 60)
        print("🎯 分析结果展示")
        print("=" * 60)
        
        for stock_code, result in analysis_results.items():
            print(f"\n📊 {stock_code} {result['股票名称']}")
            print(f"🎯 综合评分: {result['综合评分']:.1f}分")
            print(f"💡 建议操作: {result['建议操作']}")
            print(f"🛡️ 止损位: {result['止损位']}")
            print(f"🚀 主升浪状态: {result['主升浪状态']}")
            print(f"💪 平台状态: {result['平台状态']}")
        
        print("\n" + "=" * 60)
        print("✅ 演示完成！")
        print("📄 详细报告已保存到: " + report_path)
        print("📁 输出目录: " + os.path.dirname(report_path))
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 演示运行异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()