#!/usr/bin/env python3
# db_manager.py - SQLite本地缓存数据库管理（基于docs/gemmi_an.md数据中枢方案）
"""
Mystery 趋势交易系统 - 数据库缓存层
====================================
理论来源: docs/gemmi_an.md（数据中枢与全量自动化分析方案）

核心设计:
  - SQLite 本地缓存 (mystery_cache.db)，解决频繁调用 baostock API 慢的问题
  - 联合主键 (code, date, period) + 覆盖索引，百万级数据毫秒级加载
  - safe_upsert 线程安全增量写入（Cache-Aside 旁路缓存模式的落库端）

三张核心表:
  1. stock_industry_info  : 证券代码/名称/类型/行业分类（主键 code）
  2. stock_kline_data     : 核心行情表（code,date,period联合主键，日/周/月线）
  3. stock_financial_data : 基本面快照（code,report_date 联合主键）
"""

import os
import sqlite3
import logging
import threading
from typing import Dict, List, Optional, Any

import pandas as pd

logger = logging.getLogger(__name__)

# 数据库默认路径（环境变量 MYSTERY_DB_PATH 可覆盖，docs/step3.md 路径统一）
_DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'mystery_cache.db')
DEFAULT_DB_PATH = os.environ.get('MYSTERY_DB_PATH', _DEFAULT_DB)


