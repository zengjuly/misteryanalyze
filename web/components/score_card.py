#!/usr/bin/env python3
# score_card.py - 评分卡片组件（docs/ui.md §5.2）
"""st.metric 多卡片布局：综合评分/真三振/主升浪/资金活跃 + 三大心法状态"""
import streamlit as st


def render_metric_cards(signal: dict):
    """渲染顶部 4 列评分卡片（综合评分/真三振/主升浪/资金活跃）"""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("综合评分", f"{signal.get('综合评分', 0):.1f}", "0-100")
    c2.metric("真三振", "✅ 是" if signal.get('真三振') else "❌ 否")
    c3.metric("主升浪信号", "✅ 是" if signal.get('主升浪信号') else "❌ 否")
    c4.metric("资金活跃", "✅ 是" if signal.get('资金活跃') else "❌ 否")


def render_detail_cards(signal: dict):
    """渲染详细状态卡片（年线滤网/周线锚定/破五反五/共振级别）"""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("年线滤网", "✅ 通过" if signal.get('年线滤网') else "❌ 未通过")
    c2.metric("周线锚定", "✅ 锚定" if signal.get('周线锚定') else "❌ 未锚定")
    c3.metric("破五反五", "✅ 符合" if signal.get('破五反五') else "❌ 不符合")
    c4.metric("共振级别", signal.get('共振级别', '无共振'))


def render_advice(signal: dict):
    """醒目展示操作建议"""
    advice = signal.get('操作建议', '观望')
    score = signal.get('综合评分', 0)
    if '强烈关注' in advice or '重点关注' in advice:
        st.success(f"🎯 {advice}")
    elif '可关注' in advice:
        st.info(f"📌 {advice}")
    else:
        st.warning(f"⏳ {advice}")
    st.caption(f"共振评分 {signal.get('共振评分', 0)} / 100 · "
               f"最强板块: {', '.join(map(str, signal.get('最强板块', [])[:3])) or '无'}")
