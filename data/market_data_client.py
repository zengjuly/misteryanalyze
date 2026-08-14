#!/usr/bin/env python3
# market_data_client.py - 统一数据入口（AKShare主源 + Baostock备用源退避）
"""
MarketDataClient - 统一数据入口（主备切换 + 退避）
====================================================
理论来源: docs/sources.md（AKShare + Baostock 双源退避与日K重采样）

功能:
  1. 主源失败自动切换备用源（指数退避 + 日志，不中断分析流程）
  2. 周K/月K 默认由日K重采样生成（prefer_resample=true，周期严格对齐）
  3. 线程安全: Baostock 复用全局锁（BAOSTOCK_LOCK），AKShare 内置限速

数据流:
  上层调用 fetch_daily/fetch_weekly/fetch_monthly
    → 主备退避获取原始K线
    → KLineResampler 聚合周/月K
    → 返回标准中文列名 DataFrame
"""

import logging
import os
import sys
import time
from typing import Dict, Optional

import pandas as pd

# 确保 data/ 目录在 sys.path（支持 data.market_data_client 与 market_data_client 两种导入方式）
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from akshare_client import AkshareClient
from baostock_client import BaostockClient, BAOSTOCK_LOCK
from db_manager import MysteryDB
from kline_resampler import KLineResampler
from source_health import SourceHealth
from tdx_gbbq import TdxGBBQ
from tdx_incremental import TdxIncremental
from tdx_local_client import TdxLocalClient

logger = logging.getLogger(__name__)

# 复权映射: 方案配置值 → baostock adjustflag
ADJUSTFLAG_MAP = {"qfq": "2", "hfq": "1", "none": "3"}

# 中文标准列
_CN_COLS = ["日期", "代码", "开盘价", "最高价", "最低价", "收盘价",
            "成交量", "成交额", "换手率", "涨跌幅"]


