#!/usr/bin/env python3
# trade_calendar.py - 真实最新交易日判定（在线交易日历优先 + 主库回退）
"""
真实最新交易日工具
==================
背景（2026-08-20 用户反馈）:
  市场扫描/定时任务/个股分析的缓存命中误判 —— 主库缓存停在 08-18，
  但真实最新交易日是 08-20（在线源有当日数据）。ScanStore.get_market_trade_date()
  以主库 MAX(date) 为缓存键，主库未更新时永远返回旧日期 → 误判"行情未更新"
  → 永远复用旧缓存，不拉最新行情。

方案:
  真实最新交易日 = max(在线交易日历 ≤ 今天, 主库最新交易日)
  - 在线优先: akshare tool_trade_date_hist_sina（全部交易日，TTL 缓存 10 分钟）
  - 主库回退: 在线失败时用主库 MAX(date)（保持原有行为）
  - 盘中保护: 当日 15:30 之前（收盘前）在线日历取到"今天"时回退到上一交易日，
    避免盘中把当天未收盘的行情当作最新交易日（收盘后取今天）。

用法:
  from trade_calendar import get_latest_trade_date
  latest = get_latest_trade_date()      # '2026-08-20'
  stale  = get_latest_trade_date() < '2026-08-19'
"""
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional

# 确保 data/ 目录在 sys.path
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)

# 在线交易日历 TTL 缓存（秒）
_CALENDAR_TTL = 600
_calendar_cache: Optional[List[str]] = None
_calendar_ts: float = 0.0
_calendar_lock = threading.Lock()

# 收盘时间（当日 15:30 前视为盘中，最新交易日回退上一交易日）
_CLOSE_HOUR, _CLOSE_MINUTE = 15, 30


def _fetch_online_calendar() -> List[str]:
    """akshare 全市场交易日历（含过去+未来），失败返回空列表"""
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        dates = sorted(str(d) for d in df['trade_date'])
        if dates:
            logger.debug(f"📅 在线交易日历获取成功: {len(dates)} 条 "
                         f"({dates[0]} ~ {dates[-1]})")
        return dates
    except Exception as e:
        logger.warning(f"⚠️ 在线交易日历获取失败({str(e)[:80]})，回退主库")
        return []


def _get_db_max_date() -> Optional[str]:
    """主库最新交易日（回退用，避免循环依赖延迟导入）"""
    try:
        from db_manager import MysteryDB
        db = MysteryDB()
        conn = db._connect()
        try:
            row = conn.execute(
                "SELECT MAX(date) FROM stock_kline_data WHERE period='daily'"
            ).fetchone()
            return str(row[0]) if row and row[0] else None
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"⚠️ 主库最新交易日获取失败: {e}")
        return None


def get_latest_trade_date(now: Optional[datetime] = None) -> Optional[str]:
    """
    真实最新交易日:
      1. 在线交易日历（TTL 缓存）≤ 今天的最大交易日
         - 盘中（15:30 前）回退上一交易日，避免未收盘行情
      2. 在线失败 → 主库 MAX(date)
    :param now: 当前时间（测试可注入），默认 datetime.now()
    :return: 'YYYY-MM-DD' 或 None（全部失败）
    """
    global _calendar_cache, _calendar_ts
    now = now or datetime.now()
    today = now.date()

    # 1. 在线交易日历
    with _calendar_lock:
        if _calendar_cache is None or \
                time.time() - _calendar_ts > _CALENDAR_TTL:
            dates = _fetch_online_calendar()
            if dates:
                _calendar_cache = dates
                _calendar_ts = time.time()
        else:
            dates = _calendar_cache

    if dates:
        # 盘中保护: 15:30 前 → 今天视为未收盘，取上一交易日
        if now.hour < _CLOSE_HOUR or \
                (now.hour == _CLOSE_HOUR and now.minute < _CLOSE_MINUTE):
            cutoff = (today - timedelta(days=1)).isoformat()
        else:
            cutoff = today.isoformat()
        valid = [d for d in dates if d <= cutoff]
        if valid:
            return valid[-1]
        # 在线日历有数据但无 <= cutoff 的日期（极端：跨年边界）→ 取最早的
        if dates:
            return dates[0]

    # 2. 主库回退（在线失败/无数据）
    return _get_db_max_date()


def is_trade_date(date_str: str) -> bool:
    """判断某日期是否为交易日（在线日历优先，失败按工作日近似）"""
    global _calendar_cache
    dates = _calendar_cache
    if not dates:
        with _calendar_lock:
            if not _calendar_cache:
                _calendar_cache = _fetch_online_calendar() or []
            dates = _calendar_cache
    if dates:
        return date_str in dates
    # 回退: 工作日近似（周一~周五）
    d = datetime.strptime(date_str, '%Y-%m-%d').date()
    return d.weekday() < 5


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    latest = get_latest_trade_date()
    print(f"真实最新交易日: {latest}")
    print(f"今天是否交易日(在线日历): {is_trade_date(datetime.now().date().isoformat())}")
