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

# ---------- 行业分类 session 缓存（docs/082206: 避免每票/每次 rerun 全量读） ----------
if 'industry_map' not in st.session_state:
    try:
        st.session_state['industry_map'] = feeder.get_industry_data()
    except Exception:
        st.session_state['industry_map'] = {}

# ---------- 股票代码-名称字典（模糊搜索） ----------
if 'stock_dict' not in st.session_state:
    st.session_state['stock_dict'] = feeder.get_all_stock_code_name()
stock_dict = st.session_state['stock_dict']


def search_stock(term: str):
    """模糊搜索：匹配代码或名称，返回 '代码 - 名称' 列表"""
    term = (term or '').lower().strip()
    if not term:
        return [f"{c} - {n}" for c, n in list(stock_dict.items())[:30]]
    # 单字符不扫全表（docs/082208 §2: 避免每次按键全市场遍历慢卡）
    if len(term) < 2:
        # 仅匹配代码前缀（sh/sz + 数字开头），不遍历名称
        return [f"{c} - {n}" for c, n in list(stock_dict.items())[:30]
                if c.lower().startswith(term)]
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
    # 自选股 session 缓存（docs/082208 §3: TTL 或按钮刷新，不每键 list_all）
    try:
        import time as _time
        _wl_ts = st.session_state.get('watchlist_ts', 0)
        _need_wl = (_time.time() - _wl_ts > 300  # TTL 5分钟
                    or st.session_state.get('watchlist_force_refresh'))
        if _need_wl:
            from watchlist_manager import WatchlistManager
            wl = WatchlistManager().list_all()
            wl_codes = wl['code'].tolist() if not wl.empty else []
            # 自选股 code(sh.600150) → 无点格式匹配 stock_dict
            pool_names = [
                f"{c.replace('.', '')} - "
                f"{stock_dict.get(c.replace('.', ''), n)}"
                for c, n in zip(wl_codes,
                                wl['name'].tolist() if not wl.empty else [])]
            st.session_state['watchlist_pool_names'] = pool_names
            st.session_state['watchlist_ts'] = _time.time()
            st.session_state['watchlist_force_refresh'] = False
        pool_names = st.session_state.get('watchlist_pool_names') or []
    except Exception:
        pool_names = [f"{s} - {stock_dict.get(s, '')}"
                      for s in cfg.get('stocks', [])]
    r1, r2 = st.columns([4, 1])
    with r1:
        pool_sel = st.selectbox("⭐ 自选股", [''] + pool_names)
    with r2:
        if st.button("🔄", help="刷新自选股"):
            st.session_state['watchlist_force_refresh'] = True
            st.rerun()
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

    # 统一无点格式 + 名称解析（docs/082203 §6.1 修复 sh.600984 sh.600984）
    code = code.replace('.', '').strip()
    name = stock_dict.get(code, '')
    if not name:
        try:
            from db_manager import MysteryDB
            info = MysteryDB().get_stock_info(limit=None)
            if info is not None and not info.empty and 'code_name' in info.columns:
                for c, n in zip(info['code'], info['code_name']):
                    if str(c).replace('.', '') == code and n and str(n) != 'nan':
                        name = str(n)
                        break
        except Exception:
            pass
    if not name:
        name = code

    with st.spinner(f"正在分析 {code} {name} ..."):
        try:
            from db_manager import MysteryDB
            from datetime import datetime, timedelta
            db = MysteryDB()

