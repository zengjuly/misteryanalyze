#!/usr/bin/env python3
# session.py - Web 会话状态管理（docs/ui.md §3.2）
"""统一的 st.session_state 读写工具 + 后端单例（DataFeeder/MysteryLogic）"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
for p in [_PROJECT_ROOT, os.path.join(_PROJECT_ROOT, 'data'),
          os.path.join(_PROJECT_ROOT, 'utils')]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st

_JSON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')


def get_state(key: str, default=None):
    """读取会话状态（不存在返回默认值）"""
    return st.session_state.get(key, default)


def set_state(key: str, value):
    """写入会话状态"""
    st.session_state[key] = value


def get_feeder():
    """获取 DataFeeder 单例（传 config 启用多源退避+缓存，否则单源 baostock 慢）"""
    from utils.data_feeder import DataFeeder
    if 'feeder' not in st.session_state:
        st.session_state['feeder'] = DataFeeder(get_config())
    return st.session_state['feeder']


def get_logic():
    """获取 MysteryLogic 单例"""
    from analysis.mystery_logic import MysteryLogic
    if 'logic' not in st.session_state:
        st.session_state['logic'] = MysteryLogic()
    return st.session_state['logic']


def get_config():
    """加载 config.yaml"""
    import yaml
    path = os.path.join(_PROJECT_ROOT, 'config', 'config.yaml')
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_scan_results():
    """读取最近一次扫描结果（JSON 文件，供真三振池页面）"""
    import json
    path = os.path.join(_JSON_DIR, 'scan_results.json')
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_scan_results(results: list):
    """保存扫描结果到 JSON（真三振池数据源）"""
    import json
    os.makedirs(_JSON_DIR, exist_ok=True)
    path = os.path.join(_JSON_DIR, 'scan_results.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


def load_watchlist():
    """读取自选股代码列表（docs/081601.md §三: SQLite WatchlistManager 统一）"""
    try:
        from data.watchlist_manager import WatchlistManager
        return WatchlistManager().codes()
    except Exception:
        # 兼容旧 JSON 数据
        import json
        path = os.path.join(_JSON_DIR, 'watchlist.json')
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []


def save_watchlist(watchlist: list):
    """保存自选股列表（SQLite WatchlistManager + 旧 JSON 兼容）"""
    try:
        from data.watchlist_manager import WatchlistManager
        wm = WatchlistManager()
        for c in watchlist:
            wm.add(c, source='manual')
    except Exception:
        import json
        os.makedirs(_JSON_DIR, exist_ok=True)
        path = os.path.join(_JSON_DIR, 'watchlist.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(watchlist, f, ensure_ascii=False, indent=1)