class MarketDataClient:
    """统一数据入口：本地增量优先 + 主备退避 + 周期选择 + 日K重采样"""

    def __init__(self, config: Dict):
        ds_cfg = config.get("data_source", {}) if config else {}
        self.ak_client = AkshareClient(
            rate_limit=ds_cfg.get("rate_limit_akshare", 0.3),
            timeout=ds_cfg.get("timeout", 30))
        self.bs_client = BaostockClient()
        # 通达信本地数据源（tdx_local，含协议增量补充）
        tdx_cfg = ds_cfg.get("tdx", {})
        self.tdx_client = TdxLocalClient(
            vipdoc_dir=tdx_cfg.get("vipdoc_dir"),
            enable=tdx_cfg.get("enable", True),
            config=config)
        # 源健康评分与动态熔断（docs/step2.md）
        self.source_health = SourceHealth(config)
        # 升级版重采样器（交易日历感知 + 最少K线数过滤）
        self.resampler = KLineResampler(config)
        self.primary = ds_cfg.get("primary", "akshare")
        # fallback 支持: 字符串或列表
        fb = ds_cfg.get("fallback", "baostock")
        self.fallback_list = fb if isinstance(fb, list) else [fb]
        self.retry_times = int(ds_cfg.get("retry_times", 3))
        self.retry_delay = float(ds_cfg.get("retry_delay", 2))
        self.prefer_resample = bool(ds_cfg.get("prefer_resample", True))
        self.adjust = ds_cfg.get("adjust", "qfq")
        # 源顺序: 主源 + 去重后的备用源列表
        self.source_order = [self.primary]
        for s in self.fallback_list:
            if s and s != self.primary and s not in self.source_order:
                self.source_order.append(s)
        # tdx 空结果缓存：本地数据包缺失时避免每次调用重复空转
        self._tdx_empty_codes = set()
        self._bs_logged_in = False

        # ===== 阶段1优化: 增量更新 + 复权因子（docs/step1.md）=====
        inc_cfg = ds_cfg.get("incremental", {})
        self.incremental_enabled = bool(inc_cfg.get("enable", True))
        self.incremental_gap_threshold = float(inc_cfg.get(
            "gap_threshold", 0.11))  # 除权断裂检测阈值（超过视为除权）
        # 本地缓存数据库（增量锚点/缓存合并用）
        self.db = MysteryDB()
        # 通达信增量更新器（.day文件尾部读取）
        vipdoc_dir = (tdx_cfg.get("vipdoc_dir")
                      or "/home/ai/ai_runner/stock/data/tdx_vipdoc")
        self.tdx_incremental = TdxIncremental(
            vipdoc_dir=vipdoc_dir,
            db_manager=self.db,
            max_bars_per_request=int(inc_cfg.get("max_bars_per_request", 800)))
        # 除权除息因子（gbbq文件可选，无则走连续性检查）
        self.tdx_gbbq = TdxGBBQ(gbbq_file=tdx_cfg.get("gbbq_file"))
        # 交易日历注入（缓存日K日期并集 → 重采样过滤）
        if self.resampler.use_trading_calendar:
            try:
                calendar = self.db.get_trading_calendar()
                if calendar:
                    self.resampler.set_calendar(calendar)
            except Exception as e:
                logger.warning(f"⚠️ 交易日历加载失败({e})，跳过日历过滤")
        if self.incremental_enabled:
            logger.info(f"⚡ 增量更新已启用（gap阈值={self.incremental_gap_threshold}，"
                        f"复权因子={'可用' if self.tdx_gbbq.factors_available else '不可用→连续性检查'}）")

    # ============ 对外接口 ============
    def fetch_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        # 尝试本地增量更新（配置启用且本地有.day文件时）
        if self.incremental_enabled:
            full = self._fetch_with_incremental(code, start_date, end_date)
            if full is not None:
                return full
        # 否则走原有的 _fetch_with_fallback 多源逻辑
        return self._fetch_with_fallback(code, "daily", start_date, end_date)

    def fetch_weekly(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self.prefer_resample:
            daily = self.fetch_daily(code, start_date, end_date)
            if not daily.empty:
                return self.resampler.resample(daily, "weekly")
            return pd.DataFrame()
        return self._fetch_with_fallback(code, "weekly", start_date, end_date)

    def fetch_monthly(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if self.prefer_resample:
            daily = self.fetch_daily(code, start_date, end_date)
            if not daily.empty:
                return self.resampler.resample(daily, "monthly")
            return pd.DataFrame()
        return self._fetch_with_fallback(code, "monthly", start_date, end_date)

    # ============ 增量更新（docs/step1.md） ============
    @staticmethod
    def _to_db_code(code: str) -> str:
        """统一为数据库9位格式(sh.600150)：sh600150→sh.600150，600150→sh.600150"""
        code = str(code).strip()
        if '.' in code:
            return code
        for m in ['sh', 'sz', 'bj']:
            if code.startswith(m):
                return f"{m}.{code[2:]}"
        digits = ''.join(c for c in code if c.isdigit())
        if digits.startswith(('6', '9', '5')):
            return f"sh.{digits}"
        if digits.startswith(('4', '8')):
            return f"bj.{digits}"
        return f"sz.{digits}"

    @staticmethod
    def _to_cn_columns(df: pd.DataFrame) -> pd.DataFrame:
        """英文列 → 中文标准列（缓存数据与增量合并前统一）"""
        if df is None or df.empty:
            return df
        rename_map = {
            'date': '日期', 'open': '开盘价', 'high': '最高价',
            'low': '最低价', 'close': '收盘价', 'volume': '成交量',
            'amount': '成交额', 'turn': '换手率', 'pctChg': '涨跌幅',
            'code': '代码',
        }
        df = df.rename(columns=rename_map)
        for col in _CN_COLS:
            if col not in df.columns:
                df[col] = None
        return df[_CN_COLS].copy()

    def _fetch_with_incremental(self, code: str, start_date: str,
                                end_date: str) -> Optional[pd.DataFrame]:
        """
        本地增量更新路径:
          1. 查数据库最新日期 → 读.day文件尾部增量
          2. 无增量 → 直接返回缓存（零网络请求）
          3. 有增量 → 复权处理（gbbq因子/连续性检查）→ 缓存+增量合并
          4. 除权断裂/无缓存 → 返回 None 回退在线源
        """
        try:
            # 数据库统一9位code（sh.600150），增量读取用6位（tdx_incremental内部转换）
            db_code = self._to_db_code(code)
            last_date = self.db.get_last_date(db_code, 'daily')
            if not last_date:
                # 无缓存锚点：增量无意义，回退在线源全量拉取
                return None
            delta = self.tdx_incremental.fetch_delta(code, last_date)
            cached = self.db.load_kline(db_code, 'daily')
            cached_cn = self._to_cn_columns(cached)

            if delta.empty:
                # 本地无新数据 → 直接返回缓存（毫秒级，零网络）
                if not cached_cn.empty:
                    logger.debug(f"⚡ [{code}] 增量无新数据，返回缓存 {len(cached_cn)} 条")
                    return self._slice(cached_cn, start_date, end_date)
                return None

            # 有增量: 复权一致性处理
            if self.adjust != "none":
                delta = self._adjust_delta(code, delta, cached_cn)
                if delta is None:
                    return None  # 除权断裂 → 回退在线源

            # 缓存 + 增量合并（同日期以增量为准）
            merged = pd.concat([cached_cn, delta], ignore_index=True)
            merged['日期'] = pd.to_datetime(merged['日期'])
            merged = (merged.drop_duplicates(subset=['日期'], keep='last')
                      .sort_values('日期'))
            merged['日期'] = merged['日期'].dt.strftime('%Y-%m-%d')
            merged['代码'] = db_code  # 统一9位格式
            # 增量行(.day)无换手率字段 → 用缓存最近值前向填充（近似，保证分析连续性）
            # 说明: .day 文件不含换手率，增量行该列为 None；ffill 用前一交易日值近似，
            # 使最新交易日换手率/量比等指标可计算（误差仅限最近几天增量）。
            if '换手率' in merged.columns:
                merged['换手率'] = merged['换手率'].ffill()
            logger.info(f"⚡ [{code}] 增量更新: 缓存{len(cached_cn)}条 + 增量{len(delta)}条"
                        f" → 合并{len(merged)}条（last_date={last_date}）")
            return self._slice(merged, start_date, end_date)
        except Exception as e:
            logger.warning(f"⚠️ [{code}] 增量更新异常({str(e)[:100]})，回退在线源")
            return None

    def _adjust_delta(self, code: str, delta: pd.DataFrame,
                      cached_cn: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        增量复权一致性处理:
          1. gbbq 因子可用 → 直接应用复权调整
          2. 否则连续性检查（缓存末收盘 vs 增量首收盘；增量内部跳变）
             通过 → 比例衔接修正；超阈值(除权断裂) → 返回None回退在线源
        """
        delta = delta.copy()
        # 1. gbbq 因子复权
        if self.tdx_gbbq.factors_available:
            delta = self.tdx_gbbq.apply_adjust(code, delta, self.adjust)
            return delta

        # 2. 连续性检查
        if not cached_cn.empty:
            last_close = float(cached_cn.iloc[-1]['收盘价'])
            first_close = float(delta.iloc[0]['收盘价'])
            if last_close and first_close:
                gap = abs(first_close / last_close - 1)
                if gap > self.incremental_gap_threshold:
                    logger.warning(f"⚠️ [{code}] 增量与缓存断裂(gap={gap:.2%}>"
                                   f"{self.incremental_gap_threshold:.0%})，"
                                   f"疑似除权，回退在线源保证复权一致")
                    return None
                # 衔接对齐：仅当增量首日与缓存末日重叠（同一天）时做比例对齐。
                # 正常增量(首日>缓存末日)不做scale——前复权不改变最新价，
                # 增量原始价与缓存前复权价在最新段基准一致，直接合并即连续。
                delta_first = str(pd.to_datetime(delta.iloc[0]['日期']).date())
                cache_last = str(pd.to_datetime(cached_cn.iloc[-1]['日期']).date())
                if delta_first == cache_last:
                    scale = last_close / first_close
                    for col in ['开盘价', '最高价', '最低价', '收盘价']:
                        delta[col] = delta[col] * scale
                    # 重算涨跌幅
                    delta['涨跌幅'] = delta['收盘价'].pct_change() * 100
        # 增量内部跳变检查（窗口内除权检测）
        if '涨跌幅' in delta.columns:
            inner_vals = pd.to_numeric(delta['涨跌幅'], errors='coerce').dropna()
            if not inner_vals.empty:
                inner = inner_vals.abs().max()
                if inner > self.incremental_gap_threshold * 100:
                    logger.warning(f"⚠️ [{code}] 增量内部跳变({inner:.1f}%)，"
                                   f"疑似窗口内除权，回退在线源")
                    return None
        return delta

    @staticmethod
    def _slice(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        """按日期范围切片（增量返回需与请求范围一致）"""
        if start_date:
            df = df[df['日期'] >= str(start_date)]
        if end_date:
            df = df[df['日期'] <= str(end_date)]
        return df

    # ============ 主备退避核心 ============
    def _fetch_with_fallback(self, code: str, period: str,
                             start_date: str, end_date: str) -> pd.DataFrame:
        """
        主备源退避获取（健康评分 + 动态熔断，docs/step2.md）：
        先按健康状态过滤源（熔断剔除）→ 主源重试 retry_times 次（指数退避）
        → 失败切换备用源 → 全部失败返回空
        """
        # 健康过滤：剔除熔断中的源（可配置按健康分动态排序）
        ordered = self.source_health.get_ordered_sources(self.source_order)
        # tdx 空结果缓存：本地数据包缺失时跳过 tdx 源（避免重复空转）
        if self._tdx_empty_codes:
            sources = [s for s in ordered if not (
                s == "tdx_local" and code in self._tdx_empty_codes)]
        else:
            sources = ordered

        last_error = None
        for src in sources:
            switched_fast = False  # tdx 本地无数据快速切换标记
            for attempt in range(self.retry_times):
                start_time = time.time()
                try:
                    df = self._fetch_from_source(src, code, period, start_date, end_date)
                    latency = (time.time() - start_time) * 1000
                    if df is not None and not df.empty:
                        # 成功：记录健康分
                        self.source_health.record(src, True, latency)
                        # 统一列名标准化（不同源可能返回 date/日期 差异）
                        df = self._normalize_columns(df)
                        logger.info(f"[{src}] {code} {period} 获取成功，"
                                    f"{len(df)} 条，耗时{latency:.0f}ms")
                        return df
                    # 空结果视为无数据（非故障）：记录成功避免停牌股误熔断；
                    # tdx_local 本地无文件重试无意义，直接切换下一源
                    self.source_health.record(src, True, latency)
                    last_error = RuntimeError(f"{src} 返回空数据")
                    if src == "tdx_local":
                        self._tdx_empty_codes.add(code)
                        logger.info(f"[tdx_local] {code} {period} 本地无数据，"
                                    f"快速切换下一源")
                        switched_fast = True
                        break  # 跳过该源剩余重试
                except Exception as e:
                    last_error = e
                    latency = (time.time() - start_time) * 1000
                    # 失败：记录健康分（连续失败达到阈值触发熔断）
                    self.source_health.record(src, False, latency)
                    wait = self.retry_delay * (2 ** attempt)
                    logger.warning(f"[{src}] {code} {period} 第{attempt+1}次失败: "
                                   f"{str(e)[:100]}，{wait:.1f}s后重试")
                    time.sleep(wait)
            if not switched_fast:
                logger.warning(f"[{src}] {code} {period} 重试{self.retry_times}次耗尽，"
                               f"切换下一数据源")
        logger.warning(f"⚠️ {code} {period} 所有数据源均失败，最后错误: {last_error}")
        return pd.DataFrame()

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        统一列名标准化：英文列 → 中文标准列
        兼容 baostock（date/开盘价...混合）与 akshare/tdx（全中文）输出
        """
        if df is None or df.empty:
            return df
        rename_map = {
            'date': '日期', 'open': '开盘价', 'high': '最高价',
            'low': '最低价', 'close': '收盘价', 'volume': '成交量',
            'amount': '成交额', 'turn': '换手率', 'pctChg': '涨跌幅',
        }
        df = df.rename(columns=rename_map)
        return df

    def _fetch_from_source(self, src: str, code: str, period: str,
                           start_date: str, end_date: str) -> pd.DataFrame:
        """从指定源获取数据"""
        adjust = self.adjust
        if src == "tdx_local":
            # 通达信本地源仅支持日线；周/月由上层 prefer_resample 重采样
            if period == "daily":
                return self.tdx_client.get_daily_data(code, start_date, end_date)
            return pd.DataFrame()
        if src == "akshare":
            if period == "daily":
                return self.ak_client.get_daily_data(code, start_date, end_date, adjust=adjust)
            elif period == "weekly":
                return self.ak_client.get_weekly_data(code, start_date, end_date, adjust=adjust)
            elif period == "monthly":
                return self.ak_client.get_monthly_data(code, start_date, end_date, adjust=adjust)
        elif src == "baostock":
            adjustflag = ADJUSTFLAG_MAP.get(adjust, "2")
            # baostock 全局单socket：加锁串行化（线程安全）
            with BAOSTOCK_LOCK:
                # 确保已登录（baostock 未登录时查询返回 'you don't login'）
                if not self._bs_logged_in:
                    self._bs_logged_in = self.bs_client.login()
                if period == "daily":
                    return self.bs_client.get_daily_data(code, start_date, end_date,
                                                         adjustflag=adjustflag)
                elif period == "weekly":
                    return self.bs_client.get_weekly_data(code, start_date, end_date,
                                                          adjustflag=adjustflag)
                elif period == "monthly":
                    return self.bs_client.get_monthly_data(code, start_date, end_date,
                                                           adjustflag=adjustflag)
        raise ValueError(f"未知数据源: {src}")

    # ============ 生命周期 ============
    def logout(self):
        """登出所有数据源"""
        try:
            if self._bs_logged_in:
                self.bs_client.logout()
                self._bs_logged_in = False
        except Exception:
            pass
