#!/usr/bin/env python3
# tdx_incremental.py - 通达信本地.day文件增量更新器（基于docs/step1.md阶段1优化）
"""
TdxIncremental - 通达信增量更新器
==================================
理论来源: docs/step1.md（最新工程优化实施指南 - 阶段1核心代码）

核心价值:
  每日分析仅需读取 .day 文件尾部"上次同步日期之后"的新记录，
  毫秒级完成增量获取，避免全量网络请求（AKShare/baostock）。

设计要点:
  1. 直接 struct 解析 .day 文件（32字节/条），不依赖 mootdx，性能极高
  2. 兼容两种目录结构:
     - 标准: {vipdoc}/{market}/lday/{market}{code}.day
     - 扁平: {vipdoc}/{market}\\lday\\{market}{code}.day
       （旧版解压脚本把zip内反斜杠路径当文件名解压的遗留结构）
  3. 返回标准中文列名 DataFrame: 日期/代码/开盘价/最高价/最低价/收盘价/成交量/成交额/涨跌幅
  4. 幂等: 只读取 last_date 之后的数据，重复同步不产生重复

说明:
  - .day 文件为不复权原始价；复权一致性由上层 TdxGBBQ / 连续性检查保证
  - 成交量单位: 股 → 手（/100），与 AKShare 一致
  - 涨跌幅: 由收盘价 pct_change 重算
"""

import logging
import os
import struct
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# .day 单条记录 32 字节: 日期(4) 开盘(4) 最高(4) 最低(4) 收盘(4) 成交额(4f) 成交量(4) 保留(4)
DAY_RECORD_SIZE = 32
DAY_RECORD_FMT = '<IIIIIfII'


class TdxIncremental:
    """通达信增量更新器：从本地 .day 文件尾部读取增量"""

    def __init__(self, vipdoc_dir: str, db_manager=None,
                 max_bars_per_request: int = 800):
        self.vipdoc_dir = vipdoc_dir
        self.db = db_manager
        self.max_bars_per_request = max_bars_per_request

    # ============ 路径解析 ============
    @staticmethod
    def _get_market(code: str) -> str:
        """根据6位代码判断市场: sh/sz/bj"""
        if code.startswith(("6", "9", "5")):      # 沪市A股/科创板/ETF
            return "sh"
        elif code.startswith(("0", "2", "3")):    # 深市A股/创业板
            return "sz"
        elif code.startswith(("4", "8")):         # 北交所
            return "bj"
        return "sh"  # 默认

    @staticmethod
    def _normalize_code(stock_code: str) -> str:
        """统一转为6位数字（sh600150 → 600150，sh.600150 → 600150）"""
        code = str(stock_code).strip().lower()
        for prefix in ["sh.", "sz.", "bj.", "sh", "sz", "bj"]:
            code = code.replace(prefix, "")
        digits = "".join(ch for ch in code if ch.isdigit())
        return digits.zfill(6)

    def _day_file_path(self, code: str) -> Optional[str]:
        """
        定位 .day 文件路径:
        1. 标准目录结构: {vipdoc}/{market}/lday/{market}{code}.day
        2. 扁平遗留结构: {vipdoc}/{market}\\lday\\{market}{code}.day
        """
        market = self._get_market(code)
        rel_std = os.path.join(market, "lday", f"{market}{code}.day")
        std = os.path.join(self.vipdoc_dir, rel_std)
        if os.path.exists(std):
            return std
        # 扁平遗留结构（反斜杠为文件名字符）
        flat = os.path.join(self.vipdoc_dir, f"{market}\\lday\\{market}{code}.day")
        if os.path.exists(flat):
            return flat
        return None

    def has_local_data(self, code: str) -> bool:
        """该股票本地是否有 .day 文件"""
        return self._day_file_path(code) is not None

    # ============ 增量读取 ============
    def _read_day_file_tail(self, code: str,
                            last_date: Optional[str]) -> pd.DataFrame:
        """
        读取 .day 文件中日期大于 last_date 的所有记录（增量）
        :param code: 6位或带前缀代码
        :param last_date: 上次同步日期 YYYY-MM-DD，None=读取全部（限尾部）
        :return: 标准中文列名 DataFrame，可能为空
        """
        filepath = self._day_file_path(code)
        if not filepath:
            return pd.DataFrame()

        records = []
        try:
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(DAY_RECORD_SIZE)
                    if not chunk or len(chunk) < DAY_RECORD_SIZE:
                        break
                    date, open_, high, low, close, amount, volume, _ = \
                        struct.unpack(DAY_RECORD_FMT, chunk)
                    date_str = str(date)
                    # 过滤无效/异常记录
                    if date_str == '0' or date_str < '19900101':
                        continue
                    trade_date = datetime.strptime(
                        date_str, '%Y%m%d').strftime('%Y-%m-%d')
                    if last_date and trade_date <= last_date:
                        continue  # 只取新数据
                    records.append({
                        '日期': trade_date,
                        '代码': code,
                        '开盘价': open_ / 100.0,
                        '最高价': high / 100.0,
                        '最低价': low / 100.0,
                        '收盘价': close / 100.0,
                        '成交量': volume / 100.0,   # 股 → 手
                        '成交额': amount,            # 元
                        '换手率': None,              # 本地文件无换手率
                        '涨跌幅': None,              # 稍后统一计算
                    })
        except Exception as e:
            logger.error(f"❌ 读取 {filepath} 失败: {e}")
            return pd.DataFrame()

        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期')
        # 计算涨跌幅（首条为NaN）
        df['涨跌幅'] = df['收盘价'].pct_change() * 100
        return df

    def fetch_delta(self, code: str, last_date: Optional[str]) -> pd.DataFrame:
        """
        获取增量日K（本地.day文件尾部）
        :param code: 证券代码（sh600150 / 600150 / sh.600150 均可）
        :param last_date: 数据库最新日期 YYYY-MM-DD，None=读取尾部全部
        :return: 标准中文列名 DataFrame（仅last_date之后的数据），可能为空
        """
        code = self._normalize_code(code)
        delta = self._read_day_file_tail(code, last_date)
        if not delta.empty and self.max_bars_per_request:
            # 限制条数，避免一次读取过多
            delta = delta.tail(self.max_bars_per_request)
        if not delta.empty:
            logger.debug(f"📥 [tdx增量] {code} 本地增量 {len(delta)} 条"
                         f"（last_date={last_date}）")
        return delta

    # ============ 入库 ============
    def sync_one(self, code: str, period: str = 'daily',
                 max_rows: int = None) -> int:
        """
        同步单只股票日K增量入库（需提供 db_manager）
        :param code: 证券代码
        :param period: 周期（默认daily）
        :param max_rows: 入库后保留最大条数
        :return: 新增条数
        """
        if self.db is None:
            logger.warning("未提供 db_manager，无法入库")
            return 0
        last_date = self.db.get_last_date(code, period)
        delta = self.fetch_delta(code, last_date)
        if delta.empty:
            return 0
        # 写入数据库（自动触发trim循环覆盖）
        inserted = self.db.upsert_kline(delta, code, period, max_rows=max_rows)
        logger.info(f"✅ [tdx增量] {code} 入库 {inserted} 条"
                    f"（last_date={last_date}）")
        return inserted
