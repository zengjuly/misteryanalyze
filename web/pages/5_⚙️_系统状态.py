#!/usr/bin/env python3
# 5_⚙️_系统状态.py - 系统状态页面（docs/ui.md §4.5）
"""数据源健康状态 / SQLite缓存信息 / 源健康报告生成"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), '..', 'data'))

import streamlit as st
import pandas as pd

st.set_page_config(page_title="系统状态", page_icon="⚙️", layout="wide")

from web.utils.session import get_config

st.title("⚙️ 系统状态")
st.caption("数据源健康 / 缓存信息 / 源健康报告")

cfg = get_config()

# ---------- 1. 数据源健康 ----------
st.subheader("🩺 数据源健康状态")
try:
    from market_data_client import MarketDataClient
    mc = MarketDataClient(cfg)
    stats = mc.source_health.get_source_stats()
    rows = []
    for src, s in stats.items():
        rows.append({
            '数据源': src,
            '健康分': s.get('health_score', 0),
            '成功率': f"{s.get('success_rate', 0):.0%}",
            '连续失败': s.get('consecutive_failures', 0),
            '熔断': '🔴' if not s.get('is_open', True) else '🟢',
            '总请求': s.get('total', 0),
            '平均耗时(ms)': round(s.get('avg_latency_ms', 0), 1),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch")
    else:
        st.info("暂无数据源健康统计（尚无请求记录）")
except Exception as e:
    st.warning(f"⚠️ 数据源健康状态获取失败: {e}")

# ---------- 2. SQLite 缓存信息 ----------
st.subheader("🗄️ SQLite 缓存信息")
try:
    from db_manager import MysteryDB, DEFAULT_DB_PATH
    db = MysteryDB()
    conn = db._connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT code) FROM stock_kline_data")
    total_rows, total_codes = cur.fetchone()
    cur.execute("SELECT MAX(date) FROM stock_kline_data WHERE period='daily'")
    last_date = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM stock_industry_info")
    stock_info = cur.fetchone()[0]
    conn.close()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("缓存路径", DEFAULT_DB_PATH.split('/')[-2] + '/'
              + os.path.basename(DEFAULT_DB_PATH))
    c2.metric("K线总行数", f"{total_rows:,}")
    c3.metric("覆盖股票数", f"{total_codes:,}")
    c4.metric("最新数据日期", str(last_date))
    st.caption(f"证券信息表: {stock_info} 条 · 数据库大小: "
               f"{os.path.getsize(DEFAULT_DB_PATH) / 1024 / 1024:.1f} MB")
except Exception as e:
    st.warning(f"⚠️ 缓存信息获取失败: {e}")

# ---------- 3. 源健康报告 ----------
st.subheader("📄 源健康报告")
if st.button("🔄 生成源健康报告"):
    try:
        from source_report import generate_source_report
        outdir = os.environ.get('SOURCE_REPORT_DIR',
                                os.path.join(os.path.dirname(
                                    os.path.dirname(os.path.abspath(__file__))),
                                    '..', 'logs'))
        os.makedirs(outdir, exist_ok=True)
        path = generate_source_report(mc.source_health, output_dir=outdir)
        st.success(f"✅ 报告已生成: {path}")
        with open(path, encoding='utf-8') as f:
            rep = json.load(f)
        st.json(rep)
    except Exception as e:
        st.error(f"❌ 报告生成失败: {e}")

st.caption(f"🕐 页面加载时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
