#!/usr/bin/env python3
# scan_store.py - 全市场扫描结果独立存储库（docs/081601.md §四 增强）
"""
全市场扫描结果独立数据库
========================
需求（用户）：
  1. 全市场扫描的结果单独存储一个数据库（不混入主行情库）
  2. 具备缓存功能：行情不更新时不需要重复执行扫描
  3. 后台扫描状态和结果有查看入口（Web 页3/页5）

设计：
  - 独立 SQLite 库 scan_results.db（env SCAN_RESULTS_DB_PATH 可覆盖，
    默认与主行情库同目录，生产环境自动落在 /home/ai/ai_runner/stock/data/db/）
  - 表：
    * scan_jobs   任务状态表（job_id PK / status / progress / params JSON /
                  trade_date 缓存键 / start_time / end_time / message / summary JSON）
    * scan_results 每只股票扫描明细（job_id + code 复合主键）
  - 缓存键 = (period, trade_date, enable_three_strike, enable_main_wave, scope)
    其中 trade_date 取主库 stock_kline_data 最新交易日 —— 行情没更新
    （同一天/非交易日/周末）时，相同参数的任务直接命中缓存，不重复扫描。
  - 兼容：旧版 scan_jobs 表在主行情库 DEFAULT_DB_PATH 中；本模块为新代码
    入口，Web 轮询/查看统一走这里（旧表不再写入，保留不删）。

用法:
  from data.scan_store import ScanStore
  store = ScanStore()
  job_id = store.create_job(params={'period': 'daily', 'limit': None, ...})
  store.update_job(job_id, progress=0.5)
  store.save_results(job_id, results)          # 逐批/逐只写入明细
  store.finish_job(job_id, summary=...)        # 完成/失败
  cached = store.find_cache(params)            # 命中缓存返回 job_id + 结果
  jobs = store.list_jobs()                     # 状态/结果查看入口数据
"""
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime

logger = logging.getLogger('scan_store')

# 生产数据目录：与主行情库同目录（MYSTERY_DB_PATH 指向的生产库路径）
def _default_db_path() -> str:
    mystery = os.environ.get('MYSTERY_DB_PATH', '')
    if mystery:
        return os.path.join(os.path.dirname(mystery), 'scan_results.db')
    # 项目内默认（开发环境，与开发缓存同目录）
    return os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'data', 'db', 'scan_results.db')


SCAN_RESULTS_DB_PATH = os.environ.get(
    'SCAN_RESULTS_DB_PATH', _default_db_path())


