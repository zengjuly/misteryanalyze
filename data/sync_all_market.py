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
import json
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
    datefmt='%H:%M:%S',
    force=True)  # force=True: 覆盖其他模块import时设置的root handler，保证INFO可见
logger = logging.getLogger('sync_all_market')


def get_all_a_shares(engine: MysteryDataEngine, include_index: bool = False,
                     skip_sync_if_cached: bool = True) -> list:
    """
    动态获取市场所有A股代码列表
    :param engine: 数据引擎
    :param include_index: 是否包含指数
    :param skip_sync_if_cached: 本地证券列表已有足够股票时跳过网络同步
        （query_stock_basic 全市场拉取耗时30s+，缓存存在时无必要重复）
    :return: 股票代码列表（9位格式 sh.600150）
    """
    if skip_sync_if_cached:
        # 本地已有足够股票列表 → 直接使用（避免每次同步都拉全市场）
        cached = engine.db.get_stock_info(stock_only=not include_index,
                                          listed_only=True)
        if cached is not None and len(cached) >= 1000:
            codes = cached['code'].tolist()
            logger.info(f"📋 使用本地证券列表缓存 {len(codes)} 只"
                        f"（跳过网络同步）")
            return codes

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


def _load_config() -> dict:
    """加载 config.yaml（供 sync 段线程/断点配置）"""
    try:
        import yaml
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', 'config', 'config.yaml')
        with open(path, encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"⚠️ 配置加载失败({e})，使用默认值")
        return {}


