#!/usr/bin/env python3
# 1_📈_个股分析.py - 个股深度分析页面（docs/ui.md §4.1 + docs/ui2.md 升级）
"""模糊搜索 → 深度分析（Excel对齐：震荡区间/周月K/筹码/主升浪8项/财务）
+ 周期切换K线(MACD+震荡区间) + 分析结果缓存（行情未更新不重复分析）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..', 'data'))

import streamlit as st
from datetime import date

import pandas as pd

st.set_page_config(page_title="个股分析", page_icon="📈", layout="wide")

from streamlit_searchbox import st_searchbox

from web.utils.session import get_feeder, get_logic, get_config
from web.components.kline_chart import plot_kline
from web.components.score_card import (
    render_metric_cards, render_detail_cards, render_advice)

st.title("📈 个股深度分析")
st.caption("支持代码/名称模糊搜索，分析结果与 Excel 报告对齐"
           "（震荡区间/周月K/筹码/主升浪8项/财务），K线含 MACD 与周期切换")

cfg = get_config()
feeder = get_feeder()
logic = get_logic()

# ---------- 股票代码-名称字典（模糊搜索） ----------
if 'stock_dict' not in st.session_state:
    st.session_state['stock_dict'] = feeder.get_all_stock_code_name()
stock_dict = st.session_state['stock_dict']


def search_stock(term: str):
    """模糊搜索：匹配代码或名称，返回 '代码 - 名称' 列表"""
    term = (term or '').lower().strip()
    if not term:
        return [f"{c} - {n}" for c, n in list(stock_dict.items())[:30]]
    hits = [f"{c} - {n}" for c, n in stock_dict.items()
            if term in c.lower() or term in n.lower()]
    return hits[:30]


def resolve_code(sel: str):
    """解析 'sh600150 - 中国船舶' → sh600150"""
    return sel.split(' - ')[0].strip() if sel else ''


# ---------- 输入区 ----------
c1, c2 = st.columns([3, 2])
with c1:
    selected = st_searchbox(
        search_stock, key="stock_search",
        label="🔍 代码/名称模糊搜索",
        placeholder="输入代码或名称，如 600150 / 中国船舶")
with c2:
    # 股票池 = 自选股列表（watchlist_manager 独立库，sh.600150 格式）
    try:
        from watchlist_manager import WatchlistManager
        wl = WatchlistManager().list_all()
        wl_codes = wl['code'].tolist() if not wl.empty else []
        # 自选股 code(sh.600150) → 无点格式匹配 stock_dict
        pool_names = [
            f"{c.replace('.', '')} - {stock_dict.get(c.replace('.', ''), n)}"
            for c, n in zip(wl_codes,
                            wl['name'].tolist() if not wl.empty else [])]
    except Exception:
        pool_names = [f"{s} - {stock_dict.get(s, '')}"
                      for s in cfg.get('stocks', [])]
    pool_sel = st.selectbox("⭐ 自选股", [''] + pool_names)
    if pool_sel:
        selected = pool_sel

# ---------- 从其他页面跳转：?code=sh600150 自动填充并分析 ----------
_qp = st.query_params
_jump_code = str(_qp.get('code', '')) if _qp else ''
if _jump_code:
    # 一次性跳转：分析完成后清除参数，避免每次 rerun 重复触发
    try:
        del _qp['code']
    except Exception:
        pass

if st.button("🚀 开始分析", type="primary", width="stretch") or _jump_code:
    if _jump_code:
        code = _jump_code
    elif not selected:
        st.warning("请选择或输入股票代码")
        st.stop()
        code = None
    else:
        code = resolve_code(selected)
    if not code:
        st.warning("无法解析股票代码")
        st.stop()
    name = stock_dict.get(code, code)

    with st.spinner(f"正在分析 {code} {name} ..."):
        try:
            from db_manager import MysteryDB
            db = MysteryDB()
            daily = feeder.get_daily(code)
            if daily is None or daily.empty:
                st.error(f"❌ 无法获取 {code} 行情数据")
                st.stop()
            last_date = str(daily['日期'].max())[:10]

            # ===== 分析结果缓存（docs/ui2.md 二级缓存） =====
            db_code = code[:2] + '.' + code[2:] if '.' not in code else code
            cached = db.get_analysis_cache(db_code, 'daily', last_date)
            if cached and cached.get('signal'):
                signal = cached['signal']
                st.caption(f"⚡ 命中分析缓存（最新交易日 {last_date}，"
                           f"行情未更新未重复分析）")
            else:
                weekly = feeder.get_weekly(code)
                # 大盘指数会话内只拉一次（指数获取走在线源较慢，避免每次分析卡顿）
                if 'market_data_cache' not in st.session_state:
                    with st.spinner("加载大盘指数数据..."):
                        st.session_state['market_data_cache'] = \
                            feeder.get_market_index()
                market_data = st.session_state['market_data_cache']
                signal = logic.comprehensive_signal_analysis(
                    daily, weekly_data=weekly, market_data=market_data,
                    industry_data=None, industry_trend=None)
                db.set_analysis_cache(db_code, 'daily', last_date,
                                      {'signal': signal})

            st.success(f"✅ {code} {name} 分析完成（最新交易日 {last_date}）")

            # 所属板块（docs/ui2.md: 支持分析板块）
            industry_name = '未知'
            try:
                ind_map = feeder.get_industry_data()
                cm = ind_map.get('code_map', {})
                industry_name = cm.get(db_code, cm.get(code, '未知'))
            except Exception:
                pass
            st.info(f"🏢 所属板块: **{industry_name}**")

            # ---------- 1. 评分卡片 ----------
            st.subheader("🎯 评分概览")
            render_metric_cards(signal)
            st.subheader("🧭 三大心法与共振状态")
            render_detail_cards(signal)
            st.subheader("💡 操作建议")
            render_advice(signal)

            # ---------- 2. 财务数据（docs/ui2.md, 无缓存自动拉取） ----------
            st.subheader("💰 财务数据")
            try:
                from financial_storage import FinancialStorage
                fs = FinancialStorage(db)
                fi = fs.ensure_financial(db_code)
                if fi:
                    f1, f2, f3, f4 = st.columns(4)
                    f1.metric("PE", fi.get('PE', 'N/A'))
                    f2.metric("PB", fi.get('PB', 'N/A'))
                    f3.metric("股息率",
                              f"{fi.get('股息率', 0):.2f}%" if fi.get('股息率') is not None else 'N/A')
                    f4.metric("最新ROE",
                              f"{fi.get('ROE', 0):.2f}%" if fi.get('ROE') is not None else 'N/A')
                    if fi.get('报告期'):
                        st.caption(f"报告期: {fi.get('报告期')}")
                    hist = fs.load_history(db_code, limit=8)
                    if hist is not None and not hist.empty:
                        with st.expander("📊 近三年 ROE 历史"):
                            # load_financial 返回英文原始列（report_date/roe）
                            roe_df = hist[['report_date', 'roe']].dropna().tail(8)
                            roe_df.columns = ['报告期', 'ROE']
                            st.dataframe(roe_df, width="stretch")
                else:
                    st.warning("财务数据获取失败（在线源不可用）")
            except Exception as e:
                st.warning(f"财务数据获取失败: {e}")

            # ---------- 3. Excel 对齐明细 ----------
            st.subheader("📋 分析明细（与Excel报告对齐）")
            # 震荡区间（自适应平台 + 平台箱体）
            try:
                from analysis.adaptive_platform import analyze_adaptive_platform
                ap = analyze_adaptive_platform(daily, stock_code=code)
                p1, p2, p3 = st.columns(3)
                p1.metric("自适应平台 POC", ap.get('POC', 'N/A'))
                p2.metric("平台上轨", ap.get(
                    '自适应上轨', ap.get('上轨', ap.get('upper', 'N/A'))))
                p3.metric("平台下轨", ap.get(
                    '自适应下轨', ap.get('下轨', ap.get('lower', 'N/A'))))
            except Exception as e:
                st.caption(f"自适应平台: {e}")
            plat = logic.platform_breakthrough_analysis(daily)
            if plat.get('平台范围'):
                st.markdown(f"**震荡区间（平台箱体）**: {plat.get('平台范围')} "
                            f"| 状态: {plat.get('平台状态', '未知')}")
            # 筹码分析
            det = logic.technical_detail_capture(daily)
            st.markdown(f"**筹码分析**: 集中度 {det.get('筹码集中度', '未知')} "
                        f"| 趋势 {det.get('筹码趋势', '未知')}")
            # 主升浪8项指标对比表
            cl = logic.main_bull_wave_checklist(daily)
            if cl.get('详情'):
                items = [d for d in cl['详情'] if '✅' in d or '❌' in d]
                if items:
                    st.markdown(f"**主升浪8项指标对比**（满足 {cl.get('满足数量', 0)}/8）")
                    for it in items:
                        st.markdown(f"- {it}")
            # 周/月K箱体（简版: 重采样后近N周期高低）
            from kline_resampler import KLineResampler
            rs = KLineResampler()
            wk = rs.resample(daily, 'weekly')
            mo = rs.resample(daily, 'monthly')
            if wk is not None and len(wk):
                w_hi, w_lo = float(wk['最高价'].tail(20).max()), float(wk['最低价'].tail(20).min())
                st.markdown(f"**周线箱体**（近20周）: {w_lo:.2f} ~ {w_hi:.2f} "
                            f"| 最新 {wk['收盘价'].iloc[-1]:.2f}")
            if mo is not None and len(mo):
                m_hi, m_lo = float(mo['最高价'].tail(12).max()), float(mo['最低价'].tail(12).min())
                st.markdown(f"**月线箱体**（近12月）: {m_lo:.2f} ~ {m_hi:.2f} "
                            f"| 最新 {mo['收盘价'].iloc[-1]:.2f}")

            # ---------- 4. K线图（最近1000交易日 + MA377/610 + EMA20，docs/081601.md） ----------
            st.subheader("📊 K线图（1000交易日 + MA377/610 + EMA20，日/周/月一次完成）")
            from indicators.ma_indicators import MAIndicators

            # 长历史K线（1000交易日；缓存不足时在线源拉取，会话内复用）
            kkey = f'kline_long_{code}'
            if kkey not in st.session_state:
                from datetime import datetime, timedelta
                start4y = (datetime.now() - timedelta(days=365 * 4)
                           ).strftime('%Y-%m-%d')
                long_df = feeder.get_daily(code, start_date=start4y)
                if long_df is None or long_df.empty:
                    long_df = daily
                st.session_state[kkey] = long_df
            long_df = st.session_state[kkey]

            def _prep_kline(kdf, box_dict, max_bars=1000):
                """补 MA377/610 + EMA20 后绘制（docs/081601.md）"""
                kdf = kdf.copy()
                if len(kdf) > max_bars:
                    kdf = kdf.tail(max_bars)
                if 'MA377' not in kdf.columns:
                    kdf = MAIndicators().calculate_ma(kdf)
                if 'EMA20' not in kdf.columns:
                    kdf = MAIndicators().calculate_ema(kdf)
                return plot_kline(kdf, title=f"{code} {name}", box=box_dict,
                                  max_bars=max_bars)

            # 日K箱体（近20日震荡区间）
            day_box = {'上沿': float(daily['最高价'].tail(20).max()),
                       '下沿': float(daily['最低价'].tail(20).min()),
                       'POC': ap.get('POC') if 'ap' in dir() else None}
            tab_d, tab_w, tab_m = st.tabs(["📅 日线", "📆 周线", "🗓️ 月线"])
            with tab_d:
                st.plotly_chart(_prep_kline(long_df, day_box, max_bars=1000),
                                width="stretch")
                st.caption(f"日线: 最近 {min(len(long_df), 1000)} 个交易日")
            with tab_w:
                wk_long = rs.resample(long_df, 'weekly') if long_df is not None else None
                if wk_long is not None and len(wk_long):
                    w_hi = float(wk_long['最高价'].tail(20).max())
                    w_lo = float(wk_long['最低价'].tail(20).min())
                    st.plotly_chart(_prep_kline(wk_long,
                                                {'上沿': w_hi, '下沿': w_lo},
                                                max_bars=200),
                                    width="stretch")
                    st.caption(f"周线（对应日线窗口，最近200周）: "
                               f"{w_lo:.2f} ~ {w_hi:.2f} "
                               f"| 最新 {wk_long['收盘价'].iloc[-1]:.2f}")
                else:
                    st.info("周线数据不足")
            with tab_m:
                mo_long = rs.resample(long_df, 'monthly') if long_df is not None else None
                if mo_long is not None and len(mo_long):
                    m_hi = float(mo_long['最高价'].tail(12).max())
                    m_lo = float(mo_long['最低价'].tail(12).min())
                    st.plotly_chart(_prep_kline(mo_long,
                                                {'上沿': m_hi, '下沿': m_lo},
                                                max_bars=50),
                                    width="stretch")
                    st.caption(f"月线（对应日线窗口，最近50月）: "
                               f"{m_lo:.2f} ~ {m_hi:.2f} "
                               f"| 最新 {mo_long['收盘价'].iloc[-1]:.2f}")
                else:
                    st.info("月线数据不足")

            # ---------- 5. 分析详情 ----------
            st.subheader("📋 触发条件明细")
            for d in signal.get('详情', []):
                st.markdown(f"- {d}")

            # ---------- 6. 最近20日数据 ----------
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
            # 分析结果 Excel（信号摘要 + 最近20日）
            try:
                from web.utils.download import excel_download_button
                sig_row = {
                    '股票代码': code, '股票名称': name,
                    '综合评分': signal.get('综合评分', ''),
                    '共振级别': signal.get('共振级别', ''),
                    '真三振': signal.get('真三振', ''),
                    '主升浪信号': signal.get('主升浪信号', ''),
                    '资金活跃': signal.get('资金活跃', ''),
                    '操作建议': signal.get('操作建议', ''),
                    '筹码集中度': det.get('筹码集中度', ''),
                    '平台范围': plat.get('平台范围', ''),
                    '平台状态': plat.get('平台状态', ''),
                    '主升浪满足': cl.get('满足数量', ''),
                    '主升浪判断': cl.get('综合判断', ''),
                }
                excel_download_button(
                    tail[show_cols].round(3),
                    f"{code}_{name}_分析结果_{date.today()}.xlsx",
                    button_label="📥 导出分析结果 Excel",
                    sheet_name='最近20日',
                    sheets={'信号摘要': pd.DataFrame([sig_row])},
                    key=f"export_analysis_{code}",
                    help="多 sheet: 最近20日K线 / 信号摘要")
            except Exception as ex:
                st.caption(f"Excel导出不可用: {ex}")
        except Exception as e:
            st.error(f"❌ 分析异常: {e}")
            import traceback
            st.code(traceback.format_exc())
