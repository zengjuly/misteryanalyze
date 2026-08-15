#!/usr/bin/env python3
# 2_📊_板块监控.py - 板块监控页面（docs/ui.md §4.2 + docs/ui2.md 升级）
"""板块共振强度模型: 得分 = MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大×0.3
Top15 条形图 + 全量排名表 + 成分股钻取（真三振/高评分龙头高亮）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..', 'data'))

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="板块监控", page_icon="📊", layout="wide")

from web.utils.session import get_feeder, get_logic


@st.cache_data(ttl=3600, show_spinner=False)
def calc_sector_strength():
    """板块得分 = MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大×0.3
    （基于缓存K线，本地计算快）"""
    from db_manager import MysteryDB
    import numpy as np
    feeder = get_feeder()
    db = MysteryDB()
    ind_map = feeder.get_industry_data()
    industry_codes = ind_map.get('industry_codes', {})
    rows = []
    for industry, codes in industry_codes.items():
        samples = codes[:6]  # 每行业抽样6只
        ma20_bias, chg10, amount_ratio = [], [], []
        for c in samples:
            try:
                df = db.load_kline(c, 'daily')
                if df is None or len(df) < 15:
                    continue
                close = float(df['close'].iloc[-1])
                ma20 = float(df['close'].tail(20).mean())
                if ma20 > 0:
                    ma20_bias.append((close / ma20 - 1) * 100)
                past = float(df['close'].iloc[-11])
                if past > 0:
                    chg10.append((close / past - 1) * 100)
                if 'amount' in df.columns:
                    a_ma5 = float(df['amount'].iloc[-6:-1].mean())
                    if a_ma5 > 0:
                        amount_ratio.append(
                            float(df['amount'].iloc[-1]) / a_ma5)
            except Exception:
                continue
        if not ma20_bias:
            continue
        bias = float(np.mean(ma20_bias))
        chg = float(np.mean(chg10)) if chg10 else 0.0
        amt = float(np.mean(amount_ratio)) if amount_ratio else 1.0
        score = bias * 0.4 + chg * 0.3 + (amt - 1) * 100 * 0.3
        rows.append({
            '板块': industry, '成分股数': len(codes), '样本数': len(ma20_bias),
            'MA20偏离%': round(bias, 2), '近10日涨幅%': round(chg, 2),
            '成交额放大': round(amt, 2), '板块得分': round(score, 2),
        })
    rows.sort(key=lambda r: r['板块得分'], reverse=True)
    return rows


st.title("📊 板块监控")
st.caption("板块共振强度 = MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大×0.3"
           "（docs/ui2.md）")

try:
    with st.spinner("计算板块强度..."):
        rows = calc_sector_strength()
    if not rows:
        st.info("暂无板块数据（数据库无行业分类或行情缓存）")
        st.stop()

    df = pd.DataFrame(rows)

    # ---------- Top15 条形图 + 排名表 ----------
    col_left, col_right = st.columns([1, 1.4])
    with col_left:
        st.subheader("🏆 Top15 强势板块")
        top = df.head(15).iloc[::-1]  # 反转让最大在顶部
        fig = px.bar(top, x='板块得分', y='板块', orientation='h',
                     color='板块得分', color_continuous_scale='RdYlGn',
                     title="板块得分 Top15")
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch")
    with col_right:
        st.subheader(f"全量板块排名（{len(df)} 个）")
        st.dataframe(df, width="stretch", height=520)
        st.download_button("📥 导出CSV", df.to_csv(index=False).encode('utf-8-sig'),
                           "industry_strength.csv", "text/csv")

    # ---------- 成分股钻取 ----------
    st.divider()
    st.subheader("🔍 板块成分股钻取（真三振/高评分龙头高亮）")
    industry_list = df['板块'].tolist()
    sel = st.selectbox("选择板块", industry_list)
    if sel:
        from db_manager import MysteryDB
        db = MysteryDB()
        ind_map = get_feeder().get_industry_data()
        codes = ind_map.get('industry_codes', {}).get(sel, [])
        # 成分股名称
        info = db.get_stock_info(limit=None)
        name_map = {}
        if info is not None and not info.empty:
            name_map = dict(zip(info['code'], info['code_name']))
        if st.button("🔬 钻取该板块成分股信号", type="secondary"):
            logic = get_logic()
            results = []
            prog = st.progress(0.0, text="分析成分股...")
            for i, c in enumerate(codes[:30]):
                try:
                    cc = c.replace('.', '')  # sh.600150 -> sh600150
                    d = get_feeder().get_daily(cc)
                    if d is None or d.empty:
                        continue
                    sig = logic.comprehensive_signal_analysis(d, weekly_data=None)
                    results.append({
                        '代码': cc,
                        '名称': name_map.get(c, ''),
                        '综合评分': sig.get('综合评分', 0),
                        '真三振': sig.get('真三振', False),
                        '主升浪信号': sig.get('主升浪信号', False),
                        '共振级别': sig.get('共振级别', '无共振'),
                        '操作建议': sig.get('操作建议', '观望'),
                    })
                except Exception:
                    continue
                prog.progress((i + 1) / min(len(codes), 30))
            prog.empty()
            if results:
                rdf = pd.DataFrame(results).sort_values('综合评分', reverse=True)
                # 高亮真三振/评分≥85 的龙头
                styled = rdf.style.map(
                    lambda v: 'background-color: #fdeaea' if v is True else '',
                    subset=['真三振'])
                st.dataframe(styled, width="stretch", height=420)
                st.info(f"🏆 龙头（真三振或评分≥85）: "
                        f"{', '.join(rdf[(rdf['真三振']) | (rdf['综合评分'] >= 85)]['代码'].tolist()) or '无'}")
            else:
                st.warning("成分股分析无结果（数据不足）")
        else:
            comp = pd.DataFrame([{'代码': c, '名称': name_map.get(c, '')}
                                 for c in codes[:200]])
            st.dataframe(comp, width="stretch", height=320)
except Exception as e:
    st.error(f"❌ 板块数据加载失败: {e}")
    import traceback
    st.code(traceback.format_exc())