def _save_checkpoint(checkpoint_file: str, done_codes: set,
                     days: int = None, periods: list = None):
    """写断点文件（docs/step3.md: 已完成股票代码列表 + 同步参数元数据）
    元数据记录 days/periods——参数变更时断点失效（避免 --days 2000 被
    --days 1100 的断点跳过，用户反馈修复）
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(checkpoint_file)),
                    exist_ok=True)
        payload = {'days': days, 'periods': periods,
                   'done': sorted(done_codes)}
        tmp = checkpoint_file + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, checkpoint_file)  # 原子替换，避免中断损坏
    except Exception as e:
        logger.warning(f"⚠️ 断点文件写入失败: {e}")


def sync_all_market(periods: list = None, days: int = None,
                    threads: int = None, limit: int = None,
                    include_index: bool = False,
                    checkpoint_file: str = None,
                    progress_bar: bool = True,
                    force: bool = False) -> dict:
    """
    全量同步主函数（断点续传 + 进度条 + 配置化线程，docs/step3.md）
    :param periods: 周期列表 ['daily','weekly','monthly']
    :param days: 回溯天数
    :param threads: 线程数（None=读取config sync.threads；⚠️ baostock为全局
                    单socket连接，多线程并发会导致解码错误，默认1=串行最稳定）
    :param limit: 仅同步前N只（测试用）
    :param include_index: 是否包含指数
    :param checkpoint_file: 断点文件路径（JSON，记录已完成股票，中断后续传；
                            含 days/periods 元数据，参数变更自动失效）
    :param progress_bar: 是否显示tqdm进度条
    :param force: 忽略断点强制全量同步（--force）
    """
    start_time = time.time()
    cfg = _load_config()
    # 关键: 必须传 config 启用双源退避（tdx_local 本地优先 + 增量路径），
    # 否则 MysteryDataEngine 无 market_client → 纯 baostock 网络拉取（全市场极慢）
    engine = MysteryDataEngine(config=cfg)
    if periods is None:
        periods = ['daily']
    if days is None:
        days = DEFAULT_LOOKBACK_DAYS.get(periods[0], 1100)

    # 配置化线程（config.yaml sync.threads，按主数据源类型）
    if threads is None:
        sync_cfg = (cfg.get('sync') or {}).get('threads') or {}
        # 主源决定线程数: tdx_local 本地读取可多线程; baostock 全局单socket必须1
        primary = 'baostock'
        if engine.market_client is not None and engine.market_client.source_order:
            primary = engine.market_client.source_order[0]
        threads = int(sync_cfg.get(primary, sync_cfg.get('baostock', 1)))
        threads = max(1, threads)
        logger.info(f"⚙️ 线程数来自配置 sync.threads.{primary} = {threads}")

    # 1. 获取全市场股票
    codes = get_all_a_shares(engine, include_index=include_index)
    if not codes:
        logger.error("❌ 获取全市场股票列表为空（ths_official/baostock 均失败或无缓存）")
        # 修复: 空列表时必须报错退出，不得误报"所有股票均已完成"
        engine.close()
        return {'ok': 0, 'fail': 0, 'skipped': 0,
                'elapsed': round(time.time() - start_time, 1),
                'error': '证券列表为空'}
    if limit:
        codes = codes[:limit]
        logger.info(f"🔒 测试模式: 仅同步前 {limit} 只")

    # 2. 断点续传：跳过已完成（docs/step3.md）
    # 参数感知（用户反馈修复）: checkpoint 带 days/periods 元数据，
    # 本次参数与断点不一致 → 断点失效全量重同步；旧格式(纯list)同样失效
    done_codes = set()
    if checkpoint_file and os.path.exists(checkpoint_file) and not force:
        try:
            with open(checkpoint_file, encoding='utf-8') as f:
                raw = json.load(f)
            if isinstance(raw, dict) and 'done' in raw:
                cp_days = raw.get('days')
                cp_periods = raw.get('periods')
                if cp_days is not None and int(cp_days) == int(days) \
                        and sorted(cp_periods or []) == sorted(periods):
                    done_codes = set(raw['done'])
                    logger.info(f"📌 断点续传: 跳过已完成的 {len(done_codes)} 只 "
                                f"(days={cp_days}, periods={cp_periods})")
                else:
                    logger.info(f"📌 断点参数不匹配(days={cp_days}≠{days} 或 "
                                f"periods={cp_periods}≠{periods}) → 全量重同步")
            else:
                logger.info(f"📌 旧格式断点(无参数元数据) → 全量重同步")
        except Exception as e:
            logger.warning(f"⚠️ 断点文件读取失败({e})，重新全量同步")
    elif force:
        logger.info("📌 --force: 忽略断点，全量同步")
    pending = [c for c in codes if c not in done_codes]
    if not pending:
        logger.info("✅ 所有股票均已完成（断点），无需同步")
        engine.close()
        return {'ok': len(done_codes), 'fail': 0, 'skipped': len(done_codes),
                'elapsed': round(time.time() - start_time, 1)}

    progress = {'ok': 0, 'fail': 0}
    lock = threading.Lock()

    # 3. 多线程并行同步（tqdm 进度条）
    logger.info(f"🚀 开始多线程同步: {len(pending)} 只待同步 × {periods} 周期, "
                f"{threads} 线程, 回溯{days}天")
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {
            executor.submit(sync_worker, engine, code, periods, days,
                            progress, lock): code
            for code in pending
        }
        total = len(futures)
        if progress_bar:
            try:
                from tqdm import tqdm
                iterator = tqdm(as_completed(futures), total=total,
                                desc='⏳ 同步进度', unit='只')
            except ImportError:
                logger.warning("⚠️ tqdm 未安装，使用日志进度")
                iterator = as_completed(futures)
        else:
            iterator = as_completed(futures)
        done = 0
        for fut in iterator:
            done += 1
            code = futures[fut]
            # 断点更新（每50只或最后一只写盘）
            if checkpoint_file:
                done_codes.add(code)
                if done % 50 == 0 or done == total:
                    _save_checkpoint(checkpoint_file, done_codes,
                                     days=days, periods=periods)
            if not progress_bar and (done % 200 == 0 or done == total):
                logger.info(f"⏳ 进度: {done}/{total} "
                            f"(成功{progress['ok']} 失败{progress['fail']})")

    # 4. 汇总（最后写一次断点，含参数元数据）
    if checkpoint_file:
        _save_checkpoint(checkpoint_file, done_codes,
                         days=days, periods=periods)
        logger.info(f"📌 断点已保存: {checkpoint_file} "
                    f"({len(done_codes)} 只完成)")
    elapsed = time.time() - start_time
    stats = engine.stats()
    logger.info(f"✅ 全量同步完成! 耗时{elapsed:.1f}秒, "
                f"成功{progress['ok']} 失败{progress['fail']}")
    logger.info(f"📦 数据库: {stats}")
    engine.close()
    return {**progress, 'elapsed': round(elapsed, 1), 'stats': stats,
            'total': total, 'skipped': len(done_codes) - len(pending)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='全市场数据同步到本地缓存')
    parser.add_argument('--period', choices=['daily', 'weekly', 'monthly'],
                        default='daily', help='同步周期')
    parser.add_argument('--days', type=int, default=None, help='回溯天数')
    parser.add_argument('--threads', type=int, default=None,
                        help='线程数(默认读config sync.threads; baostock单连接'
                             '建议1=串行最稳定,2-4折中)')
    parser.add_argument('--limit', type=int, default=None, help='仅同步前N只(测试)')
    parser.add_argument('--index', action='store_true', help='包含指数')
    parser.add_argument('--checkpoint', type=str, default=None,
                        help='断点文件路径(JSON, 中断后续传; 默认读config '
                             'sync.checkpoint_file)')
    parser.add_argument('--no-progress', action='store_true',
                        help='关闭tqdm进度条')
    parser.add_argument('--force', action='store_true',
                        help='忽略断点强制全量同步（--days 变更时断点自动失效）')
    args = parser.parse_args()

    # 断点文件：参数 > config
    checkpoint = args.checkpoint
    if checkpoint is None:
        cfg = _load_config()
        checkpoint = (cfg.get('sync') or {}).get('checkpoint_file')
        if checkpoint and not os.path.isabs(checkpoint):
            checkpoint = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), '..', checkpoint)

    result = sync_all_market(
        periods=[args.period],
        days=args.days,
        threads=args.threads,
        limit=args.limit,
        include_index=args.index,
        checkpoint_file=checkpoint,
        force=args.force,
        progress_bar=not args.no_progress,
    )
    print(f"\n📊 同步结果: {result}")
