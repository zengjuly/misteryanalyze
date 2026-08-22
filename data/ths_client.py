#!/usr/bin/env python3
# ths_client.py - 同花顺官方扶摇 Financial-API 客户端（docs/0821.md 第一主源）
"""通过 fuyao.py --compact 命令行管道获取行情/财务/板块数据
真实 CLI 参数（2026-08 实测）:
  prices-historical --thscode 600519.SH --start-ms <ms> --end-ms <ms> --adjust forward
  valuations-snapshot --thscode 600519.SH        → {"item":[{pe_ttm,pb_mrq,...}]}
  index-catalog                                   → [{thscode,name}, ...]
  index-constituents --thscode 885566.TI          → [{thscode,ticker,name}, ...]
  index-historical --thscode 885566.TI --start-ms --end-ms
返回统一中文列（日期/开盘价/最高价/最低价/收盘价/成交量/成交额），与系统一致
"""
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

# 统一中文列（对齐系统标准，docs/step3.md）
CN_COLS = {'日期': None, '开盘价': None, '最高价': None, '最低价': None,
           '收盘价': None, '成交量': None, '成交额': None, '换手率': None}


class ThsOfficialClient:
    """同花顺扶摇金融 API 命令行管道客户端（第一主源）"""

    def __init__(self, config: dict = None):
        self.cfg = ((config or {}).get('data_source', {})
                    .get('ths_config', {}))
        self.script_path = self.cfg.get(
            'script_path',
            '/home/ai/ai_runner/stock/Financial-API/python/toolkit/'
            'fuyao/scripts/fuyao.py')
        self.adjust = self.cfg.get('adjust', 'forward')
        # 本地 MarketDB DuckDB 中枢（docs/0822.md）：目录 → 拼 market.duckdb，
        # 文件 → 直接用；env MARKETDB_DB_PATH 优先
        md_dir = self.cfg.get('marketdb_dir')
        self.marketdb_path = os.environ.get('MARKETDB_DB_PATH') or (
            os.path.join(md_dir, 'market.duckdb') if md_dir
            and os.path.isdir(md_dir) else md_dir)
        # API Key 统一来源: 环境变量 HITHINK_FINANCE_API_KEY（AGENTS.md 规范，
        # key 不写入代码/配置/日志）
        # 子进程解释器: 默认当前 venv python（fuyao 依赖在 venv 中）
        self._fuyao_python = self.cfg.get('python_path') or sys.executable
        # 板块目录进程内缓存（docs/082203.md §2）
        self._index_catalog_cache = None
        self._index_name_to_code = {}

    # ---------- 板块目录缓存（082203 §2） ----------
    def get_index_catalog(self, force: bool = False) -> list:
        """index-catalog 一次拉取，进程内缓存。返回 [{thscode, name}, ...]"""
        if self._index_catalog_cache is not None and not force:
            return self._index_catalog_cache
        raw = self._run_fuyao(['index-catalog', '--tag', 'industry'])
        out = []
        name_map = {}
        for cat in (raw or []):
            if not isinstance(cat, dict):
                continue
            code = cat.get('thscode') or cat.get('index_code')
            name = cat.get('name') or cat.get('index_name')
            if not code or not name:
                continue
            out.append({'thscode': str(code), 'name': str(name)})
            name_map[str(name)] = str(code)
        self._index_catalog_cache = out
        self._index_name_to_code = name_map
        return out

    def fetch_constituents_by_code(self, thscode: str) -> list:
        """板块成分股（index-constituents）→ 无点代码列表 [sh600519, ...]"""
        if not thscode:
            return []
        cons = self._run_fuyao(
            ['index-constituents', '--thscode', str(thscode)])
        stocks = []
        for item in (cons or []):
            raw = item.get('thscode', '')
            if '.' in raw:
                code, mkt = raw.split('.')
                stocks.append(f"{mkt.lower()}{code}")
        return stocks

    # ============ 0. 本地 MarketDB 秒级读取（0822.md 核心） ============
    def _fetch_daily_local(self, ths_code: str, start_date: str,
                           end_date: str) -> pd.DataFrame:
        """本地 DuckDB 缓存读取（v_daily_qfq 前复权视图），秒级零进程"""
        if not self.marketdb_path or not os.path.exists(self.marketdb_path):
            return pd.DataFrame()
        try:
            from marketdb import MarketDB
            with MarketDB.open(self.marketdb_path) as db:
                df = db.get_daily(ths_code, start=start_date,
                                  end=end_date, adjust='forward')
            if df is not None and not df.empty:
                out = pd.DataFrame()
                out['日期'] = pd.to_datetime(df['date'])
                out['开盘价'] = df['open'].astype(float)
                out['最高价'] = df['high'].astype(float)
                out['最低价'] = df['low'].astype(float)
                out['收盘价'] = df['close'].astype(float)
                out['成交量'] = df['volume'].astype(float)
                # v_daily_qfq 成交额列名为 turnover（非 amount）
                if 'turnover' in df.columns:
                    out['成交额'] = df['turnover'].astype(float)
                elif 'amount' in df.columns:
                    out['成交额'] = df['amount'].astype(float)
                else:
                    out['成交额'] = 0.0
                out['换手率'] = None
                logger.info(f"[ths本地MarketDB] {ths_code} "
                            f"{len(out)}条 秒级读取")
                return out.sort_values('日期').reset_index(drop=True)
        except Exception as e:
            logger.debug(f"MarketDB 本地读取失败: {str(e)[:80]}")
        return pd.DataFrame()

    # ============ 0.1 盘前增量离线同步（0822.md） ============
    def sync_market_data(self, force: bool = False) -> bool:
        """本地 MarketDB 增量离线同步（bootstrap 拉全市场到 DuckDB）
        :param force: 强制全量（默认 False：bootstrap 自身判定落后才 FULL）
        :return: 是否执行了同步
        """
        bootstrap = os.path.join(
            os.path.dirname(os.path.dirname(self.script_path)), '..', '..',
            'bootstrap.py')
        bootstrap = os.path.abspath(bootstrap)
        if not os.path.exists(bootstrap):
            logger.warning(f"❌ 找不到 bootstrap.py: {bootstrap}")
            return False
        cmd = [self._fuyao_python, bootstrap, '--prefer-local']
        if force:
            cmd.append('--force')
        try:
            logger.info("🚀 本地 MarketDB 增量同步启动（bootstrap --prefer-local）...")
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 encoding='utf-8', timeout=3600)
            if res.returncode == 0:
                logger.info("✅ MarketDB 同步完成")
                return True
            logger.warning(f"⚠️ MarketDB 同步异常: {res.stderr[-200:]}")
        except Exception as e:
            logger.warning(f"⚠️ MarketDB 同步失败: {str(e)[:100]}")
        return False

    def _run_fuyao(self, args: list, timeout: int = 30) -> list:
        """拉起 fuyao.py 子进程，提取纯净 JSON 流"""
        if not os.path.exists(self.script_path):
            logger.warning(f"❌ 找不到同花顺 SDK: {self.script_path}")
            return []
        cmd = [self._fuyao_python, self.script_path, '--compact'] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 check=True, encoding='utf-8', timeout=timeout)
            out = res.stdout.strip()
            if out:
                data = json.loads(out)
                return data if isinstance(data, list) else [data]
        except Exception as e:
            logger.debug(f"fuyao 调用失败 {args[:2]}: {str(e)[:80]}")
        return []

    @staticmethod
    def _to_ths_code(stock_code: str) -> str:
        """sh600519 -> 600519.SH；指数 sh000001 -> 000001.SH"""
        code = stock_code.replace('.', '')
        pure = code[2:]
        mkt = code[:2].upper()
        return f"{pure}.{mkt}"

    # ============ 0. 全市场证券列表（ths_official 优先，docs/082201） ============
    def fetch_all_tickers(self, refresh_cache: bool = False,
                          use_cache: bool = True) -> list:
        """全市场 A 股证券列表（fuyao tickers-list --all，5559 只 in 2026-08）

        返回: [{'thscode': '600000.SH', 'ticker': '600000', 'name': '浦发银行',
                'exchange': 'SH', 'asset_type': 'a-share', 'currency': 'CNY'}, ...]
        失败返回 []（调用方走 baostock 兜底）

        稳定性: 优先读 fuyao 本地缓存 docs/tickers-cache.json（网络波动兜底），
        缺失/过期(7天)时网络拉取；网络失败自动重试 2 次
        """
        # 1. 本地缓存优先（fuyao tickers-list --refresh-cache 写入的）
        cache_path = os.path.join(os.path.dirname(self.script_path),
                                  '..', 'docs', 'tickers-cache.json')
        cache_path = os.path.abspath(cache_path)
        if use_cache and not refresh_cache:
            try:
                if os.path.exists(cache_path):
                    mtime = os.path.getmtime(cache_path)
                    if time.time() - mtime < 7 * 24 * 3600:  # 7天内
                        with open(cache_path, encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, list) and len(data) >= 1000:
                            logger.info(
                                f"📋 证券列表本地缓存: {len(data)} 只"
                                f"（{os.path.basename(cache_path)}）")
                            return data
            except Exception as e:
                logger.debug(f"证券列表缓存读取失败: {e}")

        # 2. 网络拉取（失败重试 2 次，网络波动时显著提高成功率）
        last_err = ''
        for attempt in range(3):
            try:
                args = ['tickers-list', '--all']
                if refresh_cache or attempt == 0 and not use_cache:
                    args.append('--refresh-cache')
                # tickers-list --all 输出 4 万+ 行 JSON，必须放宽超时（默认30s不够）
                raw = self._run_fuyao(args, timeout=120)
                if raw:
                    # 成功 → 写本地缓存（下次优先读）
                    if use_cache:
                        try:
                            os.makedirs(os.path.dirname(cache_path),
                                        exist_ok=True)
                            with open(cache_path, 'w',
                                      encoding='utf-8') as f:
                                json.dump(raw, f, ensure_ascii=False)
                        except Exception as e:
                            logger.debug(f"证券列表缓存写入失败: {e}")
                    return raw
                last_err = '空结果'
            except Exception as e:
                last_err = str(e)[:80]
            if attempt < 2:
                logger.warning(f"⚠️ tickers-list 第{attempt+1}次失败"
                               f"（{last_err}），重试...")
        logger.warning(f"⚠️ fuyao tickers-list 全部失败: {last_err}")
        return []

    # ============ 1. 个股历史行情 ============
    def fetch_daily(self, stock_code: str, days: int = 1100,
                    start_date: str = None, end_date: str = None,
                    period: str = 'daily') -> pd.DataFrame:
        """获取个股前复权历史日K（docs/0821.md prices-historical + 0822.md 本地优先）"""
        ths_code = self._to_ths_code(stock_code)
        if end_date is None:
            end = datetime.now()
        else:
            end = pd.to_datetime(end_date)
        if start_date is None:
            start = end - timedelta(days=days)
        else:
            start = pd.to_datetime(start_date)

        # 1. 本地 MarketDB 秒级读取（0822.md：消除逐股 subprocess 进程开销）
        local_df = self._fetch_daily_local(ths_code,
                                           start.strftime('%Y-%m-%d'),
                                           end.strftime('%Y-%m-%d'))
        if local_df is not None and not local_df.empty:
            return local_df

        # 2. fuyao subprocess 兜底（0821.md prices-historical）
        args = ['prices-historical', '--thscode', ths_code,
                '--start-ms', str(int(start.timestamp() * 1000)),
                '--end-ms', str(int(end.timestamp() * 1000)),
                '--adjust', self.adjust]
        raw = self._run_fuyao(args)
        if not raw:
            return pd.DataFrame()
        df = pd.DataFrame(raw)
        if df.empty or 'date_ms' not in df.columns:
            return pd.DataFrame()
        out = pd.DataFrame()
        out['日期'] = pd.to_datetime(df['date_ms'], unit='ms')
        out['开盘价'] = df.get('open_price', 0).astype(float)
        out['最高价'] = df.get('high_price', 0).astype(float)
        out['最低价'] = df.get('low_price', 0).astype(float)
        out['收盘价'] = df.get('close_price', 0).astype(float)
        out['成交量'] = df.get('volume', 0).astype(float)
        out['成交额'] = df.get('turnover', 0).astype(float)  # 成交额(元)
        out['换手率'] = None
        out = out.sort_values('日期').reset_index(drop=True)
        return out

    # ============ 2. 个股财务快照 ============
    def fetch_financials(self, stock_code: str) -> dict:
        """提取最新估值快照（PE/PB，docs/0821.md valuations-snapshot）"""
        ths_code = self._to_ths_code(stock_code)
        raw = self._run_fuyao(['valuations-snapshot', '--thscode', ths_code])
        if raw:
            item = raw[0].get('item', []) if isinstance(raw[0], dict) \
                else raw
            if item and isinstance(item[0], dict):
                fin = item[0]
                return {
                    'pe': fin.get('pe_ttm') or 0,
                    'pb': fin.get('pb_mrq') or 0,
                    'pe_mrq': fin.get('pe_mrq') or 0,
                    'ps': fin.get('ps_ttm') or 0,
                    'roe': 0, 'dividend_yield': 0,
                }
        return {'pe': 0, 'pb': 0, 'pe_mrq': 0, 'ps': 0,
                'roe': 0, 'dividend_yield': 0}

    # ============ 3. 板块目录与成分 ============
    def fetch_block_info(self) -> dict:
        """全市场板块及成分股: {板块名: [sh600519, ...]}（082203 §2.4 缓存目录）"""
        block_map = {}
        catalogs = self.get_index_catalog()
        if not catalogs:
            return block_map
        for cat in catalogs[:200]:  # 最多 200 个板块（防过慢）
            index_code = cat.get('thscode') or cat.get('index_code')
            index_name = cat.get('name') or cat.get('index_name')
            if not index_code or not index_name:
                continue
            cons = self._run_fuyao(
                ['index-constituents', '--thscode', index_code])
            if cons:
                stocks = []
                for item in cons:
                    raw = item.get('thscode', '')
                    if '.' in raw:
                        code, mkt = raw.split('.')
                        stocks.append(f"{mkt.lower()}{code}")
                if stocks:
                    block_map[index_name] = stocks
        return block_map

    # ============ 4. 板块历史行情 ============
    def fetch_block_daily_by_code(self, thscode: str, days: int = 1100,
                                  start_date: str = None,
                                  end_date: str = None) -> pd.DataFrame:
        """板块指数日K：index-historical --thscode，不扫目录（082203 §2.2）"""
        if not thscode:
            return pd.DataFrame()
        if end_date is None:
            end = datetime.now()
        else:
            end = pd.to_datetime(end_date)
        start = (end - timedelta(days=days)) if start_date is None \
            else pd.to_datetime(start_date)
        raw = self._run_fuyao([
            'index-historical', '--thscode', str(thscode),
            '--start-ms', str(int(start.timestamp() * 1000)),
            '--end-ms', str(int(end.timestamp() * 1000))])
        if not raw:
            return pd.DataFrame()
        df = pd.DataFrame(raw)
        if df.empty or 'date_ms' not in df.columns:
            return pd.DataFrame()
        out = pd.DataFrame()
        out['日期'] = pd.to_datetime(df['date_ms'], unit='ms')
        out['开盘价'] = df.get('open_price', 0).astype(float)
        out['最高价'] = df.get('high_price', 0).astype(float)
        out['最低价'] = df.get('low_price', 0).astype(float)
        out['收盘价'] = df.get('close_price', 0).astype(float)
        out['成交量'] = df.get('volume', 0).astype(float)
        out['成交额'] = df.get('turnover', 0).astype(float)
        out['换手率'] = None
        return out.sort_values('日期').reset_index(drop=True)

    # 兼容别名（082202 sync_sector_data 曾用名）
    def fetch_index_hist(self, index_code: str, days: int = 1100,
                         start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
        return self.fetch_block_daily_by_code(
            index_code, days=days, start_date=start_date, end_date=end_date)

    def fetch_block_daily(self, block_name: str, days: int = 1100,
                          start_date: str = None,
                          end_date: str = None) -> pd.DataFrame:
        """按板块中文名解析 thscode 后拉指数日K（082203 §2.3 缓存目录）"""
        self.get_index_catalog()
        target = self._index_name_to_code.get(block_name)
        if not target:
            for cat in (self._index_catalog_cache or []):
                if cat.get('name') == block_name:
                    target = cat.get('thscode')
                    break
        if not target:
            return pd.DataFrame()
        return self.fetch_block_daily_by_code(
            target, days=days, start_date=start_date, end_date=end_date)
