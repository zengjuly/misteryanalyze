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
        # API Key 统一来源: 环境变量 HITHINK_FINANCE_API_KEY（AGENTS.md 规范，
        # key 不写入代码/配置/日志）
        # 子进程解释器: 默认当前 venv python（fuyao 依赖在 venv 中）
        self._fuyao_python = self.cfg.get('python_path') or sys.executable

    def _run_fuyao(self, args: list) -> list:
        """拉起 fuyao.py 子进程，提取纯净 JSON 流"""
        if not os.path.exists(self.script_path):
            logger.warning(f"❌ 找不到同花顺 SDK: {self.script_path}")
            return []
        cmd = [self._fuyao_python, self.script_path, '--compact'] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 check=True, encoding='utf-8', timeout=30)
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

    # ============ 1. 个股历史行情 ============
    def fetch_daily(self, stock_code: str, days: int = 1100,
                    start_date: str = None, end_date: str = None,
                    period: str = 'daily') -> pd.DataFrame:
        """获取个股前复权历史日K（docs/0821.md prices-historical）"""
        ths_code = self._to_ths_code(stock_code)
        if end_date is None:
            end = datetime.now()
        else:
            end = pd.to_datetime(end_date)
        if start_date is None:
            start = end - timedelta(days=days)
        else:
            start = pd.to_datetime(start_date)
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
        """全市场板块（概念/行业）及成分股: {板块名: [sh600519, ...]}
        docs/0821.md index-catalog + index-constituents
        """
        block_map = {}
        catalogs = self._run_fuyao(['index-catalog'])
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
    def fetch_block_daily(self, block_name: str, days: int = 1100,
                          start_date: str = None,
                          end_date: str = None) -> pd.DataFrame:
        """板块指数历史K线（docs/0821.md index-historical）"""
        catalogs = self._run_fuyao(['index-catalog'])
        target = None
        for cat in catalogs:
            if (cat.get('name') or cat.get('index_name')) == block_name:
                target = cat.get('thscode') or cat.get('index_code')
                break
        if not target:
            return pd.DataFrame()
        if end_date is None:
            end = datetime.now()
        else:
            end = pd.to_datetime(end_date)
        start = (end - timedelta(days=days)) if start_date is None \
            else pd.to_datetime(start_date)
        raw = self._run_fuyao([
            'index-historical', '--thscode', target,
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