# ===== 阶段1：日K（docs/082208 §4 分阶段 spinner） =====
            with st.spinner("① 加载日K..."):
                # 日 K 只拉一次：长窗口，分析与图表共用（docs/082205.md）
                kkey = f'kline_long_{code}'
                if kkey not in st.session_state:
                    start4y = (datetime.now() - timedelta(days=365 * 4)
                               ).strftime('%Y-%m-%d')
                    long_df = feeder.get_daily(code, start_date=start4y)
                    if long_df is None or long_df.empty:
                        # 无 start_date 再试一次（兼容部分源忽略 start_date）
                        long_df = feeder.get_daily(code)
                    if long_df is not None and not long_df.empty:
                        st.session_state[kkey] = long_df
                long_df = st.session_state.get(kkey)

                if long_df is None or long_df.empty:
                    st.error(f"❌ 无法获取 {code} 行情数据")
                    raise ValueError(f"无法获取 {code} 行情数据")

                # 分析用同一 DataFrame（指标已在 get_daily 内附带 MA）
                daily = long_df
                last_date = str(daily['日期'].max())[:10]

# ===== 阶段2：信号（含缓存，docs/082208 §4） =====
            with st.spinner("② 综合信号分析..."):
                # ===== 分析结果缓存（signal + 明细 ap/plat/det/cl，docs/082207.md） =====
                db_code = code[:2] + '.' + code[2:] if '.' not in code else code
                cached = db.get_analysis_cache(db_code, 'daily', last_date)
                ap = plat = det = cl = None
                if cached and cached.get('signal'):
                    signal = cached['signal']
                    ap = cached.get('ap') or {}
                    plat = cached.get('plat') or {}
                    det = cached.get('det') or {}
                    cl = cached.get('cl') or {}
                    st.caption(f"⚡ 命中分析缓存（最新交易日 {last_date}，"
                               f"含明细载荷，跳过重复计算）")
                else:
                    weekly = feeder.get_weekly(code)
                    # 大盘指数会话内只拉一次（指数获取走在线源较慢，避免每次分析卡顿）
                    if 'market_data_cache' not in st.session_state:
                        with st.spinner("加载大盘指数数据..."):
                            st.session_state['market_data_cache'] = \
                                feeder.get_market_index()
                    market_data = st.session_state['market_data_cache']
                    # 行业趋势：优先板块强度 map（session/模块缓存），否则仅 bool 缺失
                    # （docs/082206: 有板块名时应尽力算 bool，不双空）
                    industry_trend = None
                    industry_data = None
                    try:
                        ind_map = st.session_state.get('industry_map') or {}
                        cm = ind_map.get('code_map') or {}
                        ind_name = cm.get(db_code) or cm.get(code)
                        if ind_name:
                            from web.pages_util import build_sector_strength_map
                            if 'sector_strength_map' not in st.session_state:
                                st.session_state['sector_strength_map'] = \
                                    build_sector_strength_map()
                            smap = st.session_state['sector_strength_map'] or {}
                            score = smap.get(ind_name)
                            if score is not None:
                                # 与板块监控同一套得分：>0 视为向上
                                industry_trend = bool(float(score) > 0)
                    except Exception:
                        industry_trend = None

                    signal = logic.comprehensive_signal_analysis(
                        daily, weekly_data=weekly, market_data=market_data,
                        industry_data=industry_data,
                        industry_trend=industry_trend)

                    # 明细一次算完写入缓存（可 JSON 序列化，docs/082207.md）
                    try:
                        from analysis.adaptive_platform import (
                            analyze_adaptive_platform)
                        ap = analyze_adaptive_platform(
                            daily, stock_code=code, latest_only=True)
                    except Exception:
                        ap = {}
                    try:
                        plat = logic.platform_breakthrough_analysis(daily)
                    except Exception:
                        plat = {}
                    try:
                        det = logic.technical_detail_capture(daily)
                    except Exception:
                        det = {}
                    try:
                        cl = logic.main_bull_wave_checklist(daily)
                    except Exception:
                        cl = {}

                    db.set_analysis_cache(db_code, 'daily', last_date, {
                        'signal': signal,
                        'ap': ap,
                        'plat': plat,
                        'det': det,
                        'cl': cl,
                    })

        except Exception as e:
            import traceback
            _err = (e, traceback.format_exc())
        else:
            _err = None

    # 统一错误处理（spinner 块外，st.stop 不会卡住 spinner）
    if _err is not None:
        st.error(f"❌ 分析异常: {_err[0]}")
        st.code(_err[1])
        st.stop()

    # ★ 结果全部进 session，与 widget rerun 解耦（docs/082210）
    # 注意：不 st.stop() —— 让脚本继续执行到展示区，分析完成即自动渲染
    # （docs/082212: 修复"需切换股票才显示结果"——stop 中断导致本次 rerun 不渲染）
    st.session_state['stock_analysis'] = {
        'code': code, 'name': name, 'db_code': db_code,
        'last_date': last_date, 'industry_display': industry_display
        if 'industry_display' in dir() else '未知',
        'signal': signal, 'daily': daily, 'long_df': long_df,
        'ap': ap, 'plat': plat, 'det': det, 'cl': cl,
    }

