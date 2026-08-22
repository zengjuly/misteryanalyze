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
                      period: str = 'daily',
                      enable_three_strike: bool = True,
                      enable_main_wave: bool = True,
                      market_data: dict = None,
                      sector_map: dict = None,
                      ind_map: dict = None,
                      sys_obj=None,
                      latest: bool = False) -> dict:
    """
    扫描单只股票：自适应窗口 + VAP-ATR + 主升浪指标 + 三振共振 + 信号捕获
    :param engine: 数据引擎
    :param code: 股票代码
    :param enable_three_strike: 使能三振共振（docs/081601.md）
    :param enable_main_wave: 使能主升浪8项
    :param market_data: 大盘指数 {指数名: df}（扫描前置构建一次）
    :param sector_map: 板块得分 {板块名: 得分}（扫描前置构建一次）
    :param ind_map: 行业归属 {code: 行业名}（扫描前置构建一次）
    :param sys_obj: StockAnalysisSystem 实例（循环外构造一次，避免每只重建）
    :param latest: 强制最新行情（2026-08-17 用户需求）：绕过本地缓存直读
        MarketDataClient（内部 stale 判断：缓存已最新→毫秒级返回；落后→
        在线源拉最新交易日）。板块/自选股等小范围扫描启用，全市场默认 False
    :return: 分析结果字典
    """
    from main import StockAnalysisSystem

    try:
        # 从本地缓存加载行情（Cache-Aside：未命中自动回填）；
        # latest=True 时强制走 fetch_daily 的 stale 回退（最新行情）
        kline = engine.get_kline(code, period, force_refresh=latest)
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

        # 技术指标（轻量管线: MA + MACD + 量比 足够主升浪/三振/筹码/平台使用）
        # 完整 _calculate_all_indicators 每只 50s+（含量价/动量全管线），
        # 全市场扫描不可行 → 用轻量指标（docs/081601.md 扫描性能）
        from indicators.ma_indicators import MAIndicators
        from indicators.trend_indicators import TrendIndicators
        from indicators.momentum_indicators import MomentumIndicators
        indicators = MAIndicators().calculate_ma(df)
        indicators = TrendIndicators().calculate_macd(indicators)
        # 量比（technical_detail_capture 筹码/量比指标需要，缺失会抛 '量比' 异常）
        indicators = MomentumIndicators().calculate_volume_ratio(indicators)

        # 自适应 VAP-ATR 平台（扫描需全序列 → latest_only=False，docs/082207.md）
        from analysis.adaptive_platform import analyze_adaptive_platform
        platform = analyze_adaptive_platform(indicators, code,
                                             latest_only=False)

        # 主升浪8项指标（docs/081601.md: 使能主升浪）
        from analysis.mystery_logic import MysteryLogic
        ml = MysteryLogic()
        checklist = {'满足数量': 0, '综合判断': '未知', '详情': []}
        if enable_main_wave:
            checklist = ml.main_bull_wave_checklist(indicators,
                                                    industry_trend=None)

        # 三振共振四维分析（docs/081601.md: 使能三振；行业趋势用板块得分）
        three = {}
        if enable_three_strike:
            try:
                industry_trend = None
                if sector_map:
                    # 该股所属行业板块得分 > 0 视为行业向好（ind_map 前置构建）
                    ind_name = (ind_map or {}).get(
                        code if '.' in code else (code[:2] + '.' + code[2:]))
                    if ind_name and ind_name in sector_map:
                        industry_trend = sector_map[ind_name] > 0
                three = ml.three_resonance_analysis(
                    indicators, market_data=market_data,
                    industry_data=None, industry_trend=industry_trend)
            except Exception as e:
                logger.debug(f"{code} 三振分析降级: {str(e)[:60]}")

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
        # 三振结果（docs/081601.md: 扫描结果显示真三振/评分/级别）
        if three:
            result['三振评分'] = three.get('共振评分')
            result['真三振'] = three.get('真三振')
            result['三振级别'] = three.get('共振级别')
            result['综合评分'] = three.get('共振评分') or 0
        # 与个股分析一致的字段（设计原则 2026-08-17: 板块/扫描每只股票
        # 内容与个股分析保持一致——补 共振级别/操作建议/主升浪信号/资金活跃）
        if three.get('共振级别'):
            result['共振级别'] = three.get('共振级别')
        if three.get('共振建议') is not None:
            result['操作建议'] = three.get('共振建议')
        if three.get('主升浪信号') is not None:
            result['主升浪信号'] = three.get('主升浪信号')
        if three.get('资金活跃') is not None:
            result['资金活跃'] = three.get('资金活跃')
        return result
    except Exception as e:
        logger.warning(f"⚠️ {code} 扫描异常: {e}")
        return {'股票代码': code, '综合评分': 0, '信号': '异常'}


