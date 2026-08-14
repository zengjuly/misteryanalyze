#!/usr/bin/env python3
# app.py - Mystery趋势交易系统 Web 前端主入口（docs/ui.md）
"""Streamlit 多页面应用主入口
运行: streamlit run web/app.py --server.port 1888
"""
import os
import sys

# 项目根目录加入 sys.path（web/ 下独立运行）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in [_PROJECT_ROOT, os.path.join(_PROJECT_ROOT, 'data'),
          os.path.join(_PROJECT_ROOT, 'utils')]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st

st.set_page_config(
    page_title="Mystery趋势交易分析系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- 侧边栏 ----------
with st.sidebar:
    st.title("📈 Mystery趋势交易系统")
    st.caption("《Mistery趋势交易论》量化实现 v1.12.0")
    st.divider()
    st.markdown("""
**三大心法**
- 🧭 年线滤网：MA5/10/20/60 全在 MA250 之上
- ⚓ 周线锚定：周线稳居 60 周线之上
- 🔄 破五反五：破五 2 日内收回 + MA20 向上

**四维共振**
- 个股30 + 大盘25 + 行业25 + 资金20
""")
    st.divider()
    st.caption("⚠️ 分析结果仅供参考，不构成投资建议")

st.write("# 📈 Mystery趋势交易分析系统")
st.write("""
欢迎使用 Mystery 趋势交易分析系统！本系统基于《Mistery趋势交易论》量化实现，
左侧选择页面开始分析：

| 页面 | 功能 |
|------|------|
| **📈 个股分析** | 输入股票代码查看深度分析（评分卡片/K线/三大心法/四维共振） |
| **📊 板块监控** | 行业板块强度排名与成分股共振情况 |
| **🔍 全市场扫描** | 扫描股票池，筛选真三振/主升浪信号 |
| **💎 真三振池** | 最近扫描产出的真三振股票列表 |
| **⚙️ 系统状态** | 数据源健康/缓存信息/源健康报告 |

> 侧边栏也可直接选择页面。
""")
