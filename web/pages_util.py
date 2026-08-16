#!/usr/bin/env python3
# pages_util.py - Web 页面与扫描共用工具（docs/081601.md 扫描使能三振）
"""板块强度计算（从页面2 提取，供全市场扫描三振判定复用）
得分 = MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大×0.3（docs/ui2.md）
"""
import logging
import os
import sys

logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'data'))

# 板块强度模块级缓存（TTL 30 分钟，避免每次扫描/页面重复计算 83×30 次查询）
_strength_cache = {'ts': 0.0, 'rows': []}
_CACHE_TTL = 1800


def calc_sector_strength(use_cache: bool = True) -> list:
    """板块强度计算（行业分类 + 缓存K线），返回 [{板块, 板块得分, ...}]
    :param use_cache: 30 分钟内复用缓存（docs/081601.md 扫描前置构建一次）
    """
    import time
    if use_cache and _strength_cache['rows'] \
            and time.time() - _strength_cache['ts'] < _CACHE_TTL:
        return _strength_cache['rows']
    try:
        from utils.data_feeder import DataFeeder
        import yaml
        cfg = yaml.safe_load(open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config', 'config.yaml')))
        feeder = DataFeeder(cfg)
        ind = feeder.get_industry_data()
        industry_codes = ind.get('industry_codes', {})
        if not industry_codes:
            return []
        from db_manager import MysteryDB
        db = MysteryDB()
        rows = []
        for industry, codes in industry_codes.items():
            if len(codes) < 3:
                continue
            ma20_dev, chg10, amt_up, n = [], [], [], 0
            for c in codes[:10]:  # 每板块最多抽样10只（性能：83×10=830次）
                try:
                    # 日期限制: 近60天数据即可算 MA20/10日涨幅/成交额
                    from datetime import datetime, timedelta
                    start = (datetime.now() - timedelta(days=60)
                             ).strftime('%Y-%m-%d')
                    kdf = db.load_kline(c, 'daily', start_date=start)
                    if kdf is None or len(kdf) < 20:
                        continue
                    close = kdf['close'].astype(float)
                    last = close.iloc[-1]
                    ma20 = close.tail(20).mean()
                    dev = (last / ma20 - 1) * 100 if ma20 else 0
                    c10 = (last / close.iloc[-11] - 1) * 100 \
                        if len(close) > 11 else 0
                    amt = kdf['amount'].astype(float).tail(5).mean() \
                        if 'amount' in kdf.columns else 0
                    amt_prev = kdf['amount'].astype(float).tail(20).head(15)\
                        .mean() if 'amount' in kdf.columns else 0
                    ma20_dev.append(dev)
                    chg10.append(c10)
                    amt_up.append(1 if (amt and amt_prev and amt > amt_prev * 1.1)
                                  else 0)
                    n += 1
                except Exception:
                    continue
            if n < 3:
                continue
            score = (sum(ma20_dev) / n) * 0.4 + \
                    (sum(chg10) / n) * 0.3 + \
                    (sum(amt_up) / n) * 100 * 0.3
            rows.append({'板块': industry, '成分股数': len(codes),
                         '样本数': n, 'MA20偏离%': round(sum(ma20_dev) / n, 2),
                         '近10日涨幅%': round(sum(chg10) / n, 2),
                         '成交额放大': round(sum(amt_up) / n * 100, 1),
                         '板块得分': round(score, 2)})
        rows.sort(key=lambda r: r['板块得分'], reverse=True)
        _strength_cache['ts'] = time.time()
        _strength_cache['rows'] = rows
        return rows
    except Exception as e:
        logger.warning(f"⚠️ 板块强度计算失败: {e}")
        return []


def build_sector_strength_map() -> dict:
    """板块得分 map: {板块名: 得分}（供三振行业趋势判定）"""
    return {r['板块']: r['板块得分'] for r in calc_sector_strength()}
