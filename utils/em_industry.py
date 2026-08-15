#!/usr/bin/env python3
# em_industry.py - 东方财富行业板块数据（docs/ui2.md 通达信风格行业板块）
"""akshare 东财行业板块 → {code_map, industry_codes}
- 行业列表: ak.stock_board_industry_name_em()（86个，名称简短如"船舶制造"）
- 成分股: ak.stock_board_industry_cons_em(symbol)（逐行业，线程池并发加速）
- 失败自动降级: 返回空（调用方回退 baostock 证监会分类）
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict

logger = logging.getLogger(__name__)

_MAX_WORKERS = 6


def _fetch_cons(symbol: str) -> list:
    """拉取单个行业成分股（[code, name]），失败返回 []"""
    try:
        import akshare as ak
        df = ak.stock_board_industry_cons_em(symbol=symbol)
        if df is None or df.empty:
            return []
        code_col = '代码' if '代码' in df.columns else df.columns[1]
        name_col = '名称' if '名称' in df.columns else df.columns[2]
        return [(str(r[code_col]).zfill(6), str(r[name_col]))
                for _, r in df.iterrows()]
    except Exception as e:
        logger.warning(f"⚠️ 东财行业成分拉取失败 {symbol}: {str(e)[:60]}")
        return []


def fetch_em_industry() -> Dict:
    """拉取东财行业板块（含成分股），返回 {'code_map': {...}, 'industry_codes': {...}}
    全部失败返回空 dict（调用方回退 baostock）
    """
    try:
        import akshare as ak
        names_df = ak.stock_board_industry_name_em()
        if names_df is None or names_df.empty:
            return {}
        name_col = '板块名称' if '板块名称' in names_df.columns else names_df.columns[0]
        symbols = [str(s) for s in names_df[name_col].tolist()]
        logger.info(f"🏢 东财行业 {len(symbols)} 个，并发拉取成分股...")

        code_map, industry_codes = {}, {}
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_cons, s): s for s in symbols}
            for fut in as_completed(futures):
                industry = futures[fut]
                try:
                    members = fut.result()
                except Exception:
                    members = []
                codes = []
                for c6, nm in members:
                    mkt = 'sh' if c6.startswith(('6', '9')) else 'sz'
                    full = f"{mkt}.{c6}"
                    code_map[full] = industry
                    codes.append(full)
                if codes:
                    industry_codes[industry] = codes
        if code_map:
            logger.info(f"🏢 东财行业拉取完成: {len(code_map)} 只, "
                        f"{len(industry_codes)} 个行业")
        return {'code_map': code_map, 'industry_codes': industry_codes}
    except Exception as e:
        logger.warning(f"⚠️ 东财行业拉取异常（回退 baostock）: {str(e)[:80]}")
        return {}
