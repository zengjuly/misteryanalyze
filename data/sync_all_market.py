#!/usr/bin/env python3
# sync_all_market.py - 全量A股自动化并行拉取与数据洗盘（基于docs/gemmi_an.md数据中枢方案）
"""
全市场数据同步脚本
==================
理论来源: docs/gemmi_an.md（数据中枢与全量自动化分析方案）

功能:
  1. 动态获取市场所有股票列表（get_all_a_shares，含行业分类补充）
  2. 多线程并行同步日/周/月线行情至本地 SQLite 缓存
  3. 增量更新（仅拉取最近 N 天，safe_upsert 覆盖写入）
  4. 财务数据快照同步

用法:
  python sync_all_market.py                # 全量同步（默认最近1100天日线）
  python sync_all_market.py --period daily # 指定周期
  python sync_all_market.py --limit 500    # 仅同步前500只（测试用）
  python sync_all_market.py --threads 8    # 8线程
  python sync_all_market.py --days 365     # 仅最近365天（每日增量）
"""

import argparse
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_engine import MysteryDataEngine, DEFAULT_LOOKBACK_DAYS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S')
logger = logging.getLogger('sync_all_market')


def get_all_a_shares(engine: MysteryDataEngine, include_index: bool = False) -> list:
    """
    动态获取市场所有A股代码列表
    :param engine: 数据引擎
    :param include_index: 是否包含指数
    :return: 股票代码列表（9位格式 sh.600150）
    """
    # 同步全市场证券列表到缓存
    n = engine.sync_stock_list(include_index=include_index)
    if n == 0:
        logger.error("❌ 证券列表同步失败")
        return []

    # 从缓存读取股票列表
    df = engine.db.get_stock_info(stock_only=not include_index, listed_only=True)
    codes = df['code'].tolist() if not df.empty else []
    logger.info(f"📋 获取全市场股票 {len(codes)} 只")
    return codes


def sync_worker(engine: MysteryDataEngine, code: str, periods: list,
                days: int, progress: dict, lock: threading.Lock,
                retry: int = 3, delay: float = 0.5) -> int:
    """
    单只股票同步工作线程
    :return: 成功同步的K线行数
    """
    total_rows = 0
    for attempt in range(retry):
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            for period in periods:
                df = engine.get_kline(
                    code, period,
                    start_date=start.strftime('%Y-%m-%d'),
                    end_date=end.strftime('%Y-%m-%d'),
                    force_refresh=True)  # 强制刷新（增量覆盖）
                if df is not None and not df.empty:
                    total_rows += len(df)
            with lock:
                progress['ok'] += 1
            return total_rows
        except Exception as e:
            # 网络解码错误（'utf-8' codec can't decode）或连接异常 → 重试
            err_str = str(e)
            if any(k in err_str for k in ['codec', 'decode', '接收', '网络', 'socket',
                                          'Connection', 'connection', 'timed out']):
                time.sleep(delay * (attempt + 1))  # 退避重试
            else:
                time.sleep(delay)
            if attempt < retry - 1:
                continue
            with lock:
                progress['fail'] += 1
            logger.warning(f"⚠️ {code} 同步失败(重试{retry}次): {err_str[:120]}")
    return total_rows


def sync_all_market(periods: list = None, days: int = None,
                    threads: int = 1, limit: int = None,
                    include_index: bool = False) -> dict:
    """
    全量同步主函数
    :param periods: 周期列表 ['daily','weekly','monthly']
    :param days: 回溯天数
    :param threads: 线程数（⚠️ baostock为全局单socket连接，多线程并发会导致
                    utf-8解码错误/数据交错，默认1=串行最稳定；2-4为折中）
    :param limit: 仅同步前N只（测试用）
    :param include_index: 是否包含指数
    """
    start_time = time.time()
    engine = MysteryDataEngine()
    if periods is None:
        periods = ['daily']
    if days is None:
        days = DEFAULT_LOOKBACK_DAYS.get(periods[0], 1100)

    # 1. 获取全市场股票
    codes = get_all_a_shares(engine, include_index=include_index)
    if limit:
        codes = codes[:limit]
        logger.info(f"🔒 测试模式: 仅同步前 {limit} 只")

    progress = {'ok': 0, 'fail': 0}
    lock = threading.Lock()

    # 2. 多线程并行同步
    logger.info(f"🚀 开始多线程同步: {len(codes)} 只 × {periods} 周期, "
                f"{threads} 线程, 回溯{days}天")
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {
            executor.submit(sync_worker, engine, code, periods, days, progress, lock)
            for code in codes
        }
        done = 0
        total = len(futures)
        for _ in as_completed(futures):
            done += 1
            if done % 200 == 0 or done == total:
                logger.info(f"⏳ 进度: {done}/{total} "
                            f"(成功{progress['ok']} 失败{progress['fail']})")

    # 3. 汇总
    elapsed = time.time() - start_time
    stats = engine.stats()
    logger.info(f"✅ 全量同步完成! 耗时{elapsed:.1f}秒, "
                f"成功{progress['ok']} 失败{progress['fail']}")
    logger.info(f"📦 数据库: {stats}")
    engine.close()
    return {**progress, 'elapsed': round(elapsed, 1), 'stats': stats}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='全市场数据同步到本地缓存')
    parser.add_argument('--period', choices=['daily', 'weekly', 'monthly'],
                        default='daily', help='同步周期')
    parser.add_argument('--days', type=int, default=None, help='回溯天数')
    parser.add_argument('--threads', type=int, default=1,
                        help='线程数(baostock单连接,默认1串行最稳定;2-4折中)')
    parser.add_argument('--limit', type=int, default=None, help='仅同步前N只(测试)')
    parser.add_argument('--index', action='store_true', help='包含指数')
    args = parser.parse_args()

    result = sync_all_market(
        periods=[args.period],
        days=args.days,
        threads=args.threads,
        limit=args.limit,
        include_index=args.index,
    )
    print(f"\n📊 同步结果: {result}")
