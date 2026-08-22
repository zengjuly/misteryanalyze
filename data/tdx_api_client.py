#!/usr/bin/env python3
# tdx_api_client.py - 本地 tdx-api Docker 容器 REST 客户端（docs/0821.md 第二备用源）
"""Go tdx-api 容器（localhost:8080）毫秒级 K 线提取
实际响应（2026-08 实测）:
  GET /api/kline-all?code=600519&type=day
  → {"code":0,"data":{"count":5988,"list":[{"Open":34510,"High":37780,
      "Low":32850,"Close":35550,"Volume":406318,"Amount":...,"Time":"..."}]}}
  价格字段为原始价×1000（需 /1000）；无换手率/量比（不伪造，上游补齐逻辑处理）
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


class TdxApiClient:
    """tdx-api 本地容器 REST 客户端（第二备用源）"""

    def __init__(self, config: dict = None):
        self.cfg = ((config or {}).get('data_source', {})
                    .get('tdx_api_config', {}))
        self.api_url = self.cfg.get('api_url', 'http://localhost:8080/api')
        self.timeout = float(self.cfg.get('timeout', 5))

    def fetch_daily(self, stock_code: str, days: int = 1100,
                    start_date: str = None, end_date: str = None,
                    period: str = 'daily') -> pd.DataFrame:
        """从本地 tdx-api 容器拉取日K并统一为中文列（price×1000 → 元）
        接口要求带交易所前缀大写代码（SZ000001/SH600519）——修复: 原来传纯数字
        指数走 /api/index（sh000001/sz399001 小写前缀），股票走 /api/kline-all
        """
        pure = stock_code.replace('.', '').replace('sh', '').replace('sz', '')
        mkt = 'SH' if stock_code.startswith('sh') else (
            'SZ' if stock_code.startswith('sz') else 'BJ')
        api_code = f"{mkt}{pure}"
        # 指数判定（sh000xxx/sz399xxx/bj899xxx）→ /api/index 接口
        _is_idx = (
            (stock_code.startswith('sh') and pure.startswith('000'))
            or (stock_code.startswith('sz') and pure.startswith('399'))
            or (stock_code.startswith('bj') and pure.startswith('899'))
        )
        endpoint = 'index' if _is_idx else 'kline-all'
        try:
            import requests
            res = requests.get(
                f"{self.api_url}/{endpoint}",
                params={'code': api_code, 'type': 'day'},
                timeout=self.timeout).json()
        except Exception as e:
            logger.debug(f"tdx-api 请求异常 [{stock_code}]: {str(e)[:80]}")
            return pd.DataFrame()
        data = (res or {}).get('data', {}) if isinstance(res, dict) else {}
        # 兼容 /api/kline-all（list）与 /api/index（List，大写 L）
        items = (data.get('list') if isinstance(data, dict) else None) \
            or (data.get('List') if isinstance(data, dict) else None) or []
        if not items:
            return pd.DataFrame()
        df = pd.DataFrame(items)
        out = pd.DataFrame()
        out['日期'] = pd.to_datetime(df['Time'], utc=True,
                                     errors='coerce').dt.tz_localize(None) \
            if 'Time' in df.columns else pd.NaT
        out['开盘价'] = df.get('Open', 0).astype(float) / 1000.0
        out['最高价'] = df.get('High', 0).astype(float) / 1000.0
        out['最低价'] = df.get('Low', 0).astype(float) / 1000.0
        out['收盘价'] = df.get('Close', 0).astype(float) / 1000.0
        out['成交量'] = df.get('Volume', 0).astype(float)
        out['成交额'] = df.get('Amount', 0).astype(float)
        out['换手率'] = None  # 备用源缺换手率——不伪造（上游完整性检查处理）
        out = out.dropna(subset=['日期']).sort_values('日期')
        if start_date:
            out = out[out['日期'] >= pd.to_datetime(start_date)]
        if end_date:
            out = out[out['日期'] <= pd.to_datetime(end_date)]
        if len(out) > days:
            out = out.tail(days)
        return out.reset_index(drop=True)

    def fetch_financials(self, stock_code: str) -> dict:
        """tdx-api 不承接财务，返回空（触发上游现有财务链路）"""
        return {}

    def fetch_block_info(self) -> dict:
        return {}

    def fetch_block_daily(self, block_name: str, days: int = 1100,
                          start_date: str = None,
                          end_date: str = None) -> pd.DataFrame:
        """容器端不承接板块业务，返回空优雅触发链条下移（docs/0821.md）"""
        return pd.DataFrame()