def _resolve_output_dir(output_dir: str = None) -> str:
    """解析输出目录（None → config 中的 output_dir）"""
    if output_dir:
        return output_dir
    from main import StockAnalysisSystem
    sys_tmp = StockAnalysisSystem('config/config.yaml')
    return sys_tmp.config.get('output_dir', 'output')


def _write_scan_reports(results: list, output_dir: str,
                        summary: dict = None, tag: str = None) -> tuple:
    """生成 文本汇总 + CSV 明细 + Excel 明细（独立库命中/正常扫描共用）
    :return: (csv_path, txt_path, xlsx_path)
    """
    results_df = pd.DataFrame(results)
    output_dir = _resolve_output_dir(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    signal_stocks = [r for r in results if r.get('信号') and r['信号'] != '无']
    breakout_stocks = [r for r in results if r.get('突破信号')]
    true_three = [r for r in results if r.get('真三振')]

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = f'_{tag}' if tag else ''
    # 文本汇总
    txt_path = os.path.join(output_dir, f'市场扫描报告_{timestamp}{suffix}.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"=== 全市场扫描报告 {datetime.now()} ===\n")
        f.write(f"扫描股票数: {len(results)} | 含信号: {len(signal_stocks)} "
                f"| VAP-ATR突破: {len(breakout_stocks)}\n\n")
        f.write("【信号股票 Top】\n")
        for r in signal_stocks[:20]:
            f.write(f"  {r.get('股票名称', '')} ({r.get('股票代码')}): "
                    f"{r.get('信号')} | POC={r.get('POC')} | "
                    f"满足{r.get('主升浪满足')}/8 | {r.get('主升浪综合判断')}\n")
        f.write("\n【VAP-ATR突破股票】\n")
        for r in breakout_stocks[:20]:
            f.write(f"  {r.get('股票名称', '')} ({r.get('股票代码')}): "
                    f"POC={r.get('POC')} 上轨={r.get('自适应上轨')}\n")

    # CSV 明细
    csv_path = os.path.join(output_dir, f'市场扫描明细_{timestamp}{suffix}.csv')
    results_df.to_csv(csv_path, index=False, encoding='utf-8-sig')

    # Excel 明细（多 sheet: 汇总 / 全部明细 / 信号股票 / 真三振）
    xlsx_path = os.path.join(output_dir, f'市场扫描明细_{timestamp}{suffix}.xlsx')
    try:
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            summary_df = pd.DataFrame([{
                '扫描时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '扫描股票数': len(results),
                '含信号': len(signal_stocks),
                'VAP-ATR突破': len(breakout_stocks),
                '真三振': len(true_three),
                '信号股票数': len(signal_stocks),
            }])
            summary_df.to_excel(writer, sheet_name='汇总', index=False)
            results_df.to_excel(writer, sheet_name='全部明细', index=False)
            if signal_stocks:
                pd.DataFrame(signal_stocks).to_excel(
                    writer, sheet_name='信号股票', index=False)
            if true_three:
                pd.DataFrame(true_three).to_excel(
                    writer, sheet_name='真三振', index=False)
        logger.info(f"📊 Excel明细已生成: {os.path.basename(xlsx_path)}")
    except Exception as e:
        logger.warning(f"⚠️ Excel生成失败（不影响CSV/TXT）: {e}")
        xlsx_path = ''

    return csv_path, txt_path, xlsx_path


def _sync_scan_reports_to_git(output_dir: str, *report_paths) -> bool:
    """将扫描报告同步到输出目录git仓库并推送远端（与 main.py 同步逻辑一致）"""
    import subprocess as sp
    output_dir = _resolve_output_dir(output_dir)
    try:
        check = sp.run(['git', '-C', output_dir, 'rev-parse',
                        '--is-inside-work-tree'],
                       capture_output=True, text=True, timeout=30)
        if check.returncode != 0:
            logger.warning(f"⚠️ {output_dir} 不是git仓库，跳过git同步")
            return False
        remote = sp.run(['git', '-C', output_dir, 'remote'],
                        capture_output=True, text=True, timeout=30)
        has_remote = bool(remote.stdout.strip())
        paths = [os.path.basename(p) for p in report_paths if p]
        if paths:
            sp.run(['git', '-C', output_dir, 'add', '--'] + paths,
                   capture_output=True, text=True, timeout=30)
        else:
            sp.run(['git', '-C', output_dir, 'add', '-A'],
                   capture_output=True, text=True, timeout=30)
        status = sp.run(['git', '-C', output_dir, 'status', '--porcelain'],
                        capture_output=True, text=True, timeout=30)
        if not status.stdout.strip():
            logger.info("📦 输出目录无新变更，跳过提交")
            return True
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_msg = f"📊 全市场扫描报告更新 {timestamp}"
        commit = sp.run(['git', '-C', output_dir, 'commit', '-m', commit_msg],
                        capture_output=True, text=True, timeout=60)
        if commit.returncode != 0:
            logger.error(f"❌ git提交失败: {commit.stderr.strip()}")
            return False
        logger.info(f"✅ git提交成功: {commit_msg}")
        if has_remote:
            push = sp.run(['git', '-C', output_dir, 'push'],
                          capture_output=True, text=True, timeout=120)
            if push.returncode == 0:
                logger.info("🚀 git推送远端成功")
            else:
                logger.warning(f"⚠️ git推送远端失败: {push.stderr.strip()[:200]}")
        return True
    except Exception as e:
        logger.error(f"❌ git同步异常: {e}")
        return False


def run_market_scan(limit: int = None, period: str = 'daily',
                    sync_first: bool = False, top_n: int = 20,
                    output_dir: str = None,
                    enable_three_strike: bool = True,
                    enable_main_wave: bool = True,
                    use_cache: bool = True,
                    job_id: str = None,
                    progress_cb=None,
                    codes: list = None,
                    scope_name: str = '',
                    latest: bool = False) -> dict:
    """
    全量扫描分析主函数
    :param limit: 扫描股票数量限制（与 codes 互斥，None 时扫描全市场）
    :param period: K线周期
    :param sync_first: 是否先同步数据
    :param top_n: 生成报告的Top N（按信号数/评分排序）
    :param output_dir: 输出目录（默认config中的output_dir）
    :param enable_three_strike: 使能三振共振分析（docs/081601.md 用户要求）
    :param enable_main_wave: 使能主升浪8项分析
    :param use_cache: 缓存复用（同参数+同最新交易日 → 直接返回上次结果，
        行情不更新不需要重复执行）
    :param job_id: 后台任务ID（run_market_scan_background 传入；前台自动创建）
    :param progress_cb: 进度回调 fn(progress: float, message: str)
    :param codes: 显式扫描股票列表（板块成分股/自选股，2026-08-17 用户需求：
        市场扫描支持按板块或自选股扫描；传入后忽略 limit 截断）
    :param scope_name: 扫描范围名称（板块名/自选股，报告与任务备注用）
    :param latest: 使用最新行情（stale 回退在线源，小范围扫描建议开启）
    """
    from data.scan_store import ScanStore
    store = ScanStore()
    # 显式股票列表（板块/自选股）也参与缓存键区分（2026-08-17 用户需求）
    codes_sig = None
    if codes is not None:
        codes_sig = '|'.join(sorted(codes))
    params = {
        'period': period, 'limit': limit, 'sync_first': sync_first,
        'top_n': top_n, 'enable_three_strike': enable_three_strike,
        'enable_main_wave': enable_main_wave,
        'scope_name': scope_name,
        'codes': codes_sig,
    }
    trade_date = store.get_market_trade_date()

    # ===== 缓存命中：行情未更新 → 直接复用上次扫描结果 =====
    if use_cache:
        cached = store.find_cache(params, trade_date)
        if cached:
            elapsed = 0.0
            results = cached['results']
            logger.info(f"⚡ 缓存命中（交易日 {trade_date} 未更新，"
                        f"任务 {cached['job_id']} 复用）: {len(results)} 只")
            # 重新生成 CSV/Excel/报告（结果仍落在 output 目录，保持既有习惯）
            csv_path, txt_path, xlsx_path = _write_scan_reports(
                results, output_dir, cached['summary'], cached['job_id'])
            if job_id:
                store.finish_job(
                    job_id, 'finished',
                    summary={**cached['summary'], '缓存命中': True,
                             '源任务': cached['job_id']},
                    message=f"⚡ 缓存命中（行情未更新），复用任务 "
                            f"{cached['job_id']} 的 {len(results)} 只结果")
            # 同步到 output git 仓库（Excel/CSV/TXT 一并推送远端）
            _sync_scan_reports_to_git(
                output_dir, xlsx_path, csv_path, txt_path)
            return {
                '扫描数': len(results),
                '含信号': len([r for r in results if r.get('信号')
                               and r['信号'] != '无']),
                'VAP-ATR突破': len([r for r in results
                                    if r.get('突破信号')]),
                '真三振数': len([r for r in results if r.get('真三振')]),
                '报告': txt_path,
                '明细': csv_path,
                'Excel': xlsx_path,
                '耗时': 0.0,
                '缓存命中': True,
                'job_id': cached['job_id'],
                'results': results,
                'stats': store.stats(),
            }

    start_time = time.time()
    engine = MysteryDataEngine()

    # 创建任务记录（后台任务已建，前台自动建）
    if job_id is None:
        job_id = store.create_job(params, trade_date)

    # 1. 扫描范围: 显式 codes（板块/自选股）优先，否则全市场缓存列表
    if codes is not None:
        codes = list(codes)
        logger.info(f"🎯 扫描范围: {scope_name or '自定义'} {len(codes)} 只")
    else:
        codes = load_local_cached_tickers(engine, period, limit=limit,
                                          force_sync=sync_first)

    # 1.5 三振前置数据（一次性构建，docs/081601.md: 使能三振）
    market_data = {}
    sector_map = {}
    ind_map = {}
    if enable_three_strike:
        try:
            import yaml
            from utils.data_feeder import DataFeeder
            cfg = yaml.safe_load(open(os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', 'config', 'config.yaml')))
            feeder = DataFeeder(cfg)
            market_data = feeder.get_market_index()
            ind_map = feeder.get_industry_data().get('code_map', {})
            # 板块强度（db行业分类 + 缓存K线）→ 个股行业趋势判定
            from web.pages_util import build_sector_strength_map
            sector_map = build_sector_strength_map()
            logger.info(f"🧭 三振前置: 指数 {list(market_data.keys())}, "
                        f"行业归属 {len(ind_map)} 只, "
                        f"板块强度 {len(sector_map)} 个")
        except Exception as e:
            logger.warning(f"⚠️ 三振前置数据构建失败（三振降级）: {e}")

    # 2. 逐只扫描（单线程，避免baostock并发问题；轻量指标每只 <1s）
    logger.info(f"🔍 开始全量扫描 {len(codes)} 只股票...")
    results = []
    total = len(codes)
    for i, code in enumerate(codes, 1):
        r = scan_single_stock(engine, code, period,
                              enable_three_strike=enable_three_strike,
                              enable_main_wave=enable_main_wave,
                              market_data=market_data,
                              sector_map=sector_map,
                              ind_map=ind_map,
                              latest=latest)
        results.append(r)
        if i % 100 == 0 or i == total:
            logger.info(f"⏳ 扫描进度: {i}/{total}")
        # 进度上报（后台任务/Web 轮询用）
        if i % 200 == 0 or i == total:
            store.update_job(job_id, progress=round(i / total, 3),
                             message=f"扫描 {i}/{total}")
            store.save_results(job_id, results)
            if progress_cb:
                progress_cb(round(i / total, 3), f"扫描 {i}/{total}")

    # 3. 补充股票名称（从缓存证券信息表）
    info_df = engine.db.get_stock_info(stock_only=True)
    name_map = dict(zip(info_df['code'], info_df['code_name'])) if not info_df.empty else {}
    # 兼容带点/无点格式（板块/自选股 codes 传无点，db 存带点）
    name_map.update({k.replace('.', ''): v for k, v in name_map.items()})
    for r in results:
        if '股票代码' in r:
            r['股票名称'] = name_map.get(r['股票代码'], r['股票代码'])

    # 3.5 写独立库（结果存储 + 缓存源）
    try:
        store.save_results(job_id, results, trade_date)
        logger.info(f"🗄️ 扫描结果已写入独立库 {store.db_path} "
                    f"（{len(results)} 只）")
    except Exception as e:
        logger.warning(f"⚠️ 扫描结果写库失败: {e}")

    # 4. 信号统计
    signal_stocks = [r for r in results if r.get('信号') and r['信号'] != '无']
    breakout_stocks = [r for r in results if r.get('突破信号')]
    logger.info(f"🎯 信号统计: 总扫描{len(results)}, "
                f"含信号{len(signal_stocks)}, VAP-ATR突破{len(breakout_stocks)}")

    # 5. 生成报告（文本汇总 + CSV 明细）
    results_df = pd.DataFrame(results)
    if results_df.empty:
        logger.warning("⚠️ 无扫描结果")
        store.finish_job(job_id, 'failed', summary={'扫描数': 0},
                         message='无扫描结果')
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

    csv_path, txt_path, xlsx_path = _write_scan_reports(
        results, output_dir, tag=job_id)

    elapsed = time.time() - start_time
    stats = engine.stats()
    engine.close()

    summary = {
        '扫描数': len(results),
        '含信号': len(signal_stocks),
        'VAP-ATR突破': len(breakout_stocks),
        '真三振数': len([r for r in results if r.get('真三振')]),
        '耗时': round(elapsed, 1),
    }
    store.finish_job(
        job_id, 'finished', summary=summary,
        message=f"完成: 扫描{len(results)}只, 信号{len(signal_stocks)}, "
                f"真三振{summary['真三振数']}, 耗时{elapsed:.0f}s")

    # 同步到 output git 仓库（Excel/CSV/TXT 一并推送远端）
    _sync_scan_reports_to_git(output_dir, xlsx_path, csv_path, txt_path)

    # Token 极简摘要信封（docs/082202.md 阶段三：大结果落盘，仅输出聚合摘要）
    top3 = ''
    try:
        if sector_map:
            top = sorted(sector_map.items(), key=lambda kv: kv[1],
                         reverse=True)[:3]
            top3 = '，'.join(f"{name}({round(score,1)})" for name, score in top)
    except Exception:
        pass
    print('[Mystery Scan Task Completed]')
    print(f"- 交易日期: {_latest_trade_date()} | 扫描周期: {period}")
    print(f"- 扫描全量个股数: {len(results)} 只 | 耗时: {elapsed:.1f}s")
    print(f"- 真三振（三级共振）股票池: {summary['真三振数']} 只")
    if top3:
        print(f"- 强势板块 Top 3: {top3}")
    print(f"- 详细数据已落盘至: {xlsx_path}")

    logger.info(f"✅ 扫描完成! 耗时{elapsed:.1f}秒")
    logger.info(f"📦 数据库: {stats}")
    return {
        '扫描数': len(results),
        '含信号': len(signal_stocks),
        'VAP-ATR突破': len(breakout_stocks),
        '真三振数': summary['真三振数'],
        '报告': txt_path,
        '明细': csv_path,
        'Excel': xlsx_path,
        '耗时': round(elapsed, 1),
        '缓存命中': False,
        'job_id': job_id,
        'results': results,
        'stats': stats,
        **summary,
    }


def _latest_trade_date() -> str:
    """最近交易日（sector_kline 最新日期或今天）"""
    try:
        from data.db_manager import MysteryDB
        conn = MysteryDB()._connect()
        try:
            r = conn.execute(
                "SELECT MAX(trade_date) FROM sector_kline").fetchone()
            if r and r[0]:
                return r[0]
        finally:
            conn.close()
    except Exception:
        pass
    return datetime.now().strftime('%Y-%m-%d')


def run_market_scan_background(limit: int = None, period: str = 'daily',
                               sync_first: bool = False, top_n: int = 20,
                               output_dir: str = None,
                               enable_three_strike: bool = True,
                               enable_main_wave: bool = True,
                               codes: list = None,
                               scope_name: str = '',
                               latest: bool = False) -> str:
    """后台运行全市场扫描（独立库 scan_results.db + daemon 线程）
    :param codes: 显式扫描股票列表（板块成分股/自选股，None=全市场）
    :param scope_name: 扫描范围名称（板块名/自选股，报告与任务备注用）
    :param latest: 使用最新行情（stale 回退在线源）
    :return: job_id（供 Web 页轮询）
    """
    import threading
    from data.scan_store import ScanStore

    store = ScanStore()
    params = {
        'period': period, 'limit': limit, 'sync_first': sync_first,
        'top_n': top_n, 'enable_three_strike': enable_three_strike,
        'enable_main_wave': enable_main_wave,
        'scope_name': scope_name,
        'codes': '|'.join(sorted(codes)) if codes else None,
    }
    job_id = store.create_job(params)

    def _worker():
        try:
            result = run_market_scan(
                limit=limit, period=period, sync_first=sync_first,
                top_n=top_n, output_dir=output_dir,
                enable_three_strike=enable_three_strike,
                enable_main_wave=enable_main_wave,
                use_cache=True, job_id=job_id,
                codes=codes, scope_name=scope_name, latest=latest)
        except Exception as e:
            store.finish_job(job_id, 'failed', message=str(e)[:200])
            logger.error(f"❌ 后台扫描失败 {job_id}: {e}")

    t = threading.Thread(target=_worker, daemon=True, name=f'scan-{job_id}')
    t.start()
    logger.info(f"🚀 后台扫描任务已提交: {job_id}"
                f"（范围: {scope_name or '全市场'} {len(codes) if codes else ''}只）")
    return job_id


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='全市场自适应扫描分析')
    parser.add_argument('--limit', type=int, default=None, help='扫描数量限制')
    parser.add_argument('--period', choices=['daily', 'weekly', 'monthly'],
                        default='daily', help='K线周期')
    parser.add_argument('--sync', action='store_true', help='先同步数据再扫描')
    parser.add_argument('--top', type=int, default=20, help='报告Top N')
    parser.add_argument('--no-cache', action='store_true',
                        help='忽略扫描结果缓存（行情未更新时默认复用上次结果）')
    parser.add_argument('--codes', nargs='*', default=None,
                        help='显式扫描股票列表（板块/自选股，空格分隔，如 '
                             'sh600150 sz000915）；缺省=全市场')
    parser.add_argument('--scope', default='',
                        help='扫描范围名称（板块名/自选股，写任务备注）')
    parser.add_argument('--latest', action='store_true',
                        help='使用最新行情（stale 回退在线源，小范围建议开启）')
    args = parser.parse_args()

    result = run_market_scan(limit=args.limit, period=args.period,
                             sync_first=args.sync, top_n=args.top,
                             use_cache=not args.no_cache,
                             codes=args.codes,
                             scope_name=args.scope,
                             latest=args.latest)
    # Token 极简输出（docs/082202.md 阶段三：不打印 results 全量）
    if isinstance(result, dict):
        keys = ['扫描数', '含信号', 'VAP-ATR突破', '真三振数',
                '报告', '明细', 'Excel', '耗时']
        print("📊 扫描摘要: " + " | ".join(
            f"{k}={result.get(k)}" for k in keys if k in result))
    else:
        print(f"📊 扫描结果: {result}")
