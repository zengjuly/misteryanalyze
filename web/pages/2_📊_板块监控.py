#!/usr/bin/env python3
# 2_📊_板块监控.py - 板块监控页面（docs/ui.md §4.2）
"""行业板块列表 + 强度排名（按成分股平均近5日涨跌幅）+ 板块成分股"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..', 'data'))

import streamlit as st
import pandas as pd

st.set_page_config(page_title="板块监控", page_icon="📊", layout="wide")

from web.utils.session import get_feeder

st.title("📊 板块监控")
st.caption("行业板块强度排名（成分股近5日平均涨跌幅）与成分股列表")


def load_industry_strength(feeder, max_samples=5):
    """计算各行业板块强度: 成分股近5日平均涨跌幅（基于缓存K线）"""
    from db_manager import MysteryDB
    import numpy as np
    db = MysteryDB()
    ind_map = feeder.get_industry_data()
    industry_codes = ind_map.get('industry_codes', {})
    code_map = ind_map.get('code_map', {})
    rows = []
    for industry, codes in industry_codes.items():
        if not codes:
            continue
        samples = codes[:max_samples]
        pcts = []
        for c in samples:
            try:
                df = db.load_kline(c, 'daily')
                if df is not None and len(df) >= 6 and 'pctChg' in df.columns:
                    tail = df['pctChg'].dropna().tail(5)
                    if len(tail) >= 3:
                        pcts.append(float(tail.mean()))
            except Exception:
                continue
        if pcts:
            rows.append({
                '板块': industry, '成分股数': len(codes),
                '样本数': len(pcts),
                '近5日平均涨跌幅%': round(float(np.mean(pcts)), 2),
            })
    rows.sort(key=lambda r: r['近5日平均涨跌幅%'], reverse=True)
    return rows, industry_codes, code_map


feeder = get_feeder()

try:
    with st.spinner("计算板块强度..."):
        rows, industry_codes, code_map = load_industry_strength(feeder)
    if not rows:
        st.info("暂无板块数据（数据库无行业分类或行情缓存）")
        st.stop()

    # ---------- 板块强度排名 ----------
    st.subheader(f"🏆 板块强度排名（{len(rows)} 个板块）")
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", height=380)
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 导出CSV", csv, "industry_strength.csv", "text/csv")

    # ---------- 板块成分股 ----------
    st.divider()
    st.subheader("🔍 查看板块成分股")
    industry_list = [r['板块'] for r in rows]
    sel = st.selectbox("选择板块", industry_list)
    if sel:
        codes = industry_codes.get(sel, [])
        name_map = {}
        try:
            info = db_ = None
            from db_manager import MysteryDB
            db_ = MysteryDB()
            info = db_.get_stock_info(limit=None)
            if info is not None and not info.empty:
                name_map = dict(zip(info['code'], info.get('code_name', info.get('name', []))))
        except Exception:
            pass
        st.write(f"**{sel}**: {len(codes)} 只成分股")
        comp = pd.DataFrame([{
            '代码': c,
            '名称': name_map.get(c, ''),
        } for c in codes[:200]])
        st.dataframe(comp, width="stretch", height=360)
except Exception as e:
    st.error(f"❌ 板块数据加载失败: {e}")
    import traceback
    st.code(traceback.format_exc())
