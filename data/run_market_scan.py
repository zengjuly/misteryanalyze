#!/usr/bin/env python3
# run_market_scan.py - 全量自适应智能扫描分析引擎（基于docs/gemmi_an.md数据中枢方案）
"""
全市场扫描分析脚本
==================
理论来源: docs/gemmi_an.md（数据中枢与全量自动化分析方案）

功能:
  1. load_local_cached_tickers: 从本地SQLite缓存加载股票列表与行情（毫秒级）
  2. 基于个股换手率的自适应窗口计算（gemmi_an.md 自适应周期）
  3. 自适应 VAP-ATR 平台中枢识别（docs/design.md）
  4. 主升浪8项指标 + 三振共振 + 多周期箱体
  5. 信号捕获: 自适应VAP-ATR突破 / 筹码低位共振
  6. 生成 Excel/HTML/汇总报告到 output 目录 + git 同步

用法:
  python run_market_scan.py                  # 全量扫描缓存中的股票
  python run_market_scan.py --limit 100      # 仅扫描前100只
  python run_market_scan.py --sync           # 先同步再扫描
  python run_market_scan.py --period daily   # 指定K线周期
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

# 项目根目录（用于导入 main.py 等）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.data_engine import MysteryDataEngine, DEFAULT_LOOKBACK_DAYS
from data.db_manager import DEFAULT_DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S')
logger = logging.getLogger('run_market_scan')


def load_local_cached_tickers(engine: MysteryDataEngine,
                              period: str = 'daily',
                              limit: int = None,
                              force_sync: bool = False,
                              sync_days: int = None) -> list:
    """
    从本地缓存加载股票列表（未缓存或缓存为空时自动同步）
    :param engine: 数据引擎
    :param period: K线周期
    :param limit: 限制数量
    :param force_sync: 强制先同步
    :param sync_days: 同步回溯天数
    :return: 股票代码列表
    """
    cached = engine.db.get_cached_tickers(period)
    if force_sync or not cached:
        logger.info("📥 缓存为空或强制同步，开始拉取数据...")
        from data.sync_all_market import get_all_a_shares, sync_worker
        from concurrent.futures import ThreadPoolExecutor
        import threading

        codes = get_all_a_shares(engine)
        if limit:
            codes = codes[:limit]
        if sync_days is None:
            sync_days = DEFAULT_LOOKBACK_DAYS.get(period, 1100)
        progress = {'ok': 0, 'fail': 0}
        lock = threading.Lock()
        end = datetime.now()
        start = end - timedelta(days=sync_days)
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(sync_worker, engine, c, [period], sync_days,
                                 progress, lock) for c in codes]
            for f in futures:
                f.result()
        logger.info(f"✅ 同步完成: 成功{progress['ok']} 失败{progress['fail']}")
        cached = engine.db.get_cached_tickers(period)

    if limit:
        cached = cached[:limit]
    logger.info(f"📋 从本地缓存加载 {len(cached)} 只股票（{period}）")
    return cached


def scan_single_stock(engine: MysteryDataEngine, code: str,
                      period: str = 'daily') -> dict:
    """
    扫描单只股票：自适应窗口 + VAP-ATR + 主升浪指标 + 信号捕获
    :param engine: 数据引擎
    :param code: 股票代码
    :return: 分析结果字典
    """
    from main import StockAnalysisSystem

    try:
        # 从本地缓存加载行情（Cache-Aside：未命中自动回填）
        kline = engine.get_kline(code, period)
        if kline is None or kline.empty:
            return {'股票代码': code, '综合评分': 0, '信号': '数据不足'}

        # 转换为系统标准中文列名
        df = kline.rename(columns={
            'open': '开盘价', 'high': '最高价', 'low': '最低价',
            'close': '收盘价', 'volume': '成交量', 'amount': '成交额',
            'turn': '换手率', 'pctChg': '涨跌幅',
        })

        # 自适应周期计算（换手率驱动）
        from analysis.adaptive_platform import calculate_adaptive_lookback
        adaptive = calculate_adaptive_lookback(df)
        adaptive_n = adaptive.get('adaptive_n', 30)

        # 技术指标计算（复用系统指标管线）
        sys = StockAnalysisSystem('config/config.yaml')
        indicators = sys._calculate_all_indicators({'code': {'daily': df}})['code']

        # 自适应 VAP-ATR 平台
        from analysis.adaptive_platform import analyze_adaptive_platform
        platform = analyze_adaptive_platform(indicators, code)

        # 主升浪8项指标（行业趋势暂用None，全量扫描无板块实时数据）
        from analysis.mystery_logic import MysteryLogic
        ml = MysteryLogic()
        checklist = ml.main_bull_wave_checklist(indicators, industry_trend=None)

        # 信号捕获: VAP-ATR突破 / 筹码低位共振
        signals = []
        if platform.get('突破信号'):
            signals.append('VAP-ATR突破')
        chip = ml.technical_detail_capture(indicators)
        if chip.get('筹码集中度数值') is not None and chip.get('筹码集中度数值') < 2:
            signals.append('筹码低位共振')

        result = {
            '股票代码': code,
            '股票名称': '',  # 由外部补充
            '综合评分': 0,
            '自适应N': adaptive_n,
            'POC': platform.get('POC'),
            '自适应上轨': platform.get('自适应上轨'),
            '自适应下轨': platform.get('自适应下轨'),
            '平台状态': platform.get('平台状态'),
            '突破信号': platform.get('突破信号'),
            '主升浪满足': checklist.get('满足数量', 0),
            '主升浪综合判断': checklist.get('综合判断', '未知'),
            '筹码集中度': chip.get('筹码集中度'),
            '筹码集中度数值': chip.get('筹码集中度数值'),
            '信号': '、'.join(signals) if signals else '无',
            '最新价': float(df['收盘价'].iloc[-1]) if '收盘价' in df.columns else None,
        }
        return result
    except Exception as e:
        logger.warning(f"⚠️ {code} 扫描异常: {e}")
        return {'股票代码': code, '综合评分': 0, '信号': '异常'}


def run_market_scan(limit: int = None, period: str = 'daily',
                    sync_first: bool = False, top_n: int = 20,
                    output_dir: str = None) -> dict:
    """
    全量扫描分析主函数
    :param limit: 扫描股票数量限制
    :param period: K线周期
    :param sync_first: 是否先同步数据
    :param top_n: 生成报告的Top N（按信号数/评分排序）
    :param output_dir: 输出目录（默认config中的output_dir）
    """
    start_time = time.time()
    engine = MysteryDataEngine()

    # 1. 加载缓存股票列表
    codes = load_local_cached_tickers(engine, period, limit=limit,
                                      force_sync=sync_first)

    # 2. 逐只扫描（单线程，避免baostock并发问题）
    logger.info(f"🔍 开始全量扫描 {len(codes)} 只股票...")
    results = []
    for i, code in enumerate(codes, 1):
        r = scan_single_stock(engine, code, period)
        results.append(r)
        if i % 100 == 0 or i == len(codes):
            logger.info(f"⏳ 扫描进度: {i}/{len(codes)}")

    # 3. 补充股票名称（从缓存证券信息表）
    info_df = engine.db.get_stock_info(stock_only=True)
    name_map = dict(zip(info_df['code'], info_df['code_name'])) if not info_df.empty else {}
    for r in results:
        if '股票代码' in r:
            r['股票名称'] = name_map.get(r['股票代码'], r['股票代码'])

    # 4. 信号统计
    signal_stocks = [r for r in results if r.get('信号') and r['信号'] != '无']
    breakout_stocks = [r for r in results if r.get('突破信号')]
    logger.info(f"🎯 信号统计: 总扫描{len(results)}, "
                f"含信号{len(signal_stocks)}, VAP-ATR突破{len(breakout_stocks)}")

    # 5. 生成报告（Top N）
    from utils import build_report_filename
    results_df = pd.DataFrame(results)
    if results_df.empty:
        logger.warning("⚠️ 无扫描结果")
        engine.close()
        return {'扫描数': 0}

    # 排序：信号优先，其次突破，再按满足数
    def sort_key(r):
        return (
            1 if r.get('信号') and r['信号'] != '无' else 0,
            1 if r.get('突破信号') else 0,
            r.get('主升浪满足', 0),
        )
    results.sort(key=sort_key, reverse=True)
    top_df = results_df.head(top_n)

    # 输出到 output 目录
    if output_dir is None:
        from main import StockAnalysisSystem
        sys_tmp = StockAnalysisSystem('config/config.yaml')
        output_dir = sys_tmp.config.get('output_dir', 'output')
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # 文本汇总
    txt_path = os.path.join(output_dir, f'市场扫描报告_{timestamp}.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"=== 全市场扫描报告 {datetime.now()} ===\n")
        f.write(f"扫描股票数: {len(results)} | 含信号: {len(signal_stocks)} "
                f"| VAP-ATR突破: {len(breakout_stocks)}\n\n")
        f.write("【信号股票 Top】\n")
        for r in signal_stocks[:top_n]:
            f.write(f"  {r.get('股票名称', '')} ({r.get('股票代码')}): "
                    f"{r.get('信号')} | POC={r.get('POC')} | "
                    f"满足{r.get('主升浪满足')}/8 | {r.get('主升浪综合判断')}\n")
        f.write("\n【VAP-ATR突破股票】\n")
        for r in breakout_stocks[:top_n]:
            f.write(f"  {r.get('股票名称', '')} ({r.get('股票代码')}): "
                    f"POC={r.get('POC')} 上轨={r.get('自适应上轨')}\n")

    # CSV 明细
    csv_path = os.path.join(output_dir, f'市场扫描明细_{timestamp}.csv')
    results_df.to_csv(csv_path, index=False, encoding='utf-8-sig')

    elapsed = time.time() - start_time
    stats = engine.stats()
    engine.close()

    logger.info(f"✅ 扫描完成! 耗时{elapsed:.1f}秒")
    logger.info(f"📦 数据库: {stats}")
    return {
        '扫描数': len(results),
        '含信号': len(signal_stocks),
        'VAP-ATR突破': len(breakout_stocks),
        '报告': txt_path,
        '明细': csv_path,
        '耗时': round(elapsed, 1),
        'stats': stats,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='全市场自适应扫描分析')
    parser.add_argument('--limit', type=int, default=None, help='扫描数量限制')
    parser.add_argument('--period', choices=['daily', 'weekly', 'monthly'],
                        default='daily', help='K线周期')
    parser.add_argument('--sync', action='store_true', help='先同步数据再扫描')
    parser.add_argument('--top', type=int, default=20, help='报告Top N')
    args = parser.parse_args()

    result = run_market_scan(limit=args.limit, period=args.period,
                             sync_first=args.sync, top_n=args.top)
    print(f"\n📊 扫描结果: {result}")
