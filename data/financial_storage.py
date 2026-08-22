#!/usr/bin/env python3
# financial_storage.py - 财务数据标准化与存储（基于docs/step3.md阶段3优化-财务本地化）
"""
财务数据标准化与存储
====================
理论来源: docs/step3.md（阶段3完整生产化方案 - 财务完整本地化）

功能:
  - 统一财务数据存储门面：封装 db_manager 的 stock_financial_data 宽表
    （主键 (code, report_date)，含 ROE/EPS/PE/PB/股息率等字段）
  - 提供本地财务数据源状态检测（db缓存 / gpcw财务包文件）
  - 兼容现有 data_engine.get_financial 缓存路径（写入同一张表）

说明:
  通达信 gpcw*.dat 财务文件为专有二进制格式（不同年份字段不同），
  mootdx 0.11.7 financial 模块为空包，暂不做二进制解析；
  本地财务数据由 AKShare/Baostock 在线源获取并缓存至 SQLite
  （与 tdx_local_client 现有兜底策略一致）。
"""

import glob
import logging
import os
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 财务字段标准列（宽表结构，与 stock_financial_data 表一致）
STANDARD_FIELDS = [
    '报告期', 'ROE', 'ROE_AVG', 'EPS', 'PE', 'PB', '股息率', '净利润',
    '营业收入', '毛利率', '净利率',
]

# 数据库列名 → 标准中文名
_DB_TO_CN = {
    'report_date': '报告期', 'roe': 'ROE', 'roe_avg': 'ROE_AVG',
    'eps_ttm': 'EPS', 'PE': 'PE', 'PB': 'PB', 'divid_cash': '每股股息',
    'net_profit': '净利润', 'gp_margin': '毛利率', 'np_margin': '净利率',
}


