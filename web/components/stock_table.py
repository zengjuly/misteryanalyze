#!/usr/bin/env python3
# stock_table.py - 股票表格组件（docs/ui.md §5.3）
"""st.dataframe 股票列表展示：排序/筛选/真三振高亮/CSV导出"""
import pandas as pd
import streamlit as st


def render_stock_table(results: list, show_export: bool = True):
    """渲染扫描/真三振结果表格
    :param results: 分析结果字典列表（含 股票代码/股票名称/综合评分/真三振/...）
    """
    if not results:
        st.info("暂无数据，请先运行全市场扫描")
        return
    df = pd.DataFrame(results)
    # 统一列名
    cols = ['股票代码', '股票名称', '行业板块', '综合评分', '真三振', '主升浪信号',
            '资金活跃', '操作建议', '共振级别']
    cols = [c for c in cols if c in df.columns]
    show = df[cols] if cols else df
    # 高亮真三振
    styled = show.style.map(
        lambda v: 'background-color: #fdeaea' if v is True else '',
        subset=['真三振'] if '真三振' in show.columns else None,
    )
    # 股票代码列 → 点击跳转个股分析
    from web.utils.table_links import render_code_link_table
    render_code_link_table(styled.data if hasattr(styled, 'data') else show,
                           code_col='股票代码', width="stretch", height=420)
    if show_export:
        c1, c2 = st.columns(2)
        with c1:
            csv = show.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 导出 CSV", csv, "scan_results.csv",
                               "text/csv", key="export_csv")
        with c2:
            from web.utils.download import excel_download_button
            excel_download_button(
                show, "scan_results.xlsx",
                button_label="📥 导出 Excel",
                key="export_xlsx")
