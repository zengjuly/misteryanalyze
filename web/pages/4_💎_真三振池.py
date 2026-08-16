#!/usr/bin/env python3
# 4_💎_真三振池.py - 真三振池页面（docs/ui.md §4.4 + 081601.md §三 自选剥离）
"""真三振池只展示扫描结果 + 一键加入自选（自选管理已独立至 ⭐ 自选股页面）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..'))

import streamlit as st

st.set_page_config(page_title="真三振池", page_icon="💎", layout="wide")

from web.utils.session import load_scan_results, get_feeder
from web.components.stock_table import render_stock_table
from data.watchlist_manager import WatchlistManager

st.title("💎 真三振池")
st.caption("最近一次扫描产出的真三振 / 高评分股票，支持一键加入自选股"
           "（自选管理在 ⭐ 自选股 页面，docs/081601.md §三）")

results = st.session_state.get('scan_results') or load_scan_results()
if not results:
    st.info("暂无扫描结果，请先在「🔍 全市场扫描」页面运行扫描")
else:
    pool = [r for r in results if r.get('真三振')
            or r.get('综合评分', 0) >= 85]
    st.subheader(f"符合条件的股票: {len(pool)} 只")
    render_stock_table(pool, show_export=True)

    # 一键加入自选（docs/081601.md: 真三振池只保留展示+加入）
    st.divider()
    st.subheader("⭐ 加入自选股")
    if 'stock_dict' not in st.session_state:
        st.session_state['stock_dict'] = get_feeder().get_all_stock_code_name()
    sd = st.session_state['stock_dict']
    wm = WatchlistManager()
    options = [f"{r['股票代码']} - {sd.get(r['股票代码'], r.get('股票名称', ''))}"
               for r in pool]
    to_add = st.multiselect("选择加入自选股（已存在将更新来源）", options)
    if st.button("➕ 加入自选股", width="stretch"):
        added = 0
        for opt in to_add:
            code = str(opt).split(' - ')[0].strip()
            name = str(opt).split(' - ')[1].strip() if ' - ' in str(opt) else ''
            wm.add(code, name=name, source='真三振')
            added += 1
        st.success(f"✅ 已加入 {added} 只到自选股（可在 ⭐ 自选股 页面管理）")
        st.rerun()

st.caption("💡 自选股增删改查、来源筛选、CSV 导出请前往 **⭐ 自选股** 页面")