class ScanStore:
    """全市场扫描结果独立存储（scan_results.db）"""

    def __init__(self, db_path: str = SCAN_RESULTS_DB_PATH):
        self.db_path = db_path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    # ---------- 连接 ----------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute('PRAGMA journal_mode=WAL')
        return conn

    def _init_db(self):
        with self._lock, self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scan_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT,                -- running/finished/failed
                    progress REAL,              -- 0.0 ~ 1.0
                    params TEXT,                -- JSON {period, limit, sync_first,
                                                --       top_n, enable_three_strike,
                                                --       enable_main_wave, scope}
                    trade_date TEXT,            -- 缓存键：主库最新交易日
                    result_count INTEGER,       -- 结果明细条数
                    start_time TEXT,
                    end_time TEXT,
                    message TEXT,               -- 进度/结果摘要
                    summary TEXT                -- JSON {扫描数, 含信号, 真三振数, 耗时}
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scan_results (
                    job_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT,
                    industry TEXT,
                    score REAL,
                    signal TEXT,
                    three_score REAL,
                    true_three INTEGER,
                    three_level TEXT,
                    main_wave_hit INTEGER,
                    main_wave_judge TEXT,
                    breakout TEXT,
                    poc REAL,
                    upper REAL,
                    lower REAL,
                    platform TEXT,
                    chip TEXT,
                    chip_value REAL,
                    adaptive_n INTEGER,
                    price REAL,
                    trade_date TEXT,
                    PRIMARY KEY (job_id, code)
                )
            ''')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_jobs_status ON scan_jobs(status)')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_jobs_tradedate '
                'ON scan_jobs(trade_date)')
            conn.commit()

    # ---------- 任务状态 ----------
    def create_job(self, params: dict, trade_date: str = None) -> str:
        """创建后台扫描任务，返回 job_id"""
        import uuid
        job_id = str(uuid.uuid4())[:8]
        if trade_date is None:
            trade_date = self.get_market_trade_date()
        with self._lock, self._connect() as conn:
            conn.execute(
                'INSERT INTO scan_jobs (job_id, status, progress, params, '
                'trade_date, start_time, message) VALUES (?,?,?,?,?,?,?)',
                (job_id, 'running', 0.0,
                 json.dumps(params, ensure_ascii=False),
                 trade_date, datetime.now().isoformat(timespec='seconds'),
                 f"扫描 {params.get('period', 'daily')} 周期"
                 + ("（三振）" if params.get('enable_three_strike', True) else "")))
            conn.commit()
        return job_id

    def update_job(self, job_id: str, status: str = None, progress: float = None,
                   message: str = None):
        """更新任务状态（增量字段）"""
        sets, vals = [], []
        if status is not None:
            sets.append('status=?')
            vals.append(status)
        if progress is not None:
            sets.append('progress=?')
            vals.append(progress)
        if message is not None:
            sets.append('message=?')
            vals.append(message)
        if not sets:
            return
        vals.append(job_id)
        with self._lock, self._connect() as conn:
            conn.execute(f'UPDATE scan_jobs SET {", ".join(sets)} WHERE job_id=?',
                         vals)
            conn.commit()

    def finish_job(self, job_id: str, status: str = 'finished',
                   summary: dict = None, message: str = None):
        """完成任务（finished/failed），写入摘要与结束时间"""
        with self._lock, self._connect() as conn:
            conn.execute(
                'UPDATE scan_jobs SET status=?, progress=?, end_time=?, '
                'message=?, summary=? WHERE job_id=?',
                (status, 1.0 if status == 'finished' else 0.0,
                 datetime.now().isoformat(timespec='seconds'),
                 message or '',
                 json.dumps(summary or {}, ensure_ascii=False), job_id))
            conn.commit()

    def get_job(self, job_id: str) -> dict:
        """读取单个任务（含 params/summary 反序列化）"""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                'SELECT job_id, status, progress, params, trade_date, '
                'result_count, start_time, end_time, message, summary '
                'FROM scan_jobs WHERE job_id=?', (job_id,)).fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    def list_jobs(self, limit: int = 30) -> list:
        """任务历史列表（最新在前），供查看入口"""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT job_id, status, progress, params, trade_date, '
                'result_count, start_time, end_time, message, summary '
                'FROM scan_jobs ORDER BY start_time DESC LIMIT ?',
                (limit,)).fetchall()
        return [self._row_to_job(r) for r in rows]

    @staticmethod
    def _row_to_job(row) -> dict:
        keys = ('job_id', 'status', 'progress', 'params', 'trade_date',
                'result_count', 'start_time', 'end_time', 'message', 'summary')
        d = dict(zip(keys, row))
        try:
            d['params'] = json.loads(d['params'] or '{}')
        except Exception:
            d['params'] = {}
        try:
            d['summary'] = json.loads(d['summary'] or '{}')
        except Exception:
            d['summary'] = {}
        return d

    # ---------- 结果明细 ----------
    def save_results(self, job_id: str, results: list, trade_date: str = None):
        """写入扫描结果明细（INSERT OR REPLACE，可批量/逐批调用）
        字段映射兼容 run_market_scan.scan_single_stock 的返回字典
        """
        if not results:
            return
        if trade_date is None:
            trade_date = self.get_market_trade_date()
        with self._lock, self._connect() as conn:
            conn.executemany(
                'INSERT OR REPLACE INTO scan_results '
                '(job_id, code, name, industry, score, signal, three_score, '
                'true_three, three_level, main_wave_hit, main_wave_judge, '
                'breakout, poc, upper, lower, platform, chip, chip_value, '
                'adaptive_n, price, trade_date) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                [self._row_to_result(job_id, r, trade_date) for r in results])
            conn.execute(
                'UPDATE scan_jobs SET result_count=? WHERE job_id=?',
                (len(results), job_id))
            conn.commit()

    @staticmethod
    def _row_to_result(job_id: str, r: dict, trade_date: str) -> tuple:
        def f(v, default=None):
            if v is None:
                return default
            try:
                return float(v)
            except (TypeError, ValueError):
                return default
        return (
            job_id,
            str(r.get('股票代码', '')),
            str(r.get('股票名称', '') or ''),
            str(r.get('行业板块', '') or ''),
            f(r.get('综合评分')),
            str(r.get('信号', '') or ''),
            f(r.get('三振评分')),
            1 if r.get('真三振') else 0,
            str(r.get('三振级别', '') or ''),
            int(r.get('主升浪满足', 0) or 0),
            str(r.get('主升浪综合判断', '') or ''),
            str(r.get('突破信号', '') or ''),
            f(r.get('POC')),
            f(r.get('自适应上轨')),
            f(r.get('自适应下轨')),
            str(r.get('平台状态', '') or ''),
            str(r.get('筹码集中度', '') or ''),
            f(r.get('筹码集中度数值')),
            int(r.get('自适应N', 0) or 0),
            f(r.get('最新价')),
            trade_date,
        )

    def get_results(self, job_id: str) -> list:
        """读取某任务的全部扫描明细（dict 列表）"""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT code, name, industry, score, signal, three_score, '
                'true_three, three_level, main_wave_hit, main_wave_judge, '
                'breakout, poc, upper, lower, platform, chip, chip_value, '
                'adaptive_n, price, trade_date '
                'FROM scan_results WHERE job_id=? ORDER BY '
                'signal DESC, score DESC', (job_id,)).fetchall()
        keys = ('code', 'name', 'industry', 'score', 'signal', 'three_score',
                'true_three', 'three_level', 'main_wave_hit', 'main_wave_judge',
                'breakout', 'poc', 'upper', 'lower', 'platform', 'chip',
                'chip_value', 'adaptive_n', 'price', 'trade_date')
        out = []
        for r in rows:
            d = dict(zip(keys, r))
            d['true_three'] = bool(d['true_three'])
            out.append(d)
        return out

    def results_df(self, job_id: str):
        """读取结果为 pandas DataFrame（列名为中文，兼容页3/CSV）"""
        import pandas as pd
        rows = self.get_results(job_id)
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        return df.rename(columns={
            'code': '股票代码', 'name': '股票名称', 'industry': '行业板块',
            'score': '综合评分', 'signal': '信号', 'three_score': '三振评分',
            'true_three': '真三振', 'three_level': '三振级别',
            'main_wave_hit': '主升浪满足', 'main_wave_judge': '主升浪综合判断',
            'breakout': '突破信号', 'poc': 'POC', 'upper': '自适应上轨',
            'lower': '自适应下轨', 'platform': '平台状态', 'chip': '筹码集中度',
            'chip_value': '筹码集中度数值', 'adaptive_n': '自适应N',
            'price': '最新价', 'trade_date': '交易日',
        })

    def results_cn(self, job_id: str) -> list:
        """读取结果为中文列名字典列表（与 run_market_scan.scan_single_stock
        返回结构一致，供缓存命中复用/报告生成）"""
        rows = self.get_results(job_id)
        if not rows:
            return []
        cn = []
        for r in rows:
            cn.append({
                '股票代码': r['code'],
                '股票名称': r['name'],
                '行业板块': r['industry'],
                '综合评分': r['score'],
                '信号': r['signal'],
                '三振评分': r['three_score'],
                '真三振': r['true_three'],
                '三振级别': r['three_level'],
                '主升浪满足': r['main_wave_hit'],
                '主升浪综合判断': r['main_wave_judge'],
                '突破信号': r['breakout'],
                'POC': r['poc'],
                '自适应上轨': r['upper'],
                '自适应下轨': r['lower'],
                '平台状态': r['platform'],
                '筹码集中度': r['chip'],
                '筹码集中度数值': r['chip_value'],
                '自适应N': r['adaptive_n'],
                '最新价': r['price'],
            })
        return cn

    # ---------- 缓存 ----------
    @staticmethod
    def get_market_trade_date() -> str:
        """主库最新交易日（缓存键）—— 行情不更新时该值不变"""
        try:
            from data.db_manager import MysteryDB, DEFAULT_DB_PATH
            db = MysteryDB()
            conn = db._connect()
            try:
                row = conn.execute(
                    "SELECT MAX(date) FROM stock_kline_data WHERE period='daily'"
                ).fetchone()
                return str(row[0]) if row and row[0] else ''
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"⚠️ 获取市场交易日失败: {e}")
            return ''

    @staticmethod
    def _cache_key(params: dict) -> str:
        """缓存键：period + 三振/主升浪开关 + 扫描范围（limit 敏感）"""
        return json.dumps({
            'period': params.get('period', 'daily'),
            'enable_three_strike': params.get('enable_three_strike', True),
            'enable_main_wave': params.get('enable_main_wave', True),
            'limit': params.get('limit'),
        }, sort_keys=True, ensure_ascii=False)

    def find_cache(self, params: dict, trade_date: str = None) -> dict:
        """缓存查询：同参数 + 同最新交易日的已完成任务直接复用
        :return: {'job_id': ..., 'results': [...], 'summary': {...}} 或 None
        """
        if trade_date is None:
            trade_date = self.get_market_trade_date()
        if not trade_date:
            return None
        key = self._cache_key(params)
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                'SELECT job_id, summary, params FROM scan_jobs '
                'WHERE status="finished" AND trade_date=?',
                (trade_date,)).fetchall()
        for job_id, summary_json, params_json in rows:
            try:
                job_params = json.loads(params_json or '{}')
            except Exception:
                job_params = {}
            if self._cache_key(job_params) == key:
                results = self.results_cn(job_id)
                if results:
                    return {
                        'job_id': job_id,
                        'results': results,
                        'summary': json.loads(summary_json or '{}'),
                        'trade_date': trade_date,
                    }
        return None

    def stats(self) -> dict:
        """独立库统计（供系统状态页展示）"""
        with self._lock, self._connect() as conn:
            jobs = conn.execute('SELECT COUNT(*) FROM scan_jobs').fetchone()[0]
            finished = conn.execute(
                "SELECT COUNT(*) FROM scan_jobs WHERE status='finished'"
            ).fetchone()[0]
            results = conn.execute('SELECT COUNT(*) FROM scan_results').fetchone()[0]
        return {
            'db_path': self.db_path,
            'jobs': jobs,
            'finished': finished,
            'results': results,
            'size_mb': round(os.path.getsize(self.db_path) / 1024 / 1024, 2),
        }

    def close(self):
        pass


if __name__ == '__main__':
    # 自检
    store = ScanStore()
    print(f"📦 独立扫描结果库: {store.db_path}")
    print(f"   任务数={store.stats()['jobs']} 明细数={store.stats()['results']}")
    print(f"   最新交易日(缓存键)={ScanStore.get_market_trade_date()}")
    jobs = store.list_jobs(5)
    for j in jobs:
        print(f"   [{j['job_id']}] {j['status']} {j['trade_date']} "
              f"{j.get('message', '')[:50]}")
