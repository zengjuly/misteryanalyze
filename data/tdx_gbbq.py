#!/usr/bin/env python3
# tdx_gbbq.py - 通达信除权除息(gbbq)解析与前复权因子计算（基于docs/step1.md阶段1优化）
"""
TdxGBBQ - 通达信除权除息数据解析与复权因子计算
================================================
理论来源: docs/step1.md（最新工程优化实施指南 - 阶段1核心代码）

功能:
  1. 解析通达信 gbbq 文件（除权除息记录）→ 复权因子表
  2. 计算前复权(qfq)/后复权(hfq)因子并应用调整
  3. 无 gbbq 文件时 graceful 降级（返回空，由上层连续性检查兜底）

gbbq 文件格式（60字节/条，不同通达信版本有差异）:
  date    (I,  4B)  除权日 YYYYMMDD
  code    (7s, 7B)  证券代码(6位+市场标识或纯6位)
  songgu  (f,  4B)  每股送股
  peigu   (f,  4B)  每股配股
  peigujia(f,  4B)  配股价
  songzhuan(f, 4B)  每股转增
  fenhong (f,  4B)  每股派息(税前)
  ... 其余保留字段

复权算法（以除权日实际价格比计算，数学上等价于精确前复权）:
  前复权: 最新交易日因子=1；自最新向最早遍历除权日，
          除权日及之后价格保持，除权日之前价格 ×= (除权日收盘 / 除权日前一交易日收盘)
  后复权: 因子从最早累计 ×= (除权日前收 / 除权日收)

说明:
  - 若无除权信息（文件缺失/解析失败），apply_adjust 返回原数据，
    factors_available=False 供上层决策（回退在线源保证复权一致性）
"""

import logging
import os
import struct
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# gbbq 记录格式（60字节）: date(4) code(7) songgu(4) peigu(4) peigujia(4)
#                          songzhuan(4) fenhong(4) 其余保留(29字节)
GBBQ_RECORD_SIZE = 60
GBBQ_FMT = '<I7s6f'  # 4 + 7 + 24 = 35 字节（不足60，其余跳过）


