#!/usr/bin/env python3
# tdx_block_client.py - 通达信行业/概念/风格板块读取（docs/081601.md §二）
"""复用 mootdx Reader 读取通达信板块文件（T0002/hq_cache/block_*.dat）
- 行业板块: block.dat / incon.dat
- 概念板块: block_gn.dat；风格: block_fg.dat；指数: block_zs.dat
- 本机无 TDX_HOME（无 block 文件）时返回空 → 上层保持现有兜底（db 行业分类/东财/baostock）
"""
import logging
import os
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 板块文件 → 分类名
BLOCK_FILES = [
    ('行业', 'block.dat'),
    ('概念', 'block_gn.dat'),
    ('风格', 'block_fg.dat'),
    ('指数', 'block_zs.dat'),
]


class TdxBlockClient:
    """通达信板块读取器（mootdx Reader.block / incon.dat）"""

    def __init__(self, tdx_dir: str = None):
        self.tdx_dir = tdx_dir or os.environ.get('TDX_HOME') or \
            os.environ.get('TDX_VIPDOC_DIR')
        self.reader = None
        self._blocks_cache: Optional[Dict[str, pd.DataFrame]] = None
        if self.tdx_dir and os.path.exists(self.tdx_dir):
            try:
                from mootdx.reader import Reader
                self.reader = Reader.factory(market='std', tdxdir=self.tdx_dir)
                logger.info(f"📂 TDX Block Client 就绪: {self.tdx_dir}")
            except Exception as e:
                logger.warning(f"⚠️ mootdx Reader 初始化失败: {str(e)[:80]}")

    def _available(self) -> bool:
        return self.reader is not None

    def get_industry_blocks(self, group: bool = True) -> pd.DataFrame:
        """通达信行业板块（优先 block_gn.dat 概念/行业，其次 block.dat/incon.dat）
        :return: 长表（blockname, code）——group 输入的 code_list 列展开为每行一股
        """
        if not self._available():
            return pd.DataFrame()
        for kind, fname in [('概念', 'block_gn.dat'), ('行业', 'block.dat')]:
            try:
                df = self.reader.block(symbol=fname, group=group)
                if df is not None and not df.empty:
                    # group 格式: code_list 是逗号分隔串 → 展开为长表
                    if 'code_list' in df.columns and 'code' not in df.columns:
                        rows = []
                        for _, r in df.iterrows():
                            for c in str(r['code_list']).split(','):
                                c = c.strip()
                                if c:
                                    rows.append({'blockname': r.get(
                                        'blockname', ''), 'code': c})
                        if rows:
                            return pd.DataFrame(rows)
                    return df
            except Exception as e:
                logger.debug(f"读取 {fname} 失败: {str(e)[:60]}")
        try:
            df = self.reader.parse('incon.dat')
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
        return pd.DataFrame()

    def get_all_blocks(self) -> Dict[str, pd.DataFrame]:
        """返回各类板块 {分类: DataFrame}（带缓存）"""
        if self._blocks_cache is not None:
            return self._blocks_cache
        result = {}
        if not self._available():
            self._blocks_cache = result
            return result
        for kind, fname in BLOCK_FILES:
            try:
                df = self.reader.block(symbol=fname, group=True)
                if df is not None and not df.empty:
                    result[kind] = df
            except Exception:
                pass
        self._blocks_cache = result
        if result:
            logger.info(f"🏢 TDX 板块读取: {list(result.keys())} "
                        f"({self.tdx_dir})")
        return result

    def to_code_map(self, blocks_df: pd.DataFrame) -> dict:
        """板块 DataFrame → {code: 主板块名}（每个股票取首个归属板块，兼容单值列）
        :param blocks_df: get_industry_blocks 长表（blockname, code 每行一股）
        :return: {sh600150: 板块名}
        """
        multi = self.to_multi_code_map(blocks_df)
        return {c: b[0] for c, b in multi.items() if b}

    def to_multi_code_map(self, blocks_df: pd.DataFrame) -> dict:
        """板块 DataFrame → {code: [板块1, 板块2, ...]}（多归属，去重保序）
        用户要求(2026-08-17): 一只股票可归属多个板块，不再"最后覆盖"
        :param blocks_df: get_industry_blocks 长表（blockname, code 每行一股）
        :return: {sh600150: ['中特估', '军工', ...]}
        """
        code_map: dict = {}
        if blocks_df is None or blocks_df.empty:
            return code_map
        code_col = 'code' if 'code' in blocks_df.columns else \
            (blocks_df.columns[1] if len(blocks_df.columns) > 1 else None)
        name_col = 'blockname' if 'blockname' in blocks_df.columns else \
            ('name' if 'name' in blocks_df.columns else None)
        if code_col is None or name_col is None:
            return code_map
        for _, row in blocks_df.iterrows():
            raw = str(row[code_col])
            # 通达信 code 列: 市场前缀+代码（如 sh600150 / 1.600150）
            digits = ''.join(c for c in raw if c.isdigit())
            if len(digits) < 6:
                continue
            c6 = digits[-6:]
            mkt = 'sh' if c6.startswith(('6', '9', '5')) else (
                'sz' if c6.startswith(('0', '2', '3')) else 'bj')
            db_code = f"{mkt}.{c6}"
            block = str(row[name_col])
            if db_code not in code_map:
                code_map[db_code] = []
            if block not in code_map[db_code]:
                code_map[db_code].append(block)
        return code_map

    def get_stock_industry(self, code: str) -> Optional[str]:
        """单只股票所属行业（板块反查，返回主板块）"""
        code_map = self.to_code_map(self.get_industry_blocks())
        db_code = code if '.' in code else (code[:2] + '.' + code[2:])
        return code_map.get(db_code)
