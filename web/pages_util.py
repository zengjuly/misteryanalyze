#!/usr/bin/env python3
# pages_util.py - Web 页面与扫描共用工具
"""板块强度：Financial-API 官方板块指数日K（禁止成分股抽样，docs/082203 §4）
得分 = MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大×0.3
"""
import logging
import os
import sys

logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in [_ROOT, os.path.join(_ROOT, 'data'), os.path.join(_ROOT, 'utils')]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

_strength_cache = {'ts': 0.0, 'rows': []}
_CACHE_TTL = 1800


def _calc_from_sector_kline() -> list:
    """从本地 sector_kline 表计算板块强度（docs/082210: 秒级，替代在线逐个拉）
    得分 = MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大×0.3
    """
    try:
        from db_manager import MysteryDB
        db = MysteryDB()
        df = db.load_all_sector_kline()
        if df is None or df.empty:
            return []
        rows = []
        for code, g in df.groupby('sector_code'):
            g = g.sort_values('trade_date')
            close = g['close'].astype(float)
            if len(close) < 21:
                continue
            last = float(close.iloc[-1])
            ma20 = float(close.tail(20).mean())
            if ma20 <= 0:
                continue
            bias = (last / ma20 - 1) * 100
            chg10 = 0.0
            if len(close) > 11:
                past = float(close.iloc[-11])
                if past > 0:
                    chg10 = (last / past - 1) * 100
            amt_ratio = 1.0
            if 'amount' in g.columns:
                a5 = float(g['amount'].tail(5).mean() or 0)
                a15 = float(g['amount'].tail(20).head(15).mean() or 0)
                if a15 > 0:
                    amt_ratio = a5 / a15
            score = bias * 0.4 + chg10 * 0.3 + (amt_ratio - 1) * 100 * 0.3
            name = str(g['sector_name'].iloc[-1]) \
                if 'sector_name' in g.columns else code
            rows.append({
                '板块': name,
                '板块代码': code,
                'MA20偏离%': round(bias, 2),
                '近10日涨幅%': round(chg10, 2),
                '成交额放大': round(amt_ratio, 2),
                '板块得分': round(float(score), 2),
            })
        rows.sort(key=lambda r: r['板块得分'], reverse=True)
        return rows
    except Exception as e:
        logger.warning(f'⚠️ _calc_from_sector_kline 失败: {e}')
        return []


def calc_sector_strength(use_cache: bool = True) -> list:
    """基于板块指数K线计算强度，禁止个股抽样/全量。
    得分 = MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大×0.3
    （docs/082210 优化: 优先读 sector_kline 本地表秒级；在线源仅兜底）
    """
    import time
    if use_cache and _strength_cache['rows'] \
            and time.time() - _strength_cache['ts'] < _CACHE_TTL:
        return _strength_cache['rows']
    try:
        # 1. 本地 sector_kline 表优先（26万行已同步，秒级）
        rows = _calc_from_sector_kline()
        if rows:
            _strength_cache['ts'] = time.time()
            _strength_cache['rows'] = rows
            return rows
        logger.warning('⚠️ sector_kline 本地无数据，走在线源')
    except Exception as e:
        logger.warning(f'⚠️ sector_kline 读取失败: {e}')
    try:
        import yaml
        cfg_path = os.path.join(_ROOT, 'config', 'config.yaml')
        with open(cfg_path, encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
        from ths_client import ThsOfficialClient
        client = ThsOfficialClient(cfg)
        catalog = client.get_index_catalog()
        if not catalog:
            logger.warning('⚠️ index-catalog 为空，板块强度无法计算')
            return []
        max_sectors = int((cfg.get('sector') or {}).get('max_sectors', 120))
        rows = []
        for cat in catalog[:max_sectors]:
            name = cat.get('name')
            code = cat.get('thscode')
            if not name or not code:
                continue
            try:
                kdf = client.fetch_block_daily_by_code(code, days=90)
                if kdf is None or len(kdf) < 20:
                    continue
                close = kdf['收盘价'].astype(float)
                last = float(close.iloc[-1])
                ma20 = float(close.tail(20).mean())
                if ma20 <= 0:
                    continue
                bias = (last / ma20 - 1) * 100
                chg10 = 0.0
                if len(close) > 11:
                    past = float(close.iloc[-11])
                    if past > 0:
                        chg10 = (last / past - 1) * 100
                amt_ratio = 1.0
                if '成交额' in kdf.columns:
                    a5 = float(kdf['成交额'].tail(5).mean() or 0)
                    a15 = float(kdf['成交额'].tail(20).head(15).mean() or 0)
                    if a15 > 0:
                        amt_ratio = a5 / a15
                score = bias * 0.4 + chg10 * 0.3 + (amt_ratio - 1) * 100 * 0.3
                rows.append({
                    '板块': name,
                    '板块代码': code,
                    'MA20偏离%': round(bias, 2),
                    '近10日涨幅%': round(chg10, 2),
                    '成交额放大': round(amt_ratio, 2),
                    '板块得分': round(float(score), 2),
                })
            except Exception:
                continue
        rows.sort(key=lambda r: r['板块得分'], reverse=True)
        _strength_cache['ts'] = time.time()
        _strength_cache['rows'] = rows
        return rows
    except Exception as e:
        logger.warning(f'⚠️ 板块强度计算失败: {e}')
        return []


def build_sector_strength_map() -> dict:
    """板块得分 map: {板块名: 得分}（docs/081601.md 扫描三振前置）"""
    return {r['板块']: r['板块得分'] for r in calc_sector_strength()}
