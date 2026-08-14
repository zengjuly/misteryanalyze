#!/usr/bin/env python3
# 1_📈_个股分析.py - 个股深度分析页面（docs/ui.md §4.1）
"""输入股票代码 → 评分卡片/K线/三大心法/四维共振/最近N日数据"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..', 'data'))

import streamlit as st

st.set_page_config(page_title="个股分析", page_icon="📈", layout="wide")

from web.utils.session import get_feeder, get_logic, get_config
from web.components.kline_chart import plot_kline
from web.components.score_card import (
    render_metric_cards, render_detail_cards, render_advice)

st.title("📈 个股深度分析")
st.caption("输入股票代码（如 sh600150 / 600150 / 中国船舶），查看三大心法 + 四维共振综合信号")

# ---------- 输入 ----------
cfg = get_config()
stock_pool = cfg.get('stocks', [])
feeder = get_feeder()
logic = get_logic()

c1, c2 = st.columns([3, 1])
with c1:
    code_input = st.text_input("股票代码", value="sh600150",
                               placeholder="如 sh600150 或 600150 或 贵州茅台")
with c2:
    pool_select = st.selectbox("或从股票池选择", [''] + stock_pool)
if pool_select:
    code_input = pool_select

if st.button("🚀 开始分析", type="primary", width="stretch"):
    code = code_input.strip()
    if not code:
        st.warning("请输入股票代码")
        st.stop()
    # 归一化: 600150 -> sh600150（按前缀推断市场）
    if code.isdigit():
        code = ('sh' if code.startswith('6') else
                'bj' if code.startswith(('4', '8')) else 'sz') + code
    elif '.' in code and len(code) == 9:
        code = code.replace('.', '')  # sh.600150 -> sh600150

    with st.spinner(f"正在分析 {code} ..."):
        try:
            # 获取数据
            daily = feeder.get_daily(code)
            if daily is None or daily.empty:
                st.error(f"❌ 无法获取 {code} 的行情数据（请检查代码或数据源）")
                st.stop()
            weekly = feeder.get_weekly(code)
            market_data = feeder.get_market_index()
            # 名称
            name = code
            try:
                from data.baostock_client import BaostockClient
                bc = BaostockClient()
                name = bc.get_stock_name(code)
            except Exception:
                pass
            # 综合信号（三大心法 + 四维共振）
            signal = logic.comprehensive_signal_analysis(
                daily, weekly_data=weekly, market_data=market_data,
                industry_data=None, industry_trend=None)

            st.success(f"✅ {code} {name} 分析完成")
            # 1. 评分卡片区
            st.subheader("🎯 评分概览")
            render_metric_cards(signal)
            # 2. 详细状态卡片
            st.subheader("🧭 三大心法与共振状态")
            render_detail_cards(signal)
            # 3. 操作建议
            st.subheader("💡 操作建议")
            render_advice(signal)
            # 4. K线图
            st.subheader("📊 K线图（日线 + 均线 + 成交量）")
            fig = plot_kline(daily.tail(120), title=f"{code} {name} 日K线")
            st.plotly_chart(fig, width="stretch")
            # 5. 分析详情
            st.subheader("📋 分析详情")
            for d in signal.get('详情', []):
                st.markdown(f"- {d}")
            # 6. 最近20日数据
            st.subheader("🗓️ 最近20个交易日数据")
            tail = daily.tail(20).copy()
            tail['日期'] = tail['日期'].astype(str)
            show_cols = ['日期', '收盘价', '开盘价', '最高价', '最低价',
                         '成交量', '换手率']
            show_cols = [c for c in show_cols if c in tail.columns]
            st.dataframe(tail[show_cols].round(3), width="stretch")
            st.download_button("📥 导出CSV",
                               tail[show_cols].to_csv(index=False).encode('utf-8-sig'),
                               f"{code}_daily.csv", "text/csv")
        except Exception as e:
            st.error(f"❌ 分析异常: {e}")
            import traceback
            st.code(traceback.format_exc())
