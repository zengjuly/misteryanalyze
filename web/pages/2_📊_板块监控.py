#!/usr/bin/env python3
# 2_📊_板块监控.py - 板块监控（Financial-API 板块指数，非成分股抽样，docs/082203 §5）
"""板块强度 = MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大×0.3（真实指数日K）
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
import yaml

st.set_page_config(page_title="板块监控", page_icon="📊", layout="wide")

from web.utils.session import get_feeder, get_logic
from web.pages_util import calc_sector_strength

st.title("📊 板块监控")
st.caption(
    "板块强度基于 Financial-API（同花顺扶摇）官方板块指数日K："
    "MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大×0.3（非成分股抽样）"
)

try:
    with st.spinner("拉取板块指数并计算强度..."):
        rows = calc_sector_strength(use_cache=True)
    if not rows:
        st.info("暂无板块指数数据（检查 HITHINK_FINANCE_API_KEY / fuyao / index-catalog）")
        st.stop()

    df = pd.DataFrame(rows)

    col_left, col_right = st.columns([1, 1.4])
    with col_left:
        st.subheader("🏆 Top15 强势板块")
        top = df.head(15).iloc[::-1]
        fig = px.bar(top, x='板块得分', y='板块', orientation='h',
                     color='板块得分', color_continuous_scale='RdYlGn',
                     title="板块得分 Top15")
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch")
    with col_right:
        st.subheader(f"全量板块排名（{len(df)} 个）")
        st.dataframe(df, width="stretch", height=520)
        st.download_button(
            "📥 导出CSV",
            df.to_csv(index=False).encode('utf-8-sig'),
            "industry_strength.csv", "text/csv")

    st.divider()
    st.subheader("🔍 板块成分股钻取（真三振/高评分龙头高亮）")
    industry_list = df['板块'].tolist()
    code_by_name = {r['板块']: r.get('板块代码', '') for r in rows}
    sel = st.selectbox("选择板块", industry_list)
    if sel:
        sector_code = code_by_name.get(sel, '')
        name_map = {}
        try:
            from db_manager import MysteryDB
            info = MysteryDB().get_stock_info(limit=None)
            if info is not None and not info.empty:
                name_map = {
                    str(c).replace('.', ''): n
                    for c, n in zip(info['code'], info['code_name'])
                }
        except Exception:
            pass

        codes = []
        try:
            root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
            cfg = yaml.safe_load(open(
                os.path.join(root, 'config', 'config.yaml'), encoding='utf-8'))
            from ths_client import ThsOfficialClient
            client = ThsOfficialClient(cfg)
            if sector_code:
                codes = client.fetch_constituents_by_code(sector_code)
            if not codes:
                # 回退：行业映射
                ind_map = get_feeder().get_industry_data()
                codes = ind_map.get('industry_codes', {}).get(sel, [])
                codes = [str(c).replace('.', '') for c in codes]
        except Exception as e:
            st.caption(f"成分获取: {e}")

        if st.button("🔬 钻取该板块成分股信号", type="secondary"):
            logic = get_logic()
            results = []
            prog = st.progress(0.0, text="分析成分股...")
            limit_n = min(len(codes), 30)
            for i, c in enumerate(codes[:30]):
                try:
                    cc = str(c).replace('.', '')
                    d = get_feeder().get_daily(cc)
                    if d is None or d.empty:
                        continue
                    sig = logic.comprehensive_signal_analysis(
                        d, weekly_data=None)
                    try:
                        from analysis.adaptive_platform import (
                            analyze_adaptive_platform)
                        ap = analyze_adaptive_platform(d, stock_code=cc)
                        plat_info = logic.platform_breakthrough_analysis(d)
                        chip_info = logic.technical_detail_capture(d)
                        bull = logic.main_bull_wave_checklist(d)
                    except Exception:
                        ap, plat_info, chip_info, bull = {}, {}, {}, {}
                    results.append({
                        '代码': cc,
                        '名称': name_map.get(cc, ''),
                        '综合评分': sig.get('综合评分', 0),
                        '真三振': sig.get('真三振', False),
                        '主升浪信号': sig.get('主升浪信号', False),
                        '共振级别': sig.get('共振级别', '无共振'),
                        '操作建议': sig.get('操作建议', '观望'),
                        'POC': ap.get('POC'),
                        '平台上轨': ap.get('自适应上轨'),
                        '平台下轨': ap.get('自适应下轨'),
                        '平台状态': plat_info.get('平台状态', ''),
                        '筹码集中度': chip_info.get('筹码集中度', ''),
                        '主升浪满足': bull.get('满足数量', 0),
                        '最新价': float(d['收盘价'].iloc[-1])
                        if '收盘价' in d.columns else None,
                    })
                except Exception:
                    continue
                prog.progress((i + 1) / max(limit_n, 1))
            prog.empty()
            if results:
                rdf = pd.DataFrame(results).sort_values(
                    '综合评分', ascending=False)
                from web.utils.table_links import render_code_link_table
                render_code_link_table(
                    rdf, code_col='代码', width="stretch", height=420)
                leaders = rdf[
                    (rdf['真三振']) | (rdf['综合评分'] >= 85)
                ]['代码'].tolist()
                st.info(
                    f"🏆 龙头（真三振或评分≥85）: "
                    f"{', '.join(leaders) or '无'}")
            else:
                st.warning("成分股分析无结果（数据不足）")
        else:
            comp = pd.DataFrame([
                {'代码': str(c).replace('.', ''),
                 '名称': name_map.get(str(c).replace('.', ''), '')}
                for c in codes[:200]
            ])
            if not comp.empty:
                from web.utils.table_links import render_code_link_table
                render_code_link_table(
                    comp, code_col='代码', width="stretch", height=320)
            else:
                st.caption("暂无成分股列表")
except Exception as e:
    st.error(f"❌ 板块数据加载失败: {e}")
    import traceback
    st.code(traceback.format_exc())
