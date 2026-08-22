#!/usr/bin/env python3
# 6_⭐_自选股.py - 自选股管理页面（docs/081601.md §三，从三振池剥离独立）
"""模糊搜索添加自选 + 列表管理（删除/来源筛选/CSV导出）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from streamlit_searchbox import st_searchbox

st.set_page_config(page_title="自选股", page_icon="⭐", layout="wide")

from web.utils.session import get_config, get_feeder


def _search_options(searchterm: str):
    """模糊搜索（代码/名称）"""
    if not searchterm or len(searchterm.strip()) < 1:
        return []
    try:
        feeder = get_feeder()
        d = feeder.get_all_stock_code_name()
        term = searchterm.strip().lower()
        hits = []
        for code, name in d.items():
            if term in code.lower() or (name and term in str(name).lower()):
                hits.append(f"{code} - {name}")
            if len(hits) >= 20:
                break
        return hits
    except Exception:
        return []


st.title("⭐ 自选股管理")
st.caption("独立自选股（与真三振池解耦，docs/081601.md）："
           "可手动添加、从真三振一键加入、筛选来源、导出 CSV")

from data.watchlist_manager import WatchlistManager
wm = WatchlistManager()

# 名称字典（docs/082213 修复: 自选股 name 回填——tdx 同步/显示补名用）
def _build_name_map():
    try:
        import sys as _s
        _s.path.insert(0, _s.path[0] or '.')
        from data.data_feeder import DataFeeder
        import yaml as _y
        _cfg = _y.safe_load(open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config', 'config.yaml'), encoding='utf-8'))
        d = DataFeeder(_cfg).get_all_stock_code_name()
        return {str(k).replace('.', ''): v for k, v in d.items()}
    except Exception:
        return {}
NAME_MAP = _build_name_map()

# ---------- 从通达信安装目录同步自选股（docs 2026-08-17） ----------
st.caption("📂 支持从通达信安装目录（T0002/blocknew/zxg.blk）一键同步自选股")
sync_c1, sync_c2, sync_c3 = st.columns([1, 1, 2])
with sync_c1:
    if st.button("📂 从通达信同步自选股", type="primary"):
        try:
            from data.tdx_watchlist_sync import (sync_from_tdx,
                                                 resolve_tdx_home)
            home = resolve_tdx_home() or "未定位"
            with st.spinner(f"正在从通达信同步（{home}）..."):
                res = sync_from_tdx(mode='merge', name_map=NAME_MAP)
            if res['total'] > 0:
                st.success(f"✅ 已从通达信同步 {res['total']} 只自选股"
                           f"（新增 {res['synced']} 只，"
                           f"当前共 {res['watchlist']} 只）")
                st.rerun()
            else:
                st.warning(f"⚠️ 未解析到自选股（{home}），"
                           f"请确认通达信安装目录存在 zxg.blk")
        except Exception as e:
            st.error(f"❌ 同步失败: {e}")
with sync_c2:
    if st.button("♻️ 全量替换（以通达信为准）"):
        try:
            from data.tdx_watchlist_sync import sync_from_tdx
            with st.spinner("正在全量替换..."):
                res = sync_from_tdx(mode='replace', name_map=NAME_MAP)
            st.success(f"✅ 全量替换完成: TDX {res['total']} 只，"
                       f"当前共 {res['watchlist']} 只")
            st.rerun()
        except Exception as e:
            st.error(f"❌ 替换失败: {e}")

# ---------- 添加（搜索框在 form 外——自定义组件与 form 兼容问题，docs/081601.md） ----------
selected = st_searchbox(
    _search_options, key="watch_searchbox",
    label="🔍 股票搜索（代码/名称）",
    placeholder="输入代码或名称，如 600150 / 中国船舶")
with st.form("add_form"):
    note = st.text_input("备注（可选）")
    if st.form_submit_button("➕ 添加自选"):
        if selected:
            code = str(selected).split(' - ')[0].strip()
            name = str(selected).split(' - ')[1].strip() \
                if ' - ' in str(selected) else ''
            wm.add(code, name=name, source='manual', note=note)
            st.success(f"✅ 已添加自选: {code} {name}")
        else:
            st.warning("请先选择股票")

# ---------- 列表 ----------
st.subheader("📋 自选股列表")
src_filter = st.selectbox("来源筛选", ["全部", "手动", "真三振", "扫描"],
                          key="wl_src_filter")
df = wm.list_all()
if df.empty:
    st.info("暂无自选股")
else:
    if src_filter != "全部":
        df = df[df['source'] == src_filter]
    if df.empty:
        st.info(f"无「{src_filter}」来源的自选股")
    else:
        # 名称补全（docs/082213: 旧数据 name 空时从名称字典兜底）
        if 'name' in df.columns:
            df = df.copy()
            df['name'] = df.apply(
                lambda r: (r['name'] if r.get('name') else '')
                or NAME_MAP.get(str(r['code']).replace('.', ''), ''),
                axis=1)
        st.dataframe(df, width="stretch")
        # 名称显示（代码-名称）
        st.markdown("**当前自选：** " + "、".join(
            f"{r['code']}" + (f"({r['name']})" if r.get('name') else '')
            for _, r in df.iterrows()))
        # 删除
        del_cols = st.columns(4)
        with del_cols[0]:
            del_code = st.text_input("输入代码删除")
        with del_cols[1]:
            if st.button("🗑️ 删除"):
                if del_code:
                    wm.remove(del_code.strip())
                    st.success(f"已删除 {del_code}")
                    st.rerun()
                else:
                    st.warning("请输入代码")
        with del_cols[2]:
            if st.button("🧹 清空全部"):
                for c in wm.codes():
                    wm.remove(c)
                st.success("已清空")
                st.rerun()
        with del_cols[3]:
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("⬇️ 导出 CSV", csv,
                               file_name="watchlist.csv",
                               mime="text/csv")