# ---------- 展示区（与 button 解耦，docs/082210：切周期不重跑分析） ----------
ctx = st.session_state.get('stock_analysis')
if not ctx:
    st.info("请选择股票后点击「开始分析」")
    st.stop()

def _render_report(ctx):
    """渲染分析结果（docs/082210：ctx 来自 session，切周期仅重绘不重算）"""
    code = ctx['code']
    name = ctx['name']
    signal = ctx['signal']
    daily = ctx['daily']
    long_df = ctx['long_df']
    ap = ctx.get('ap') or {}
    plat = ctx.get('plat') or {}
    det = ctx.get('det') or {}
    cl = ctx.get('cl') or {}
    db_code = ctx['db_code']
    last_date = ctx['last_date']
    industry_display = ctx.get('industry_display', '未知')
    from db_manager import MysteryDB
    db = MysteryDB()

    st.success(f"✅ {code} {name} 分析完成（最新交易日 {last_date}）")
    # 所属板块（docs/082213: try 包裹+db兜底；行业优先——用户要求只显示一个时显示行业）
    industry_display = ''
    try:
        # 1. 行业板块优先（stock_industry_info.industry，session 缓存避免全量读）
        if 'ind_industry_map' not in st.session_state:
            try:
                row = db.get_stock_info(limit=None)
                _m = {}
                if row is not None and not row.empty and 'industry' in row.columns:
                    for c, ind in zip(row['code'].astype(str), row['industry']):
                        if ind and str(ind) != 'nan':
                            _m[str(c).replace('.', '')] = str(ind)
                st.session_state['ind_industry_map'] = _m
            except Exception:
                st.session_state['ind_industry_map'] = {}
        industry_display = st.session_state['ind_industry_map'].get(code, '')
        # 2. 行业缺失 → session industry_map（概念/多板块）
        if not industry_display:
            ind_map = st.session_state.get('industry_map') or {}
            cm = ind_map.get('code_map') or {}
            multi = ind_map.get('multi_map') or {}
            blocks = multi.get(db_code) or multi.get(code)
            if blocks:
                industry_display = '、'.join(str(b) for b in blocks if b)
            else:
                industry_display = cm.get(db_code) or cm.get(code) or ''
        if not industry_display:
            industry_display = '未知'
    except Exception:
        industry_display = '未知'
    st.info(f"🏢 所属板块: **{industry_display}**")

    # ---------- 1. 评分卡片 ----------
    st.subheader("🎯 评分概览")
    render_metric_cards(signal)
    st.subheader("🧭 三大心法与共振状态")
    render_detail_cards(signal)
    st.subheader("💡 操作建议")
    render_advice(signal)

    # ---------- 2. 财务数据（docs/ui2.md, 无缓存自动拉取；docs/082208 §4 阶段3） ----------
    st.subheader("💰 财务数据")
    with st.spinner("③ 加载财务..."):
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
    # 缓存未带齐明细时补算（兼容旧缓存仅含 signal，docs/082207.md）
    if not ap:
        try:
            from analysis.adaptive_platform import (
                analyze_adaptive_platform)
            ap = analyze_adaptive_platform(
                daily, stock_code=code, latest_only=True)
        except Exception as e:
            ap = {}
            st.caption(f"自适应平台: {e}")
    if not plat:
        try:
            plat = logic.platform_breakthrough_analysis(daily)
        except Exception:
            plat = {}
    if not det:
        try:
            det = logic.technical_detail_capture(daily)
        except Exception:
            det = {}
    if not cl:
        try:
            cl = logic.main_bull_wave_checklist(daily)
        except Exception:
            cl = {}

    # 震荡区间（自适应平台 + 平台箱体）
    p1, p2, p3 = st.columns(3)
    p1.metric("自适应平台 POC", ap.get('POC', 'N/A'))
    p2.metric("平台上轨", ap.get(
        '自适应上轨', ap.get('上轨', ap.get('upper', 'N/A'))))
    p3.metric("平台下轨", ap.get(
        '自适应下轨', ap.get('下轨', ap.get('lower', 'N/A'))))
    if plat.get('平台范围'):
        st.markdown(f"**震荡区间（平台箱体）**: {plat.get('平台范围')} "
                    f"| 状态: {plat.get('平台状态', '未知')}")
    # 筹码分析
    st.markdown(f"**筹码分析**: 集中度 {det.get('筹码集中度', '未知')} "
                f"| 趋势 {det.get('筹码趋势', '未知')}")
    # 主升浪8项指标对比表（docs/082210 §4: 固定 8 键展示，✅/❌ 来自 bool 键）
    st.subheader("📋 主升浪8项指标对比")
    CHECK_KEYS = [
        '长期横盘3个月以上',
        '60日均线开始向上',
        '股价突破平台',
        '放量超20日均量2倍',
        '回踩不破+MACD零轴金叉',
        'RSI>50继续走强',
        '主力资金连续流入',
        '行业板块同步走强',
    ]
    n_ok = sum(1 for k in CHECK_KEYS if cl.get(k))
    st.caption(
        f"满足 {cl.get('满足数量', n_ok)}/8 ｜ "
        f"综合判断: {cl.get('综合判断', '—')}")
    detail_lines = list(cl.get('详情') or [])
    for i, key in enumerate(CHECK_KEYS):
        ok = bool(cl.get(key))
        mark = "✅" if ok else "❌"
        extra = ""
        if i < len(detail_lines):
            extra = f" — {detail_lines[i]}"
        st.markdown(f"- {mark} {key}{extra}")
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

    # ---------- 3.0 展示对齐 pipeline（docs/082209 §2：板块涨跌/多周期/主升浪/平台全字段） ----------
    try:
        # 板块 5/10/20 日涨跌（优先板块指数K线，无则 N/A）
        from analysis.stock_pipeline import _sector_returns, _multi_period
        _sector_k = None
        try:
            ind_first = (industry_display or '未知').split('、')[0]
            if ind_first and ind_first != '未知':
                from db_manager import MysteryDB
                _sdb = MysteryDB()
                _smeta = dict((r[1], r[0]) for r in
                              _sdb.get_sector_meta(active_only=True))
                _s_code = _smeta.get(ind_first)
                if _s_code:
                    _sdf = _sdb.get_sector_kline(_s_code)
                    if _sdf is not None and not _sdf.empty:
                        _sector_k = _sdf
        except Exception:
            _sector_k = None
        _sec = _sector_returns(_sector_k)
        st.markdown("**板块强度（指数K线）**")
        st.markdown(
            f"- 近5日: **{_sec['板块近5日涨跌']}%**"
            f" | 近10日: **{_sec['板块近10日涨跌']}%**"
            f" | 近20日: **{_sec['板块近20日涨跌']}%**"
            f" | 趋势: {'📈 走强' if _sec['板块趋势'] else '📉 走弱' if _sec['板块趋势'] is not None else '—'}")
        # 多周期共振（与 main._analyze_multi_period 单票分支一致）
        _mp = _multi_period(wk, mo)
        st.markdown(
            f"- 周线: **{_mp['周线趋势']}**（最新 {_mp.get('周线最新价', '—')}，"
            f"MA20 {_mp.get('周线MA20', '—')}）"
            f" | 月线: **{_mp['月线趋势']}**（最新 {_mp.get('月线最新价', '—')}，"
            f"MA10 {_mp.get('月线MA10', '—')}）")
        st.markdown(
            f"- 多周期共振: **{'✅ 是' if _mp['多周期共振'] else '❌ 否'}**")
    except Exception as e:
        st.caption(f"板块/多周期: {e}")

    # 主升浪判定依据 + 平台全字段（pipeline 对齐，docs/082209 §2.4/2.5）
    try:
        _bull = logic.main_bull_wave_analysis(daily)
        _reasons = [x for x in (_bull.get('判定依据') or [])
                    if not str(x).startswith('判定结果')]
        while len(_reasons) < 3:
            _reasons.append('—')
        st.markdown("**主升浪分析**")
        st.markdown(
            f"- 状态: **{_bull.get('状态', _bull.get('主升浪状态', '未知'))}**"
            f" | 满足 {cl.get('满足数量', 0)}/8"
            f" | 综合判断: {cl.get('综合判断', '未知')}")
        for i, r in enumerate(_reasons, 1):
            st.markdown(f"- 判定依据{i}: {r}")
    except Exception as e:
        st.caption(f"主升浪: {e}")
    try:
        st.markdown("**平台突破分析**")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("平台状态", plat.get('平台状态', '未知'))
        box = plat.get('平台范围') or plat.get('平台箱体')
        p2.metric("平台箱体(近20日)", str(box) if box else "N/A")
        p3.metric("突破信号", "是" if plat.get('突破信号') else "否")
        p4.metric("买横信号", "是" if plat.get('买横信号') else "否")
    except Exception as e:
        st.caption(f"平台: {e}")

    # ---------- 3.1 技术指标表（Excel 对齐，docs/082203 设计约束） ----------
    try:
        from indicators.ma_indicators import MAIndicators
        from indicators.trend_indicators import TrendIndicators
        from indicators.momentum_indicators import MomentumIndicators
        ti = daily.copy()
        ti = MAIndicators().calculate_ma(ti)
        ti = TrendIndicators().calculate_macd(ti)
        ti = TrendIndicators().calculate_rsi(ti)
        ti = MomentumIndicators().calculate_volume_ratio(ti)
        last = ti.iloc[-1]
        ind_rows = [
            ('最新价', round(float(last['收盘价']), 2)),
            ('MA5', round(float(last.get('MA5', 0)), 2)),
            ('MA10', round(float(last.get('MA10', 0)), 2)),
            ('MA20', round(float(last.get('MA20', 0)), 2)),
            ('MA60', round(float(last.get('MA60', 0)), 2)),
            ('MA250', round(float(last.get('MA250', 0)), 2)
             if pd.notna(last.get('MA250')) else None),
            ('量比', round(float(last.get('量比', 0)), 2)),
            ('RSI', round(float(last.get('RSI', 0)), 2)),
            ('MACD', round(float(last.get('MACD', 0)), 2)),
            ('MACD_Signal', round(float(last.get(
                'MACD_Signal', 0)), 2)),
            ('换手率', round(float(last.get('换手率', 0) or 0), 2)),
        ]
        st.markdown(f"**技术指标（最新交易日 {last_date}）**")
        st.dataframe(pd.DataFrame(
            [{'指标': k, '数值': v} for k, v in ind_rows]),
            width="stretch", height=min(len(ind_rows) * 35 + 40, 420))
    except Exception as e:
        st.caption(f"技术指标表: {e}")

    # ---------- 3.2 财务指标表（Excel 对齐） ----------
    try:
        from data.financial_storage import FinancialStorage
        fin = FinancialStorage(MysteryDB()).ensure_financial(code)
        if not fin or not any(fin.get(k) for k in
                              ('pe', 'pb', 'roe')):
            # 兜底：同花顺估值快照（PE/PB 实时）
            from data.ths_client import ThsOfficialClient
            fin2 = ThsOfficialClient(cfg).fetch_financials(code)
            fin = {**fin, 'pe': fin.get('pe') or fin2.get('pe'),
                   'pb': fin.get('pb') or fin2.get('pb')}
        def _fmt(v):
            return '—' if v is None else (round(float(v), 2)
                                          if isinstance(v, (int, float)) else v)
        fin_rows = [
            ('ROE', _fmt(fin.get('roe'))),
            ('EPS', _fmt(fin.get('eps'))),
            ('PE', _fmt(fin.get('pe'))),
            ('PB', _fmt(fin.get('pb'))),
            ('股息率%', _fmt(fin.get('dividend_yield'))),
            ('报告期', fin.get('report_date') or
             fin.get('报告期') or '—'),
        ]
        st.markdown("**财务指标**")
        st.dataframe(pd.DataFrame(
            [{'指标': k, '数值': v} for k, v in fin_rows]),
            width="stretch", height=260)
    except Exception as e:
        st.caption(f"财务指标: {e}")

    # ---------- 3.3 三振共振 + 基础过滤详情（Excel 对齐） ----------
    st.markdown("**三振共振分析**")
    st.markdown(
        f"- 共振级别: **{signal.get('共振级别', '无共振')}**"
        f" | 共振评分: {signal.get('共振评分', 0)}"
        f" | 真三振: {'✅' if signal.get('真三振') else '❌'}")
    st.markdown(
        f"- 个股趋势: **{signal.get('个股趋势', '未知')}**"
        f" | 行业趋势: **{signal.get('行业趋势', '未知')}**"
        f" | 大盘趋势: **{signal.get('大盘趋势', '未知')}**")
    st.markdown("**基础过滤（年线滤网）**")
    st.markdown(
        f"- 年线滤网: {'✅ 通过' if signal.get('年线滤网') else '❌ 未通过'}"
        f" | 周线锚定: {'✅' if signal.get('周线锚定') else '❌'}"
        f" | 破五反五: {signal.get('破五反五', '未知')}")

    # ---------- 3.4 多周期分析详情（Excel 对齐） ----------
    st.markdown("**多周期分析**")
    try:
        w_close = float(wk['收盘价'].iloc[-1]) if wk is not None \
            and len(wk) else None
        w_ma5 = float(wk['收盘价'].tail(5).mean()) if wk is not None \
            and len(wk) else None
        w_ma10 = float(wk['收盘价'].tail(10).mean()) if wk is not None \
            and len(wk) else None
        w_ma20 = float(wk['收盘价'].tail(20).mean()) if wk is not None \
            and len(wk) else None
        if wk is not None and len(wk) >= 20:
            if w_ma5 > w_ma10 > w_ma20 and w_close > w_ma20:
                w_trend = '多头排列'
            elif w_ma5 < w_ma10 < w_ma20:
                w_trend = '空头排列'
            else:
                w_trend = '震荡整理'
        else:
            w_trend = '数据不足'
        m_close = float(mo['收盘价'].iloc[-1]) if mo is not None \
            and len(mo) else None
        m_ma5 = float(mo['收盘价'].tail(5).mean()) if mo is not None \
            and len(mo) else None
        m_ma10 = float(mo['收盘价'].tail(10).mean()) if mo is not None \
            and len(mo) else None
        if mo is not None and len(mo) >= 10:
            if m_ma5 > m_ma10 and m_close > m_ma10:
                m_trend = '多头排列'
            elif m_ma5 < m_ma10:
                m_trend = '空头排列'
            else:
                m_trend = '震荡整理'
        else:
            m_trend = '数据不足'
        st.markdown(
            f"- 周线: **{w_trend}**（最新 {w_close:.2f}，"
            f"MA20 {w_ma20:.2f}）" if w_close is not None
            else "- 周线: 数据不足")
        st.markdown(
            f"- 月线: **{m_trend}**（最新 {m_close:.2f}，"
            f"MA10 {m_ma10:.2f}）" if m_close is not None
            else "- 月线: 数据不足")
    except Exception as e:
        st.caption(f"多周期: {e}")

    # ---------- 4. K线图（最近1000交易日 + MA377/610 + EMA20，docs/081601.md） ----------
    st.subheader("📊 K线图（1000交易日 + MA377/610 + EMA20，日/周/月一次完成）")
    from indicators.ma_indicators import MAIndicators

    # long_df 已在分析入口拉取并写入 session，此处直接使用（docs/082205.md）
    long_df = st.session_state.get(f'kline_long_{code}', daily)

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
               'POC': (ap or {}).get('POC')}

    # 图表懒加载（docs/082208 §5: 默认只画日线；周/月按需生成）
    period_sel = st.radio(
        "周期",
        ["📅 日线", "📆 周线", "🗓️ 月线"],
        horizontal=True,
        key=f"kline_period_{code}",
    )
    with st.spinner("④ 绘制K线..."):
        if period_sel.startswith("📅"):
            st.plotly_chart(
                _prep_kline(long_df, day_box, max_bars=1000),
                width="stretch")
            st.caption(f"日线: 最近 {min(len(long_df), 1000)} 个交易日")
        elif period_sel.startswith("📆"):
            wk_long = rs.resample(long_df, 'weekly') \
                if long_df is not None else None
            if wk_long is not None and len(wk_long):
                w_hi = float(wk_long['最高价'].tail(20).max())
                w_lo = float(wk_long['最低价'].tail(20).min())
                st.plotly_chart(
                    _prep_kline(wk_long,
                                {'上沿': w_hi, '下沿': w_lo},
                                max_bars=200),
                    width="stretch")
                st.caption(f"周线: {w_lo:.2f} ~ {w_hi:.2f} | "
                           f"最新 {wk_long['收盘价'].iloc[-1]:.2f}")
            else:
                st.info("周线数据不足")
        else:
            mo_long = rs.resample(long_df, 'monthly') \
                if long_df is not None else None
            if mo_long is not None and len(mo_long):
                m_hi = float(mo_long['最高价'].tail(12).max())
                m_lo = float(mo_long['最低价'].tail(12).min())
                st.plotly_chart(
                    _prep_kline(mo_long,
                                {'上沿': m_hi, '下沿': m_lo},
                                max_bars=50),
                    width="stretch")
                st.caption(f"月线: {m_lo:.2f} ~ {m_hi:.2f} | "
                           f"最新 {mo_long['收盘价'].iloc[-1]:.2f}")
            else:
                st.info("月线数据不足")

    # ---------- 5. 分析详情 ----------
    st.subheader("📋 触发条件明细")
    for d in signal.get('详情', []):
        st.markdown(f"- {d}")

    # ---------- 6. 导出信号摘要（docs/082203 §6.2 无最近20日表） ----------
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
            pd.DataFrame([sig_row]),
            f"{code}_{name}_分析结果_{date.today()}.xlsx",
            button_label="📥 导出分析结果 Excel",
            sheet_name='信号摘要',
            key=f"export_analysis_{code}",
            help="信号摘要")
    except Exception as ex:
        st.caption(f"Excel导出不可用: {ex}")

# 函数定义后调用（docs/082210：切周期 rerun 时 button=False，直接渲染 session 结果）
if 'ctx' in dir() and ctx:
    _render_report(ctx)