class MysteryDB:
    """SQLite 数据库管理器（线程安全）"""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        # 确保目录存在
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._lock = threading.RLock()  # 线程安全写锁
        self._init_db()

    # ============ 建表与初始化 ============
    def _init_db(self):
        """初始化数据库表结构"""
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript("""
                -- 1. 证券信息表（代码/名称/类型/行业）
                CREATE TABLE IF NOT EXISTS stock_industry_info (
                    code        TEXT PRIMARY KEY,        -- 证券代码 sh.600150
                    code_name   TEXT,                    -- 证券名称 中国船舶
                    ipo_date    TEXT,                    -- 上市日期
                    out_date    TEXT,                    -- 退市日期
                    type        TEXT,                    -- 类型 1股票 2指数 3其他
                    status      TEXT,                    -- 状态 1上市 0退市
                    industry    TEXT                     -- 行业分类（行业表补充）
                );

                -- 2. 核心行情表（联合主键，日/周/月线合并存储）
                CREATE TABLE IF NOT EXISTS stock_kline_data (
                    code      TEXT NOT NULL,             -- 证券代码 sh.600150
                    date      TEXT NOT NULL,             -- 交易日期 2026-08-12
                    period    TEXT NOT NULL,             -- 周期 daily/weekly/monthly
                    open      REAL,                      -- 开盘价
                    high      REAL,                      -- 最高价
                    low       REAL,                      -- 最低价
                    close     REAL,                      -- 收盘价
                    preclose  REAL,                      -- 前收盘
                    volume    REAL,                      -- 成交量（股）
                    amount    REAL,                      -- 成交额（元）
                    adjustflag REAL,                     -- 复权状态 1后复权 2前复权 3不复权
                    turn      REAL,                      -- 换手率(%)
                    tradestatus REAL,                    -- 交易状态 1正常 0停牌
                    pctChg    REAL,                      -- 涨跌幅(%)
                    isST      REAL,                      -- 是否ST 1是 0否
                    PRIMARY KEY (code, date, period)
                );

                -- 核心行情快速查询覆盖索引（code+period 定位，date 排序）
                CREATE INDEX IF NOT EXISTS idx_kline_fast_query
                    ON stock_kline_data (code, period, date);

                -- 3. 基本面快照表
                CREATE TABLE IF NOT EXISTS stock_financial_data (
                    code         TEXT NOT NULL,          -- 证券代码
                    report_date  TEXT NOT NULL,          -- 报告期 2026-03-31
                    roe          REAL,                   -- 净资产收益率(%)
                    roe_avg      REAL,                   -- 加权ROE(%)
                    np_margin    REAL,                   -- 净利率(%)
                    gp_margin    REAL,                   -- 毛利率(%)
                    net_profit   REAL,                   -- 净利润
                    eps_ttm      REAL,                   -- 每股收益TTM
                    PB           REAL,                   -- 市净率（估值补充）
                    PE           REAL,                   -- 市盈率
                    divid_cash   REAL,                   -- 每股税前现金分红
                    PRIMARY KEY (code, report_date)
                );

                -- 基本面查询索引
                CREATE INDEX IF NOT EXISTS idx_financial_query
                    ON stock_financial_data (code, report_date DESC);

                -- 4. 分析结果缓存表（docs/ui2.md 二级缓存: 行情未更新不重复分析）
                CREATE TABLE IF NOT EXISTS mystery_analysis_cache (
                    stock_code      TEXT NOT NULL,   -- 证券代码 sh.600150
                    period          TEXT NOT NULL,   -- daily/full_scan
                    last_trade_date TEXT NOT NULL,   -- 最新K线日期 YYYY-MM-DD
                    report_json     TEXT NOT NULL,   -- 分析结果JSON
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (stock_code, period, last_trade_date)
                );

                -- 5. 行业板块指数行情表（docs/082202.md 真实指数，非个股抽样）
                CREATE TABLE IF NOT EXISTS sector_kline (
                    sector_code TEXT NOT NULL,      -- ths_881155 / tdx_880301
                    sector_name TEXT NOT NULL,      -- 板块名称（半导体）
                    trade_date  TEXT NOT NULL,      -- YYYY-MM-DD
                    open REAL NOT NULL, high REAL NOT NULL,
                    low REAL NOT NULL, close REAL NOT NULL,
                    volume INTEGER NOT NULL, amount REAL NOT NULL,
                    source_type TEXT DEFAULT 'ths', -- ths(扶摇) / tdx(通达信)
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (sector_code, trade_date)
                );
                CREATE INDEX IF NOT EXISTS idx_sector_kline_date
                    ON sector_kline (trade_date, sector_code);
                CREATE INDEX IF NOT EXISTS idx_sector_kline_code_date
                    ON sector_kline (sector_code, trade_date DESC);

                -- 6. 板块元数据表（sector_meta: 分类/成分状态/增量断点）
                CREATE TABLE IF NOT EXISTS sector_meta (
                    sector_code TEXT PRIMARY KEY,
                    sector_name TEXT NOT NULL,
                    parent_type TEXT,               -- 行业/概念/申万一级
                    base_code TEXT,                 -- 官方原始代码 881155
                    is_active INTEGER DEFAULT 1,
                    last_sync_date TEXT             -- 增量同步断点 YYYY-MM-DD
                );
                """)
                conn.commit()
                logger.debug(f"✅ 数据库初始化完成: {self.db_path}")
            finally:
                conn.close()

    def _connect(self) -> sqlite3.Connection:
        """建立连接（check_same_thread=False 支持多线程读取）"""
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")   # WAL模式提升并发读写
        return conn

    # ============ 证券信息 ============
    def upsert_stock_info(self, df: pd.DataFrame) -> int:
        """批量写入/更新证券信息（code主键）"""
        if df is None or df.empty:
            return 0
        with self._lock:
            conn = self._connect()
            try:
                rows = []
                for _, r in df.iterrows():
                    rows.append((
                        str(r.get('code', '')),
                        str(r.get('code_name', '') or ''),
                        str(r.get('ipoDate', '') or ''),
                        str(r.get('outDate', '') or ''),
                        str(r.get('type', '') or ''),
                        str(r.get('status', '') or ''),
                    ))
                conn.executemany("""
                    INSERT OR REPLACE INTO stock_industry_info
                    (code, code_name, ipo_date, out_date, type, status)
                    VALUES (?,?,?,?,?,?)
                """, rows)
                conn.commit()
                return len(rows)
            finally:
                conn.close()

    def update_industry(self, code: str, industry: str):
        """更新单只股票的行业分类"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE stock_industry_info SET industry=? WHERE code=?",
                    (industry, code))
                conn.commit()
            finally:
                conn.close()

    def update_industries(self, code_industry: Dict[str, str]) -> int:
        """批量更新行业分类（docs/ui2.md 板块数据填充）
        :param code_industry: {code: industry}
        :return: 更新条数
        """
        if not code_industry:
            return 0
        with self._lock:
            conn = self._connect()
            try:
                rows = [(ind, code) for code, ind in code_industry.items()
                        if code and ind]
                conn.executemany(
                    "UPDATE stock_industry_info SET industry=? WHERE code=?",
                    rows)
                conn.commit()
                return len(rows)
            finally:
                conn.close()

    # ============ 行业板块指数（docs/082202.md 真实指数） ============
    def get_sector_kline(self, sector_code: str,
                         start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
        """读取板块指数K线（sector_kline，真实指数非个股抽样）"""
        with self._lock:
            conn = self._connect()
            try:
                sql = ("SELECT trade_date, open, high, low, close, "
                       "volume, amount FROM sector_kline "
                       "WHERE sector_code=?")
                params = [sector_code]
                if start_date:
                    sql += " AND trade_date>=?"
                    params.append(start_date)
                if end_date:
                    sql += " AND trade_date<=?"
                    params.append(end_date)
                sql += " ORDER BY trade_date"
                df = pd.read_sql_query(sql, conn, params=params)
                if df.empty:
                    return df
                df = df.rename(columns={'trade_date': '日期'})
                df['日期'] = pd.to_datetime(df['日期'])
                return df
            finally:
                conn.close()

    def load_all_sector_kline(self) -> pd.DataFrame:
        """读取全部板块指数K线（sector_kline 全表，含 sector_code/sector_name，
        docs/082210: 板块强度秒级本地计算用）"""
        with self._lock:
            conn = self._connect()
            try:
                return pd.read_sql_query(
                    "SELECT sector_code, sector_name, trade_date, open, "
                    "high, low, close, volume, amount FROM sector_kline "
                    "ORDER BY sector_code, trade_date", conn)
            finally:
                conn.close()

    def save_sector_kline(self, sector_code: str, sector_name: str,
                          df: pd.DataFrame, source_type: str = 'ths') -> int:
        """批量写入板块指数K线（INSERT OR REPLACE，幂等）
        注意：成交量可能为 NaN（个别板块缺失）→ 容错为 0（修复 886082 类失败）
        """
        if df is None or df.empty:
            return 0
        rows = []
        for _, r in df.iterrows():
            def _f(v, default=0.0):
                try:
                    v = float(v)
                    return v if not pd.isna(v) else default
                except (TypeError, ValueError):
                    return default
            vol = _f(r.get('成交量', 0), 0)
            rows.append((sector_code, sector_name,
                         pd.to_datetime(r['日期']).strftime('%Y-%m-%d'),
                         _f(r.get('开盘价')), _f(r.get('最高价')),
                         _f(r.get('最低价')), _f(r.get('收盘价')),
                         int(vol), _f(r.get('成交额')), source_type))
        with self._lock:
            conn = self._connect()
            try:
                conn.executemany(
                    """INSERT OR REPLACE INTO sector_kline
                       (sector_code, sector_name, trade_date, open, high,
                        low, close, volume, amount, source_type)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""", rows)
                conn.commit()
                return len(rows)
            finally:
                conn.close()

    def get_sector_meta(self, active_only: bool = True) -> list:
        """读取板块元数据（sector_meta）"""
        with self._lock:
            conn = self._connect()
            try:
                sql = "SELECT sector_code, sector_name, last_sync_date FROM sector_meta"
                if active_only:
                    sql += " WHERE is_active=1"
                return conn.execute(sql).fetchall()
            finally:
                conn.close()

    def upsert_sector_meta(self, code: str, name: str,
                           parent_type: str = None,
                           base_code: str = None) -> None:
        """写入/更新板块元数据"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO sector_meta
                       (sector_code, sector_name, parent_type, base_code)
                       VALUES (?,?,?,?)""",
                    (code, name, parent_type, base_code))
                conn.commit()
            finally:
                conn.close()

    def update_sector_sync_date(self, sector_code: str,
                                last_date: str) -> None:
        """更新板块增量同步断点"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "UPDATE sector_meta SET last_sync_date=? "
                    "WHERE sector_code=?", (last_date, sector_code))
                conn.commit()
            finally:
                conn.close()

    def get_stock_info(self, limit: int = None, stock_only: bool = True,
                       listed_only: bool = True) -> pd.DataFrame:
        """
        读取证券信息
        :param limit: 限制条数
        :param stock_only: 仅股票（type=1）
        :param listed_only: 仅上市（status=1）
        """
        with self._lock:
            conn = self._connect()
            try:
                sql = "SELECT * FROM stock_industry_info WHERE 1=1"
                if stock_only:
                    sql += " AND type='1'"
                if listed_only:
                    sql += " AND status='1'"
                sql += " ORDER BY code"
                if limit:
                    sql += f" LIMIT {int(limit)}"
                df = pd.read_sql_query(sql, conn)
                return df
            finally:
                conn.close()

    # ============ 行情数据 ============
    # 中文列名 → 英文列名（兼容 TdxIncremental / 各数据源中文输出）
    CN_TO_EN = {
        '日期': 'date', '开盘价': 'open', '最高价': 'high', '最低价': 'low',
        '收盘价': 'close', '成交量': 'volume', '成交额': 'amount',
        '换手率': 'turn', '涨跌幅': 'pctChg', '代码': 'code',
        '前收盘': 'preclose', '复权因子': 'adjustflag', '交易状态': 'tradestatus',
        '是否ST': 'isST',
    }

    @classmethod
    def _normalize_kline_cols(cls, df: pd.DataFrame) -> pd.DataFrame:
        """将DataFrame列名统一为英文（兼容中文/英文混合输入）"""
        if df is None or df.empty:
            return df
        df = df.copy()
        df = df.rename(columns=cls.CN_TO_EN)
        # 删除残留中文列（避免重复列）
        for cn in cls.CN_TO_EN:
            if cn in df.columns:
                df = df.drop(columns=[cn])
        # 去重列名安全兜底
        return df.loc[:, ~df.columns.duplicated()]

    def get_last_date(self, code: str, period: str = 'daily') -> Optional[str]:
        """获取指定股票某周期的最大日期（增量更新锚点）"""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT MAX(date) FROM stock_kline_data WHERE code=? AND period=?",
                    (code, period))
                row = cur.fetchone()
                return row[0] if row and row[0] else None
            finally:
                conn.close()

    def get_trading_calendar(self) -> List[str]:
        """从缓存日K生成全市场交易日历（所有daily日期去重升序）"""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT DISTINCT date FROM stock_kline_data "
                    "WHERE period='daily' ORDER BY date")
                return [r[0] for r in cur.fetchall()]
            finally:
                conn.close()

    def upsert_kline(self, df: pd.DataFrame, code: str, period: str,
                     max_rows: int = None) -> int:
        """
        线程安全增量写入行情（(code,date,period)联合主键，INSERT OR REPLACE）
        :param df: 含 date/open/high/low/close/volume/amount/turn 等列的DataFrame
                   （兼容中文列名：日期/开盘价/...，自动转换）
        :param code: 证券代码（9位 sh.600150）
        :param period: 周期 daily/weekly/monthly
        :param max_rows: 可选，写入后仅保留最新max_rows条（循环覆盖）
        """
        if df is None or df.empty:
            return 0
        # 列名统一为英文（兼容中文/英文混合输入）
        df = self._normalize_kline_cols(df)
        with self._lock:
            conn = self._connect()
            try:
                rows = []
                for _, r in df.iterrows():
                    rows.append((
                        code, str(r.get('date', '')), period,
                        self._f(r.get('open')), self._f(r.get('high')),
                        self._f(r.get('low')), self._f(r.get('close')),
                        self._f(r.get('preclose')), self._f(r.get('volume')),
                        self._f(r.get('amount')), self._f(r.get('adjustflag')),
                        self._f(r.get('turn')), self._f(r.get('tradestatus')),
                        self._f(r.get('pctChg')), self._f(r.get('isST')),
                    ))
                conn.executemany("""
                    INSERT OR REPLACE INTO stock_kline_data
                    (code, date, period, open, high, low, close, preclose,
                     volume, amount, adjustflag, turn, tradestatus, pctChg, isST)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                conn.commit()
                # 循环覆盖：限制该股票该周期保留条数
                if max_rows and max_rows > 0:
                    self.trim_kline(code, period, max_rows)
                return len(rows)
            finally:
                conn.close()

    def trim_kline(self, code: str, period: str = 'daily',
                   max_rows: int = 2000) -> int:
        """
        删除旧数据，仅保留最新 max_rows 条（循环覆盖，控制存储成本）
        :param code: 证券代码
        :param period: 周期 daily/weekly/monthly
        :param max_rows: 保留最大条数
        :return: 删除的行数
        """
        if not max_rows or max_rows <= 0:
            return 0
        with self._lock:
            conn = self._connect()
            try:
                # 快速路径: 行数未超限时无需裁剪（避免每次同步都执行大DELETE解析）
                cnt = conn.execute(
                    "SELECT COUNT(*) FROM stock_kline_data "
                    "WHERE code=? AND period=?", (code, period)).fetchone()[0]
                if cnt <= max_rows:
                    return 0
                # 找出应保留的最新 max_rows 条日期
                keep_dates = conn.execute(
                    "SELECT date FROM stock_kline_data "
                    "WHERE code=? AND period=?"
                    "ORDER BY date DESC LIMIT ?",
                    (code, period, max_rows)).fetchall()
                if not keep_dates:
                    return 0
                keep_set = {r[0] for r in keep_dates}
                # 删除不在保留集合中的旧数据
                cur = conn.execute(
                    """DELETE FROM stock_kline_data
                       WHERE code=? AND period=? AND date NOT IN (%s)"""
                    % ",".join("?" * len(keep_set)),
                    [code, period] + list(keep_set))
                conn.commit()
                deleted = cur.rowcount
                if deleted > 0:
                    logger.debug(f"🗑️ {code} {period} 清理旧数据 {deleted} 条"
                                 f"（保留最近{max_rows}条）")
                return deleted
            finally:
                conn.close()

    @staticmethod
    def _f(v) -> Optional[float]:
        """转换为float或None"""
        if v is None or pd.isna(v):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def load_kline(self, code: str, period: str = 'daily',
                   start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        从本地缓存读取行情（毫秒级，覆盖索引 idx_kline_fast_query）
        :param code: 证券代码
        :param period: 周期 daily/weekly/monthly
        :param start_date: 起始日期 YYYY-MM-DD
        :param end_date: 截止日期
        :return: 按日期升序的DataFrame（列名与baostock一致）
        """
        with self._lock:
            conn = self._connect()
            try:
                sql = ("SELECT date, code, open, high, low, close, preclose, "
                       "volume, amount, adjustflag, turn, tradestatus, pctChg, isST "
                       "FROM stock_kline_data WHERE code=? AND period=?")
                params: List[Any] = [code, period]
                if start_date:
                    sql += " AND date>=?"
                    params.append(start_date)
                if end_date:
                    sql += " AND date<=?"
                    params.append(end_date)
                sql += " ORDER BY date ASC"
                df = pd.read_sql_query(sql, conn, params=params)
                return df
            finally:
                conn.close()

    def get_cached_tickers(self, period: str = 'daily') -> List[str]:
        """获取缓存中有行情数据的股票代码列表"""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT DISTINCT code FROM stock_kline_data WHERE period=?",
                    (period,))
                return [r[0] for r in cur.fetchall()]
            finally:
                conn.close()

    # ============ 分析结果缓存（docs/ui2.md 二级缓存） ============
    def get_analysis_cache(self, stock_code: str, period: str,
                           last_trade_date: str) -> Optional[Dict]:
        """读取分析结果缓存（行情未更新时直接复用，避免重复分析）
        :param stock_code: sh.600150
        :param period: daily/weekly/monthly/full_scan
        :param last_trade_date: 最新K线日期（缓存键的一部分）
        :return: 分析结果 dict 或 None
        """
        import json
        if not last_trade_date:
            return None
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT report_json FROM mystery_analysis_cache "
                    "WHERE stock_code=? AND period=? AND last_trade_date=?",
                    (stock_code, period, str(last_trade_date))).fetchone()
                return json.loads(row[0]) if row else None
            except Exception:
                return None
            finally:
                conn.close()

    def set_analysis_cache(self, stock_code: str, period: str,
                           last_trade_date: str, report: Dict) -> bool:
        """写入分析结果缓存（INSERT OR REPLACE）"""
        import json
        if not last_trade_date or report is None:
            return False
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO mystery_analysis_cache "
                    "(stock_code, period, last_trade_date, report_json, "
                    "created_at) VALUES (?,?,?,?,datetime('now'))",
                    (stock_code, period, str(last_trade_date),
                     json.dumps(report, ensure_ascii=False, default=str)))
                conn.commit()
                return True
            except Exception as e:
                logger.warning(f"⚠️ 分析缓存写入失败: {e}")
                return False
            finally:
                conn.close()

    def get_kline_count(self) -> int:
        """获取行情总行数"""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("SELECT COUNT(*) FROM stock_kline_data")
                return cur.fetchone()[0]
            finally:
                conn.close()

    # ============ 财务数据 ============
    def upsert_financial(self, code: str, report_date: str,
                         roe: float = None, roe_avg: float = None,
                         np_margin: float = None, gp_margin: float = None,
                         net_profit: float = None, eps_ttm: float = None,
                         pb: float = None, pe: float = None,
                         divid_cash: float = None) -> int:
        """写入单条基本面快照（code,report_date联合主键）"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO stock_financial_data
                    (code, report_date, roe, roe_avg, np_margin, gp_margin,
                     net_profit, eps_ttm, PB, PE, divid_cash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (code, report_date, roe, roe_avg, np_margin, gp_margin,
                      net_profit, eps_ttm, pb, pe, divid_cash))
                conn.commit()
                return 1
            finally:
                conn.close()

    def load_financial(self, code: str, limit: int = 4) -> pd.DataFrame:
        """读取基本面快照（按报告期倒序）"""
        with self._lock:
            conn = self._connect()
            try:
                sql = ("SELECT * FROM stock_financial_data WHERE code=? "
                       "ORDER BY report_date DESC LIMIT ?")
                return pd.read_sql_query(sql, conn, params=[code, limit])
            finally:
                conn.close()

    # ============ 统计 ============
    def stats(self) -> Dict[str, Any]:
        """数据库统计信息"""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("SELECT COUNT(*) FROM stock_industry_info")
                info_count = cur.fetchone()[0]
                cur = conn.execute("SELECT COUNT(*) FROM stock_kline_data")
                kline_count = cur.fetchone()[0]
                cur = conn.execute("SELECT COUNT(*) FROM stock_financial_data")
                fin_count = cur.fetchone()[0]
                return {
                    'db_path': self.db_path,
                    '证券信息数': info_count,
                    '行情行数': kline_count,
                    '财务快照数': fin_count,
                }
            finally:
                conn.close()

    def close(self):
        """关闭（WAL checkpoint）"""
        try:
            conn = self._connect()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except Exception:
            pass
