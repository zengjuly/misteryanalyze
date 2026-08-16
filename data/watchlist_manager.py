#!/usr/bin/env python3
# watchlist_manager.py - 独立自选股管理（SQLite，docs/081601.md §三）
"""自选股从真三振池剥离 → 独立管理
- watchlist 表（code, name, add_time, source, note）
- 与扫描/三振池解耦；真三振池只负责展示+一键加入自选
"""
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 与生产库一致（env MYSTERY_DB_PATH 优先）
def _default_db() -> str:
    env = os.environ.get('MYSTERY_DB_PATH')
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'data', 'mystery_cache.db')


class WatchlistManager:
    """自选股管理（SQLite 持久化）"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or _default_db()
        self._init_table()

    def _init_table(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS watchlist (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    add_time TEXT,
                    source TEXT DEFAULT 'manual',
                    note TEXT
                )
            ''')
            conn.commit()

    def add(self, code: str, name: str = '', source: str = 'manual',
            note: str = ''):
        """添加/更新自选（code 兼容 sh600150 / sh.600150 格式）"""
        code = self._normalize(code)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO watchlist '
                '(code, name, add_time, source, note) VALUES (?, ?, ?, ?, ?)',
                (code, name, datetime.now().isoformat(), source, note))
            conn.commit()

    def remove(self, code: str):
        code = self._normalize(code)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM watchlist WHERE code=?', (code,))
            conn.commit()

    def list_all(self) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                'SELECT code, name, add_time, source, note '
                'FROM watchlist ORDER BY add_time DESC', conn)

    def codes(self) -> List[str]:
        df = self.list_all()
        return df['code'].tolist() if not df.empty else []

    def exists(self, code: str) -> bool:
        code = self._normalize(code)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('SELECT 1 FROM watchlist WHERE code=?',
                               (code,))
            return cur.fetchone() is not None

    def count(self) -> int:
        return len(self.codes())

    @staticmethod
    def _normalize(code: str) -> str:
        """sh600150 / sh.600150 → sh.600150（db 标准格式）"""
        code = str(code).strip()
        if '.' in code:
            return code
        if len(code) >= 8:
            return code[:2] + '.' + code[2:]
        return code
