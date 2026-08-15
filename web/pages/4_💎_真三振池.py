#!/usr/bin/env python3
# 4_💎_真三振池.py - 真三振池页面（docs/ui.md §4.4）
"""展示最近扫描产出的真三振股票列表 + 自选股管理 + 一键分析跳转"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..'))

import streamlit as st

st.set_page_config(page_title="真三振池", page_icon="💎", layout="wide")

from web.utils.session import load_scan_results, load_watchlist, \
    save_watchlist
from web.components.stock_table import render_stock_table

st.title("💎 真三振池")
st.caption("最近一次扫描产出的真三振 / 高评分股票，支持加入自选股")

tab1, tab2 = st.tabs(["💎 真三振池", "⭐ 自选股"])

with tab1:
    results = st.session_state.get('scan_results') or load_scan_results()
    if not results:
        st.info("暂无扫描结果，请先在「🔍 全市场扫描」页面运行扫描")
    else:
        # 只显示真三振/评分≥85
        pool = [r for r in results if r.get('真三振')
                or r.get('综合评分', 0) >= 85]
        st.subheader(f"符合条件的股票: {len(pool)} 只")
        render_stock_table(pool, show_export=True)
        # 加入自选股
        st.divider()
        st.subheader("⭐ 加入自选股")
        watchlist = load_watchlist()
        codes = [r['股票代码'] for r in pool]
        to_add = st.multiselect("选择加入自选股", codes)
        if st.button("➕ 加入自选股", width="stretch"):
            for c in to_add:
                if c not in watchlist:
                    watchlist.append(c)
            save_watchlist(watchlist)
            st.success(f"已加入 {len(to_add)} 只到自选股")
            st.rerun()

with tab2:
    watchlist = load_watchlist()
    st.subheader(f"自选股 ({len(watchlist)} 只)")
    if watchlist:
        # 显示 代码 - 名称（docs/ui2.md 修复: 自选股列表显示股票名称）
        from web.utils.session import get_feeder
        if 'stock_dict' not in st.session_state:
            st.session_state['stock_dict'] = get_feeder().get_all_stock_code_name()
        sd = st.session_state['stock_dict']
        display = [f"{c} - {sd.get(c, '')}" for c in watchlist]
        st.write("、".join(display))
        if st.button("🗑️ 清空自选股"):
            save_watchlist([])
            st.rerun()
    st.divider()
    # 模糊添加自选股（docs/ui2.md §四: streamlit-searchbox）
    st.subheader("➕ 模糊添加自选股")
    from streamlit_searchbox import st_searchbox
    from web.utils.session import get_feeder
    if 'stock_dict' not in st.session_state:
        st.session_state['stock_dict'] = get_feeder().get_all_stock_code_name()
    stock_dict = st.session_state['stock_dict']

    def _search(term: str):
        term = (term or '').lower().strip()
        if not term:
            return [f"{c} - {n}" for c, n in list(stock_dict.items())[:20]]
        return [f"{c} - {n}" for c, n in stock_dict.items()
                if term in c.lower() or term in n.lower()][:20]

    add_item = st_searchbox(_search, key="pool_add", label="🔍 输入代码/名称",
                            placeholder="如 600519 / 贵州茅台")
    if st.button("➕ 添加到自选股") and add_item:
        code = add_item.split(" - ")[0].strip()
        if code and code not in watchlist:
            watchlist.append(code)
            save_watchlist(watchlist)
            st.success(f"✅ 已添加 {add_item}")
            st.rerun()
        elif code in watchlist:
            st.info("该股票已在自选股中")

st.caption("💡 提示：真三振股票可在「📈 个股分析」页输入代码做深度分析")