class FinancialStorage:
    """财务数据标准化存储门面（基于 SQLite stock_financial_data 宽表）"""

    def __init__(self, db_manager):
        """
        :param db_manager: MysteryDB 实例（或兼容接口：upsert_financial/load_financial）
        """
        self.db = db_manager

    # ============ 写入 ============
    def save_financial(self, code: str, data: Dict) -> int:
        """
        保存单条财务快照（标准化字段映射）
        :param code: 证券代码（sh.600150）
        :param data: 财务字段 dict（支持中文标准名或英文名）
        :return: 写入行数（0/1）
        """
        if not data:
            return 0
        row = self._normalize_row(data)
        # divid_cash 列语义=每股现金分红（元）；若上游只给股息率(%)则原样存
        divid = row.get('每股股息', row.get('divid_cash'))
        return self.db.upsert_financial(
            code,
            str(row.get('报告期') or ''),
            roe=row.get('ROE'), roe_avg=row.get('ROE_AVG') or row.get('ROE'),
            np_margin=row.get('净利率'), gp_margin=row.get('毛利率'),
            net_profit=row.get('净利润'), eps_ttm=row.get('EPS'),
            pb=row.get('PB'), pe=row.get('PE'),
            divid_cash=divid)

    def save_financial_df(self, code: str, df: pd.DataFrame,
                          report_date_col: str = '报告期') -> int:
        """批量保存财务 DataFrame（每行一个报告期）"""
        if df is None or df.empty:
            return 0
        n = 0
        for _, r in df.iterrows():
            data = {c: r.get(c) for c in df.columns}
            if report_date_col in df.columns:
                data['报告期'] = r.get(report_date_col)
            n += self.save_financial(code, data)
        return n

    @staticmethod
    def _normalize_row(data: Dict) -> Dict:
        """统一字段名（英文→中文标准名）"""
        row = {}
        for k, v in data.items():
            if v is None:
                continue
            key = _DB_TO_CN.get(k, k)
            row[key] = v
        return row

    # ============ 查询 ============
    def load_latest(self, code: str) -> Dict:
        """加载最新财务快照（报告期最新）
        :return: 含 每股股息（元）与 股息率（%，按最新收盘价换算，无价时 None）
        """
        df = self.db.load_financial(code, limit=1)
        if df.empty:
            return {}
        r = df.iloc[0]
        divid = r.get('divid_cash')
        # 股息率 = 每股股息/最新收盘价 × 100（divid_cash 语义为每股现金分红）
        div_yield = None
        if divid:
            try:
                kdf = self.db.load_kline(code, 'daily')
                if kdf is not None and not kdf.empty:
                    close = float(kdf['close'].iloc[-1])
                    if close > 0:
                        div_yield = round(float(divid) / close * 100, 2)
            except Exception:
                pass
        return {
            '报告期': r.get('report_date'), 'ROE': r.get('roe'),
            'ROE_AVG': r.get('roe_avg'), 'EPS': r.get('eps_ttm'),
            'PE': r.get('PE'), 'PB': r.get('PB'),
            '每股股息': divid,
            '股息率': div_yield,
            '净利润': r.get('net_profit'), '毛利率': r.get('gp_margin'),
            '净利率': r.get('np_margin'),
        }

    def load_history(self, code: str, limit: int = 4) -> pd.DataFrame:
        """加载历史财务快照（报告期倒序）"""
        return self.db.load_financial(code, limit=limit)

    def is_cached(self, code: str) -> bool:
        """该股票是否有本地财务缓存"""
        return not self.db.load_financial(code, limit=1).empty

    def ensure_financial(self, code: str, client=None) -> Dict:
        """确保财务可用：优先 ThsOfficialClient.valuations-snapshot，再 baostock。
        :param code: sh.600150 或 sh600150
        :return: {报告期/ROE/EPS/PE/PB/股息率/...}，失败 {}
        """
        fi = self.load_latest(code)
        # 有 PE/PB 或报告期/ROE/EPS 即视为有效（ths 快照无报告期）
        if fi and (
            fi.get('PE') is not None or fi.get('PB') is not None
            or fi.get('报告期') or fi.get('ROE') is not None
            or fi.get('EPS') is not None
        ):
            return fi

        code_dot = code if '.' in code else (
            code[:2] + '.' + code[2:] if len(code) > 2 else code)
        code_nodot = code.replace('.', '')

        # ----- 1. 优先同花顺扶摇 valuations-snapshot -----
        try:
            import yaml
            import os
            from datetime import date
            cfg_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config', 'config.yaml')
            with open(cfg_path, encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            from ths_client import ThsOfficialClient
            ths = ThsOfficialClient(cfg)
            snap = ths.fetch_financials(code_nodot)
            pe = snap.get('pe') or snap.get('pe_ttm')
            pb = snap.get('pb') or snap.get('pb_mrq')
            # 全 0 / 全空视为失败，走兜底
            if pe or pb:
                row = {
                    '报告期': date.today().isoformat(),  # 估值快照日占位
                    'PE': pe if pe else None,
                    'PB': pb if pb else None,
                    'ROE': snap.get('roe') or None,
                    'EPS': None,
                    '股息率': snap.get('dividend_yield') or None,
                }
                # 去掉纯 0 的 ROE/股息占位，避免污染
                if not row.get('ROE'):
                    row.pop('ROE', None)
                if not row.get('股息率'):
                    row.pop('股息率', None)
                self.save_financial(code_dot, row)
                latest = self.load_latest(code_dot)
                if latest:
                    return latest
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"⚠️ ensure_financial ths 失败({code}): {str(e)[:80]}")

        # ----- 2. 兜底 MultiSourceClient / baostock（保留） -----
        try:
            if client is None:
                import yaml
                import os
                from multi_source_client import MultiSourceClient
                cfg_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'config', 'config.yaml')
                with open(cfg_path, encoding='utf-8') as f:
                    cfg = yaml.safe_load(f)
                client = MultiSourceClient(cfg)
            if not getattr(client, 'login_success', False):
                client.login()
            current_price = None
            try:
                kdf = self.db.load_kline(code_dot, 'daily')
                if kdf is not None and not kdf.empty:
                    current_price = float(kdf['close'].iloc[-1])
            except Exception:
                pass
            data = client.get_financial_data(code_nodot, current_price)
            if not data:
                return {}
            self.save_financial(code_dot, data)
            return self.load_latest(code_dot)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"⚠️ ensure_financial 兜底失败({code}): {str(e)[:80]}")
            return {}

    # ============ 本地数据源状态 ============
    @staticmethod
    def list_gpcw_files(vipdoc_dir: str) -> List[str]:
        """
        列出本地通达信财务包文件（gpcw*.zip / cw/gpcw*.dat）
        说明: gpcw 为专有二进制格式，暂不解析；此处仅探测数据源状态
        """
        files = []
        if not vipdoc_dir or not os.path.isdir(vipdoc_dir):
            return files
        files += sorted(glob.glob(os.path.join(vipdoc_dir, 'gpcw*.zip')))
        files += sorted(glob.glob(os.path.join(vipdoc_dir, 'cw', 'gpcw*.dat')))
        return files

    def local_source_status(self, vipdoc_dir: str = None) -> Dict:
        """
        本地财务数据源状态（可观测性报告用）
        :return: {'gpcw_files': [...], 'gpcw_count': N, 'note': 说明}
        """
        gpcw = self.list_gpcw_files(vipdoc_dir)
        return {
            'gpcw_files': [os.path.basename(f) for f in gpcw[-5:]],
            'gpcw_count': len(gpcw),
            'note': 'gpcw为专有二进制格式暂不解析；财务数据由在线源获取后缓存至SQLite'
                    '（stock_financial_data表）',
        }