class TdxGBBQ:
    """通达信除权除息解析与前复权因子计算"""

    def __init__(self, gbbq_file: Optional[str] = None):
        self.gbbq_file = gbbq_file
        self._factors: Optional[pd.DataFrame] = None

    # ============ 因子表加载 ============
    @property
    def factors_available(self) -> bool:
        """是否成功加载了除权因子表"""
        if self._factors is None:
            self._factors = self.load_factors()
        return self._factors is not None and not self._factors.empty

    def load_factors(self) -> pd.DataFrame:
        """
        加载复权因子表（解析本地gbbq文件）
        返回 DataFrame: code, date, songgu, peigu, peigujia, songzhuan, fenhong
        文件不存在/解析失败 → 空DataFrame（graceful降级）
        """
        if not self.gbbq_file or not os.path.exists(self.gbbq_file):
            logger.warning("gbbq文件不存在，无法本地计算复权因子"
                           "（复权一致性由在线源保证）")
            return pd.DataFrame()

        records = []
        try:
            with open(self.gbbq_file, 'rb') as f:
                while True:
                    chunk = f.read(GBBQ_RECORD_SIZE)
                    if not chunk or len(chunk) < GBBQ_RECORD_SIZE:
                        break
                    try:
                        date_i, code_b, songgu, peigu, peigujia, \
                            songzhuan, fenhong = struct.unpack(GBBQ_FMT, chunk[:35])
                    except struct.error:
                        continue
                    code = code_b.decode('ascii', errors='ignore').strip('\x00')
                    if not code or not code.isdigit():
                        continue
                    date_str = str(date_i)
                    if date_str == '0' or len(date_str) != 8:
                        continue
                    records.append({
                        'code': code,
                        'date': (f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"),
                        'songgu': songgu, 'peigu': peigu,
                        'peigujia': peigujia, 'songzhuan': songzhuan,
                        'fenhong': fenhong,
                    })
        except Exception as e:
            logger.error(f"❌ 解析gbbq文件失败({self.gbbq_file}): {e}")
            return pd.DataFrame()

        if not records:
            logger.warning(f"gbbq文件无有效记录: {self.gbbq_file}")
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        logger.info(f"📋 gbbq因子表加载: {len(df)} 条除权记录"
                    f"（{df['code'].nunique()} 只股票）")
        return df

    def get_events(self, code: str) -> pd.DataFrame:
        """获取单只股票的除权事件表（按日期升序）"""
        if not self.factors_available:
            return pd.DataFrame()
        code6 = str(code).replace('sh', '').replace('sz', '').replace('bj', '')
        code6 = ''.join(ch for ch in code6 if ch.isdigit())
        ev = self._factors[self._factors['code'].astype(str).str[-6:] == code6]
        return ev.sort_values('date')

    # ============ 复权因子计算 ============
    @staticmethod
    def calc_qfq_factor(daily_df: pd.DataFrame,
                        events: pd.DataFrame) -> pd.DataFrame:
        """
        计算前复权因子序列（精确算法：用除权日实际价格比）
        :param daily_df: 原始(不复权)日K，含 日期/收盘价
        :param events: 除权事件表，含 date（除权日）
        :return: DataFrame[日期, qfq_factor]，因子=1 表示最新价基准
        """
        if daily_df is None or daily_df.empty:
            return pd.DataFrame(columns=['日期', 'qfq_factor'])
        df = daily_df.copy()
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期').drop_duplicates(subset=['日期'], keep='last')
        if events is None or events.empty:
            # 无除权事件 → 因子全1
            return pd.DataFrame({'日期': df['日期'], 'qfq_factor': 1.0})

        closes = df.set_index('日期')['收盘价']
        factors = pd.Series(1.0, index=closes.index)
        cum = 1.0
        ex_dates = sorted(pd.to_datetime(events['date']).dt.normalize().unique(),
                          reverse=True)
        for ex in ex_dates:
            # 找除权日及前一交易日
            pos = closes.index.searchsorted(ex)
            # pos 是 ex 之前的位置；除权日当天索引
            day_idx = closes.index.searchsorted(ex, side='right') - 1
            if day_idx < 0:
                continue
            if closes.index[day_idx] != ex:
                continue  # 除权日不在样本内
            if day_idx - 1 < 0:
                continue
            pre = closes.iloc[day_idx - 1]   # 除权日前一交易日收盘（原始价）
            post = closes.iloc[day_idx]      # 除权日收盘（原始价，除权后）
            if pre and post and pre > 0:
                ratio = post / pre           # 除权跳变比例
                if 0 < ratio < 1:            # 除权日价格向下跳变
                    cum *= ratio
            # 除权日之前（含当天之前的日期）因子 = cum
            factors.iloc[:day_idx] = cum
        return pd.DataFrame({'日期': df['日期'], 'qfq_factor': factors.values})

    @staticmethod
    def calc_hfq_factor(daily_df: pd.DataFrame,
                        events: pd.DataFrame) -> pd.DataFrame:
        """
        计算后复权因子序列（从最早累计，除权日向上调整）
        :return: DataFrame[日期, hfq_factor]
        """
        if daily_df is None or daily_df.empty:
            return pd.DataFrame(columns=['日期', 'hfq_factor'])
        df = daily_df.copy()
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期').drop_duplicates(subset=['日期'], keep='last')
        if events is None or events.empty:
            return pd.DataFrame({'日期': df['日期'], 'hfq_factor': 1.0})

        closes = df.set_index('日期')['收盘价']
        factors = pd.Series(1.0, index=closes.index)
        cum = 1.0
        ex_dates = sorted(pd.to_datetime(events['date']).dt.normalize().unique())
        for ex in ex_dates:
            day_idx = closes.index.searchsorted(ex, side='right') - 1
            if day_idx < 0 or closes.index[day_idx] != ex:
                continue
            if day_idx - 1 < 0:
                continue
            pre = closes.iloc[day_idx - 1]
            post = closes.iloc[day_idx]
            if pre and post and post > 0:
                ratio = pre / post           # 后复权向上调整
                if ratio > 1:
                    cum *= ratio
            factors.iloc[day_idx:] = cum     # 除权日及之后
        return pd.DataFrame({'日期': df['日期'], 'hfq_factor': factors.values})

    # ============ 应用复权 ============
    def apply_adjust(self, code: str, daily_df: pd.DataFrame,
                     adjust: str = "qfq") -> pd.DataFrame:
        """
        统一入口：根据 adjust 类型应用复权
        :param code: 证券代码
        :param daily_df: 原始日K（标准中文列名）
        :param adjust: qfq前复权 / hfq后复权 / none不复权
        :return: 调整后的日K（价格列已复权，量额不变）
        """
        if adjust == "none" or daily_df is None or daily_df.empty:
            return daily_df
        events = self.get_events(code)
        if events.empty:
            logger.debug(f"{code} 无除权事件，跳过复权调整")
            return daily_df

        df = daily_df.copy()
        if adjust == "qfq":
            fac = self.calc_qfq_factor(df, events)
        elif adjust == "hfq":
            fac = self.calc_hfq_factor(df, events)
        else:
            logger.warning(f"未知复权类型: {adjust}，返回原数据")
            return daily_df

        if fac.empty:
            return daily_df
        # 按日期对齐因子并应用到价格列（仅处理存在的价格列）
        df['日期'] = pd.to_datetime(df['日期'])
        fac_map = dict(zip(fac['日期'], fac[fac.columns[1]]))
        df['_f'] = df['日期'].map(fac_map).fillna(1.0)
        for col in ['开盘价', '最高价', '最低价', '收盘价']:
            if col in df.columns:
                df[col] = df[col] * df['_f']
        df = df.drop(columns=['_f'])
        # 重算涨跌幅
        if '涨跌幅' in df.columns:
            df['涨跌幅'] = df['收盘价'].pct_change() * 100
        logger.debug(f"🔄 {code} 应用{adjust}复权调整（{len(fac)}个因子）")
        return df
