#!/usr/bin/env python3
# 3_🔍_全市场扫描.py - 全市场扫描页面（docs/ui.md §4.3）
"""参数设置 → 扫描股票池 → 进度条 → 结果表格（真三振高亮/CSV导出）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..', 'data'))

import streamlit as st
from datetime import date

st.set_page_config(page_title="全市场扫描", page_icon="🔍", layout="wide")

import pandas as pd

from web.utils.session import get_feeder, get_logic, get_config, \
    save_scan_results
from web.components.stock_table import render_stock_table

st.title("🔍 全市场扫描")
st.caption("扫描股票池，筛选真三振 / 主升浪信号（结果自动保存到真三振池）")

cfg = get_config()
stock_pool = cfg.get('stocks', [])


def _get_all_a_shares():
    """获取全部A股列表（缓存中有行情的股票）"""
    from data.db_manager import MysteryDB
    db = MysteryDB()
    codes = db.get_cached_tickers('daily')
    if codes:
        return [c.replace('.', '') for c in codes]  # sh.600150 -> sh600150
    st.warning("数据库无行情缓存，请先运行 sync_all_market.py")
    return []


def _run_scan(codes):
    """执行扫描循环（提取为函数，供缓存复用）"""
    feeder = get_feeder()
    logic = get_logic()
    results = []
    total = len(codes)
    progress = st.progress(0.0, text="扫描中...")
    status = st.empty()
    # 大盘数据只取一次
    market_data = feeder.get_market_index()
    for i, code in enumerate(codes):
        try:
            status.info(f"⏳ 扫描 {i+1}/{total}: {code}")
            daily = feeder.get_daily(code)
            if daily is None or daily.empty:
                continue
            weekly = feeder.get_weekly(code)
            signal = logic.comprehensive_signal_analysis(
                daily, weekly_data=weekly, market_data=market_data,
                industry_data=None, industry_trend=None)
            name = code
            try:
                from data.baostock_client import BaostockClient
                name = BaostockClient().get_stock_name(code)
            except Exception:
                pass
            # 行业板块（docs/ui2.md 扫描结果显示板块）
            industry = ''
            try:
                db_code = code[:2] + '.' + code[2:] if '.' not in code else code
                ind_map = feeder.get_industry_data()
                industry = ind_map.get('code_map', {}).get(db_code, '')
            except Exception:
                pass
            results.append({
                '股票代码': code, '股票名称': name, '行业板块': industry,
                '综合评分': signal.get('综合评分', 0),
                '真三振': signal.get('真三振', False),
                '主升浪信号': signal.get('主升浪信号', False),
                '资金活跃': signal.get('资金活跃', False),
                '共振级别': signal.get('共振级别', '无共振'),
                '操作建议': signal.get('操作建议', '观望'),
            })
        except Exception as e:
            st.warning(f"⚠️ {code} 分析失败: {str(e)[:60]}")
        progress.progress((i + 1) / total,
                          text=f"扫描 {i+1}/{total}: {code}")
    progress.empty()
    status.empty()
    return results


# ---------- 参数 ----------
with st.sidebar:
    st.subheader("⚙️ 扫描参数")
    only_true = st.checkbox("只看真三振", value=False)
    only_main = st.checkbox("只看主升浪", value=False)
    min_score = st.slider("评分阈值", 0, 100, 85)
    # 股票池选择器（docs/ui2.md 全局股票池 + 指定板块）
    from web.utils.session import load_watchlist
    watchlist = load_watchlist()
    pool_options = ["全市场A股", "核心自选池"] + \
        (["自定义"] if watchlist else [])
    scope = st.radio("扫描范围", pool_options)
    st.caption(f"自选股 {len(watchlist)} 只")
    if scope == "全市场A股":
        selected = None
    elif scope == "核心自选池":
        selected = watchlist if watchlist else None
        if not watchlist:
            st.warning("自选股为空，请先在「真三振池」页添加")
    else:
        selected = st.multiselect("选择股票", stock_pool, default=stock_pool[:5])
    # 指定板块筛选（docs/ui2.md: 通达信行业板块）
    try:
        ind_map = get_feeder().get_industry_data()
        ind_codes = ind_map.get('industry_codes', {})
        industry_names = list(ind_codes.keys())
    except Exception:
        ind_codes, industry_names = {}, []
    if industry_names:
        sel_industry = st.selectbox("指定板块（可选，按行业板块筛选）",
                                    ["全部板块"] + industry_names)
        if sel_industry != "全部板块":
            selected = [c.replace('.', '') for c in ind_codes[sel_industry]]
            st.caption(f"📊 已指定板块: {sel_industry} "
                       f"（{len(selected)} 只成分股）")
    else:
        st.caption("行业板块数据不可用（可先打开板块监控页触发填充）")
    # 后台扫描参数（docs/081601.md §四: 后台运行 + 使能三振/主升浪）
    st.subheader("🖥️ 后台扫描")
    bg_enable_3z = st.checkbox("使能三振分析", value=True)
    bg_enable_mw = st.checkbox("使能主升浪", value=True)
    if st.button("🚀 提交后台扫描", type="primary", width="stretch"):
        from data.run_market_scan import run_market_scan_background
        bg_codes = selected if selected is not None else None
        limit = len(bg_codes) if bg_codes else None
        job_id = run_market_scan_background(
            limit=limit, period='daily', sync_first=False, top_n=20,
            enable_three_strike=bg_enable_3z,
            enable_main_wave=bg_enable_mw)
        st.session_state['scan_job_id'] = job_id
        st.success(f"🚀 后台任务已提交: {job_id}（可在下方查看进度，"
                   f"或到 ⚙️ 系统状态页查看）")

# ===== 后台任务状态轮询（docs/081601.md §四 + 独立库 scan_results.db） =====
if 'scan_job_id' in st.session_state:
    st.divider()
    st.subheader("🖥️ 后台扫描任务")
    from data.scan_store import ScanStore
    job_id = st.session_state['scan_job_id']
    try:
        job = ScanStore().get_job(job_id)
    except Exception:
        job = None
    if job:
        status = job['status']
        st.progress(job['progress'] or 0,
                    text=f"状态: {status} | {job.get('message', '')}")
        st.caption(f"任务ID: {job_id} | 提交时间: {job['start_time']} "
                   f"| 交易日: {job.get('trade_date', '')}")
        if status == 'finished':
            st.success("✅ 扫描完成")
            if job.get('summary', {}).get('缓存命中'):
                st.info(f"⚡ 本次命中缓存：行情交易日 "
                        f"{job.get('trade_date')} 未更新，复用源任务 "
                        f"{job['summary'].get('源任务')} 的结果，未重新扫描")
            df = ScanStore().results_df(job_id)
            if not df.empty:
                st.dataframe(df, width="stretch")
                st.download_button("⬇️ 下载明细 CSV", df.to_csv(
                    index=False).encode('utf-8-sig'),
                    file_name=f"scan_{job_id}.csv", mime="text/csv")
            else:
                st.info("该任务无结果明细")
            st.session_state.pop('scan_job_id', None)
        elif status == 'failed':
            st.error(f"❌ 任务失败: {job.get('message', '')}")
            st.session_state.pop('scan_job_id', None)
        else:
            st.info("⏳ 后台扫描运行中... 点击任意位置自动刷新，"
                    "或等待完成后展示结果")

# ===== 扫描任务历史 + 结果查看入口（独立库 scan_results.db） =====
st.divider()
st.subheader("📚 扫描任务历史")
st.caption("全市场扫描结果独立存储于 scan_results.db；"
           "行情（最新交易日）未更新时，同参数扫描直接命中缓存不重复执行")
try:
    from data.scan_store import ScanStore
    _store = ScanStore()
    jobs = _store.list_jobs(20)
    if not jobs:
        st.info("暂无扫描任务记录（提交后台扫描或运行 run_market_scan.py 后出现）")
    else:
        job_rows = []
        for j in jobs:
            s = j.get('summary', {})
            job_rows.append({
                '任务ID': j['job_id'],
                '状态': {'finished': '✅ 完成', 'running': '⏳ 运行中',
                        'failed': '❌ 失败'}.get(j['status'], j['status']),
                '交易日': j.get('trade_date', ''),
                '扫描数': s.get('扫描数', j.get('result_count', 0)),
                '含信号': s.get('含信号', ''),
                '真三振': s.get('真三振数', ''),
                '耗时(s)': s.get('耗时', ''),
                '提交时间': (j.get('start_time') or '')[:19],
                '摘要': (j.get('message') or '')[:40],
            })
        st.dataframe(pd.DataFrame(job_rows), width="stretch")
        # 选择历史任务查看结果
        sel_job = st.selectbox(
            "查看历史任务结果", [j['job_id'] for j in jobs],
            format_func=lambda jid: next(
                (f"{j['job_id']} [{j['status']}] {j.get('trade_date', '')} "
                 f"- {(j.get('message') or '')[:30]}"
                 for j in jobs if j['job_id'] == jid), jid))
        if sel_job:
            hist_df = _store.results_df(sel_job)
            if hist_df.empty:
                st.info(f"任务 {sel_job} 暂无结果明细")
            else:
                st.caption(f"📊 任务 {sel_job} 结果明细 "
                           f"（{len(hist_df)} 只）")
                st.dataframe(hist_df, width="stretch")
                st.download_button("⬇️ 下载该任务明细 CSV", hist_df.to_csv(
                    index=False).encode('utf-8-sig'),
                    file_name=f"scan_{sel_job}.csv", mime="text/csv")
except Exception as e:
    st.warning(f"⚠️ 扫描任务历史读取失败: {e}")

if st.button("🚀 开始扫描", type="primary", width="stretch"):
    if scope == "核心自选池" and not (watchlist or selected):
        st.warning("自选股为空，请先添加")
        st.stop()
    codes = selected if selected is not None else _get_all_a_shares()
    if not codes:
        st.warning("无可扫描的股票")
        st.stop()

    # ===== 扫描结果缓存（docs/ui2.md: 行情未更新不重复扫描） =====
    # 缓存键用最新交易日（而非自然日）：行情不更新时周末/同日重复扫描直接复用
    from db_manager import MysteryDB
    db = MysteryDB()
    from data.scan_store import ScanStore
    scan_key = ScanStore.get_market_trade_date() or str(date.today())
    cached_scan = db.get_analysis_cache('__all__', 'full_scan', scan_key)
    if cached_scan and cached_scan.get('results'):
        st.success(f"⚡ 命中今日扫描缓存（{scan_key}，{len(cached_scan['results'])} 只）")
        results = cached_scan['results']
    else:
        results = _run_scan(codes)
        db.set_analysis_cache('__all__', 'full_scan', scan_key,
                              {'results': results, 'date': scan_key,
                               'scope': scope})

    # 过滤
    if only_true:
        results = [r for r in results if r['真三振']]
    if only_main:
        results = [r for r in results if r['主升浪信号']]
    results = [r for r in results if r['综合评分'] >= min_score]
    results.sort(key=lambda r: r['综合评分'], reverse=True)

    save_scan_results(results)
    st.success(f"✅ 扫描完成: {len(results)} 只符合条件（共 {len(codes)} 只）")
    st.session_state['scan_results'] = results
    render_stock_table(results)
    st.info("💎 结果已保存，可在「真三振池」页面查看；"
            "也可在「个股分析」页面对单只股票做深度分析")
