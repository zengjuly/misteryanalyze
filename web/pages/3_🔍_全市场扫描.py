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

st.set_page_config(page_title="全市场扫描", page_icon="🔍", layout="wide")

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
            results.append({
                '股票代码': code, '股票名称': name,
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
    # 股票池选择器（docs/ui2.md 全局股票池）
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

if st.button("🚀 开始扫描", type="primary", use_container_width=True):
    if scope == "核心自选池" and not (watchlist or selected):
        st.warning("自选股为空，请先添加")
        st.stop()
    codes = selected if selected is not None else _get_all_a_shares()
    if not codes:
        st.warning("无可扫描的股票")
        st.stop()

    # ===== 扫描结果缓存（docs/ui2.md: 行情未更新不重复扫描） =====
    from db_manager import MysteryDB
    db = MysteryDB()
    from datetime import date
    scan_key = str(date.today())
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
