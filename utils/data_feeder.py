#!/usr/bin/env python3
# data_feeder.py - 数据接入适配器（docs/refact1.md §5）
"""统一数据获取层：适配多源客户端，为分析模块提供带均线的标准DataFrame

用法:
    feeder = DataFeeder(config)
    daily = feeder.get_daily('sh600150')      # 含 MA5/10/20/60/250
    weekly = feeder.get_weekly('sh600150')    # 含 MA60_W
    market = feeder.get_market_index()        # {'上证指数': df, ...}
"""
import logging
import os
import sys
from typing import Dict, Optional

import pandas as pd

# 确保 data/ 目录可导入（独立运行扫描脚本时）
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
if _DATA_DIR not in sys.path:
    sys.path.insert(0, _DATA_DIR)

logger = logging.getLogger(__name__)


class DataFeeder:
    """数据接入适配器（docs/refact1.md §5）"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.client = None
        ds_cfg = (config or {}).get('data_source') or {}
        if ds_cfg:
            try:
                from market_data_client import MarketDataClient
                self.client = MarketDataClient(config)
                logger.info(f"🔄 DataFeeder 多源客户端就绪: {self.client.source_order}")
            except Exception as e:
                logger.warning(f"⚠️ DataFeeder 多源客户端初始化失败({e})，"
                               f"使用 Baostock 单源")
        if self.client is None:
            try:
                from multi_source_client import MultiSourceClient
                self.client = MultiSourceClient(config)
            except Exception as e:
                logger.warning(f"⚠️ DataFeeder 回退客户端初始化失败: {e}")
        # 行业/财务客户端（MultiSourceClient 继承 BaostockClient，有行业/财务接口）
        self._industry_client = None

    def get_daily(self, code: str, start_date: str = None,
                  end_date: str = None) -> Optional[pd.DataFrame]:
        """获取日K并附加常用均线（MA5/10/20/60/250）
        :return: 含指标列的日K DataFrame（日期升序），失败返回 None
        """
        try:
            if self.client is None:
                return None
            if hasattr(self.client, 'fetch_daily'):
                df = self.client.fetch_daily(code, start_date, end_date)
            else:
                df = self.client.get_daily_data(code, start_date, end_date)
            if df is None or df.empty:
                return None
            df = df.copy()
            close_col = '收盘价' if '收盘价' in df.columns else 'close'
            for w in [5, 10, 20, 60, 250]:
                df[f'MA{w}'] = df[close_col].rolling(w).mean()
            return df
        except Exception as e:
            logger.warning(f"⚠️ DataFeeder.get_daily({code}) 异常: {str(e)[:80]}")
            return None

    def get_weekly(self, code: str, start_date: str = None,
                   end_date: str = None) -> Optional[pd.DataFrame]:
        """获取周K并附加 60 周均线（MA60_W）
        :return: 周K DataFrame（日期升序），失败返回 None
        """
        try:
            if self.client is None:
                return None
            if hasattr(self.client, 'fetch_weekly'):
                df = self.client.fetch_weekly(code, start_date, end_date)
            else:
                df = self.client.get_weekly_data(code, start_date, end_date)
            if df is None or df.empty:
                return None
            df = df.copy()
            close_col = '收盘价' if '收盘价' in df.columns else 'close'
            df['MA60_W'] = df[close_col].rolling(60).mean()
            return df
        except Exception as e:
            logger.warning(f"⚠️ DataFeeder.get_weekly({code}) 异常: {str(e)[:80]}")
            return None

    def get_market_index(self, codes: Dict[str, str] = None) -> Dict[str, pd.DataFrame]:
        """获取主要指数日K（db缓存优先，二次读取毫秒级）
        :param codes: {指数名: 代码}，默认 上证指数/深证成指/创业板指
        :return: {指数名: DataFrame}
        """
        codes = codes or {'上证指数': 'sh.000001', '深证成指': 'sz.399001',
                          '创业板指': 'sz.399006'}
        result = {}
        for name, code in codes.items():
            df = None
            db_code = code if '.' in code else code
            # 1. db 缓存（最新日期 3 天内直接复用，避免每次分析走在线源卡顿）
            try:
                from datetime import datetime, timedelta
                from db_manager import MysteryDB
                db = MysteryDB()
                cached = db.load_kline(db_code, 'daily')
                if cached is not None and not cached.empty:
                    last = str(cached['date'].max())[:10]
                    age = (datetime.now()
                           - datetime.strptime(last, '%Y-%m-%d')).days
                    if age <= 3:
                        m = {'date': '日期', 'open': '开盘价', 'high': '最高价',
                             'low': '最低价', 'close': '收盘价',
                             'volume': '成交量', 'amount': '成交额',
                             'turn': '换手率'}
                        df = cached.rename(columns=m)
            except Exception:
                pass
            # 2. 在线源拉取 + 写缓存
            if df is None or df.empty:
                df = self.get_daily(code)
                if df is not None and not df.empty:
                    try:
                        from db_manager import MysteryDB
                        MysteryDB().upsert_kline(df, db_code, 'daily',
                                                 max_rows=1200)
                    except Exception:
                        pass
            if df is not None and not df.empty:
                result[name] = df
        if not result:
            logger.warning("⚠️ DataFeeder 指数获取全部失败")
        return result

    def get_all_stock_code_name(self) -> Dict[str, str]:
        """全市场股票代码-名称字典（docs/ui2.md 模糊搜索用）
        :return: {code: name}，code 为 sh600150 格式（无点）
        """
        try:
            from db_manager import MysteryDB
            db = MysteryDB()
            df = db.get_stock_info(limit=None)
            if df is not None and not df.empty and 'code_name' in df.columns:
                out = {}
                for c, n in zip(df['code'], df['code_name']):
                    if n and str(n) != 'nan' and c:
                        out[str(c).replace('.', '')] = str(n)
                if out:
                    return out
        except Exception as e:
            logger.warning(f"⚠️ DataFeeder.get_all_stock_code_name 异常: {str(e)[:80]}")
        return {}

    def get_industry_data(self, refresh: bool = False) -> Dict:
        """获取行业分类数据（docs/ui.md §6 + ui2.md 通达信行业板块）
        优先读 db stock_industry_info（已填充）；为空则从多源客户端拉取并自动填充 db
        :param refresh: 强制从在线源刷新行业分类
        :return: {'code_map': {code: 行业名}, 'industry_codes': {行业名: [codes]}}
        """
        # 0. TDX 本地板块优先（docs/081601.md §二: 通达信行业板块）
        #    本机无 TDX_HOME/block 文件 → 返回空 → 继续 db 缓存/在线源
        try:
            from tdx_block_client import TdxBlockClient
            tbc = TdxBlockClient()
            blocks = tbc.get_industry_blocks()
            if blocks is not None and not blocks.empty:
                code_map = tbc.to_code_map(blocks)
                if code_map:
                    try:
                        from db_manager import MysteryDB
                        MysteryDB().update_industries(code_map)
                        logger.info(f"🏢 通达信行业板块已填充 db: "
                                    f"{len(code_map)} 只")
                    except Exception as e:
                        logger.warning(f"⚠️ 通达信板块填充 db 失败: {e}")
                    industry_codes = {}
                    for c, ind in code_map.items():
                        industry_codes.setdefault(str(ind), []).append(c)
                    return {'code_map': code_map,
                            'industry_codes': industry_codes,
                            'source': 'tdx'}
        except Exception as e:
            logger.debug(f"TDX 板块读取跳过: {str(e)[:60]}")

        # 1. 优先 db 缓存
        if not refresh:
            try:
                from db_manager import MysteryDB
                db = MysteryDB()
                df = db.get_stock_info(limit=None)
                if df is not None and not df.empty and 'industry' in df.columns:
                    filled = df[df['industry'].notna()
                                & (df['industry'].astype(str) != '')
                                & (df['industry'].astype(str) != 'nan')]
                    if len(filled) > 100:  # 已填充足够数据
                        code_map = dict(zip(filled['code'], filled['industry']))
                        industry_codes = {}
                        for c, ind in code_map.items():
                            industry_codes.setdefault(str(ind), []).append(c)
                        return {'code_map': code_map,
                                'industry_codes': industry_codes}
            except Exception as e:
                logger.warning(f"⚠️ DataFeeder 行业缓存读取失败: {str(e)[:60]}")
        # 2. 在线源拉取（东财行业主源——名称简短接近通达信风格；失败回退 baostock）
        try:
            from utils.em_industry import fetch_em_industry
            em = fetch_em_industry()
            if em and em.get('code_map'):
                code_map, industry_codes = em['code_map'], em['industry_codes']
            else:
                # 兜底: baostock 证监会行业分类
                if self._industry_client is None:
                    from multi_source_client import MultiSourceClient
                    self._industry_client = MultiSourceClient(self.config)
                if not getattr(self._industry_client, 'login_success', False):
                    self._industry_client.login()
                df = self._industry_client.get_industry_data()
                if df is None or df.empty:
                    return {}
                code_map, industry_codes = {}, {}
                for _, row in df.iterrows():
                    code = row.get('code', '')
                    industry = row.get('industry', '')
                    if code and industry and str(industry) != 'nan':
                        code_map[str(code)] = str(industry)
                        industry_codes.setdefault(str(industry), []).append(str(code))
            if code_map:
                # 3. 自动填充 db（板块监控/扫描板块筛选离线可用）
                try:
                    from db_manager import MysteryDB
                    db = MysteryDB()
                    n = db.update_industries(code_map)
                    logger.info(f"🏢 行业分类已填充 db: {n} 只, "
                                f"{len(industry_codes)} 个行业")
                except Exception as e:
                    logger.warning(f"⚠️ 行业分类填充 db 失败: {str(e)[:60]}")
                return {'code_map': code_map,
                        'industry_codes': industry_codes}
        except Exception as e:
            logger.warning(f"⚠️ DataFeeder.get_industry_data 异常: {str(e)[:80]}")
        return {}
