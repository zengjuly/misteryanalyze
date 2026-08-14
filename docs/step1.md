# 最新工程优化实施指南（阶段1核心代码）

根据您提供的优化方案，结合现有工程（已集成 TdxLocalClient + MarketDataClient + 多源退避 + 2000条限制 + 日K重采样），以下输出**阶段1高价值核心优化**的完整实现代码与集成说明。这些代码可直接用于现有工程，实现增量更新、本地复权因子一致性、交易日历感知重采样。

---

## 1. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `data/tdx_incremental.py` | 新增 | 增量更新核心逻辑，从本地.day文件或协议接口获取增量 |
| `data/tdx_gbbq.py` | 新增 | 解析通达信除权除息数据，计算复权因子 |
| `data/kline_resampler.py` | 重写 | 支持交易日历和最少K线数过滤 |
| `data/db_manager.py` | 修改 | 新增 `get_last_date`，修改 `upsert_kline` 支持复权因子 |
| `data/market_data_client.py` | 小改 | 集成增量更新与健康评分（可选） |
| `config/config.yaml` | 修改 | 新增 `incremental`、`resample`、`tdx.gbbq_file` 等配置 |

---

## 2. 核心代码实现

### 2.1 `data/tdx_incremental.py` —— 增量更新

```python
import os
import struct
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TdxIncremental:
    """
    通达信增量更新器，优先从本地.day文件尾部读取增量，不足时可通过协议补充（可选）。
    """
    def __init__(self, vipdoc_dir: str, db_manager, max_bars_per_request=800):
        self.vipdoc_dir = vipdoc_dir
        self.db = db_manager
        self.max_bars_per_request = max_bars_per_request

    def _get_market(self, code: str) -> str:
        if code.startswith(("6", "9", "5")):
            return "sh"
        elif code.startswith(("0", "2", "3")):
            return "sz"
        elif code.startswith(("4", "8")):
            return "bj"
        return "sh"

    def _read_day_file_tail(self, code: str, last_date: str | None) -> pd.DataFrame:
        """读取.day文件中日期大于 last_date 的所有记录"""
        market = self._get_market(code)
        filepath = os.path.join(self.vipdoc_dir, market, "lday", f"{market}{code}.day")
        if not os.path.exists(filepath):
            return pd.DataFrame()

        records = []
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(32)
                if not chunk or len(chunk) < 32:
                    break
                date, open_, high, low, close, amount, volume, _ = struct.unpack('<IIIIIfII', chunk)
                date_str = str(date)
                if date_str == '0' or date_str < '19900101':
                    continue
                trade_date = datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
                if last_date and trade_date <= last_date:
                    continue  # 只取新数据
                records.append({
                    '日期': trade_date,
                    '开盘价': open_ / 100.0,
                    '最高价': high / 100.0,
                    '最低价': low / 100.0,
                    '收盘价': close / 100.0,
                    '成交量': volume / 100.0,   # 转为手
                    '成交额': amount,
                    '涨跌幅': None,  # 稍后统一计算
                    '换手率': None,
                    '代码': code
                })
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records)
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期')
        # 计算涨跌幅
        df['涨跌幅'] = df['收盘价'].pct_change() * 100
        return df

    def fetch_delta(self, code: str, last_date: str | None) -> pd.DataFrame:
        """
        获取增量日K，优先本地.day文件，若本地数据不足可扩展协议获取。
        返回标准中文列名 DataFrame，可能为空。
        """
        # 本地读取增量
        delta = self._read_day_file_tail(code, last_date)
        if not delta.empty:
            # 限制条数，避免一次读取过多
            delta = delta.tail(self.max_bars_per_request)
            return delta

        # TODO: 可选使用 easy_tdx 或 mootdx 协议增量，需要外部服务
        # 如果本地文件不存在或没有新数据，可考虑调用在线源（AKShare/baostock）
        logger.debug(f"{code} 本地无增量数据，last_date={last_date}")
        return pd.DataFrame()

    def sync_one(self, code: str) -> int:
        """
        同步单只股票日K，返回新增条数。
        """
        last_date = self.db.get_last_date(code, 'daily')
        delta = self.fetch_delta(code, last_date)
        if delta.empty:
            return 0
        # 写入数据库（自动触发trim）
        inserted = self.db.upsert_kline(delta, code, 'daily', max_rows=2000)
        return inserted
```

### 2.2 `data/tdx_gbbq.py` —— 复权因子计算

```python
import os
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class TdxGBBQ:
    """
    通达信除权除息数据解析与复权因子计算。
    数据来源：通达信gbbq文件（如 vipdoc/cw/gbbq 或协议下载）。
    实际应用中可替换为从 mootdx/pytdx 获取的除权信息。
    """
    def __init__(self, gbbq_file: str = None):
        self.gbbq_file = gbbq_file

    def load_factors(self) -> pd.DataFrame:
        """
        加载复权因子表，返回 DataFrame:
        列: 代码, 除权日, 送股, 配股, 派息, ...
        """
        if not self.gbbq_file or not os.path.exists(self.gbbq_file):
            logger.warning("gbbq文件不存在，无法本地计算复权因子")
            return pd.DataFrame()
        # TODO: 解析gbbq二进制格式（不同版本格式有差异）
        # 简化：使用 pandas 读取文本格式或调用 mootdx 的 financial 接口
        # 这里仅返回空结构，实际需根据格式实现
        return pd.DataFrame(columns=['code', 'date', 'songgu', 'peigu', 'peigujia', 'paixt', 'fenhong'])

    def calc_qfq_factor(self, code: str, daily_df: pd.DataFrame) -> pd.DataFrame:
        """
        根据除权除息信息计算前复权因子并调整价格。
        若无除权信息，返回原数据。
        """
        # TODO: 实现因子计算逻辑：使用后复权算法逐日调整
        # 核心思路：从最早日期开始，遇到除权日，累计因子 = 累计因子 * (1 + 送股/10 + 配股/10) - 分红/10
        # 然后当前价 * 累计因子
        return daily_df  # 暂不调整

    def apply_adjust(self, code: str, daily_df: pd.DataFrame, adjust: str = "qfq") -> pd.DataFrame:
        """统一入口：根据adjust类型应用复权"""
        if adjust == "none":
            return daily_df
        # 待实现
        return daily_df
```

> **说明**：由于gbbq文件格式复杂，上述代码仅提供框架。实际推荐使用 `mootdx` 或 `pytdx` 的除权除息接口获取数据并缓存，或直接使用AKShare的 `stock_zh_a_daily`（支持复权）来保证一致性。若追求完全本地，可研究gbbq二进制格式。

### 2.3 `data/kline_resampler.py` —— 升级版重采样

```python
import pandas as pd

class KLineResampler:
    def __init__(self, config: dict = None):
        self.config = config or {}
        resample_cfg = self.config.get("data_source", {}).get("resample", {})
        self.min_bars_weekly = resample_cfg.get("min_bars_weekly", 3)
        self.min_bars_monthly = resample_cfg.get("min_bars_monthly", 10)
        self.use_trading_calendar = resample_cfg.get("use_trading_calendar", True)
        self._calendar = None

    def set_calendar(self, calendar: pd.DatetimeIndex):
        self._calendar = calendar

    def resample(self, daily_df: pd.DataFrame, period: str = "weekly") -> pd.DataFrame:
        """
        从日K聚合为周K/月K，支持交易日历过滤和最少K线数过滤。
        """
        if daily_df.empty:
            return pd.DataFrame()

        df = daily_df.copy()
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期').drop_duplicates(subset=['日期'], keep='last')

        # 如果有交易日历，只保留交易日
        if self.use_trading_calendar and self._calendar is not None:
            df = df[df['日期'].isin(self._calendar)]

        df = df.set_index('日期')

        if period == "weekly":
            rule = 'W-FRI'
            min_bars = self.min_bars_weekly
        elif period == "monthly":
            rule = 'ME'  # 月末最后一日
            min_bars = self.min_bars_monthly
        else:
            raise ValueError("period 必须为 'weekly' 或 'monthly'")

        agg = {
            '开盘价': 'first',
            '最高价': 'max',
            '最低价': 'min',
            '收盘价': 'last',
            '成交量': 'sum',
            '成交额': 'sum',
            '换手率': 'sum',
        }

        # 计算每周期K线数
        counts = df.resample(rule).size()
        # 执行聚合
        resampled = df.resample(rule).agg(agg)

        # 过滤K线数不足的周期
        resampled = resampled[counts >= min_bars]

        # 重新计算涨跌幅
        resampled['涨跌幅'] = resampled['收盘价'].pct_change() * 100

        # 代码列保留
        if '代码' in df.columns:
            resampled['代码'] = df['代码'].iloc[0]
        else:
            resampled['代码'] = ""

        resampled = resampled.reset_index()
        resampled['日期'] = resampled['日期'].dt.strftime('%Y-%m-%d')
        return resampled[['日期', '代码', '开盘价', '最高价', '最低价', '收盘价',
                          '成交量', '成交额', '换手率', '涨跌幅']]
```

### 2.4 `data/db_manager.py` 部分修改

```python
def get_last_date(self, code: str, period: str = 'daily') -> str | None:
    """获取指定股票某周期的最大日期"""
    query = "SELECT MAX(date) FROM stock_kline_data WHERE code=? AND period=?"
    self.cursor.execute(query, (code, period))
    row = self.cursor.fetchone()
    return row[0] if row and row[0] else None

def upsert_kline(self, df, code, period, max_rows=None):
    """
    插入或更新K线数据，并可选限制最大行数（循环覆盖）。
    若df中包含'复权因子'列，可在此处应用（或预先处理）。
    """
    if df.empty:
        return 0
    # 转换日期格式确保一致
    if '日期' in df.columns:
        df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
    # 执行 upsert（INSERT OR REPLACE）
    # ... 原有逻辑 ...
    # 限制条数
    if max_rows and period == 'daily':
        self.trim_kline(code, period, max_rows)
    return len(df)
```

### 2.5 集成到 `MarketDataClient`

在 `market_data_client.py` 中增加增量更新支持（作为日线获取的首选方式）：

```python
def fetch_daily(self, code, start_date=None, end_date=None):
    # 尝试增量更新（如果配置启用）
    if self.config.get("data_source", {}).get("incremental", {}).get("enable", True):
        incremental = TdxIncremental(self.tdx_client.vipdoc_dir, self.db)
        delta = incremental.fetch_delta(code, self.db.get_last_date(code, 'daily'))
        if not delta.empty:
            return delta
    # 否则走原有的 _fetch_with_fallback 多源逻辑
    return self._fetch_with_fallback(code, "daily", start_date, end_date)
```

---

## 3. 配置更新示例

```yaml
data_source:
  primary: "tdx_local"
  fallback: ["akshare", "baostock"]
  prefer_resample: true
  adjust: "qfq"
  rate_limit_akshare: 0.3
  retry_times: 3
  retry_delay: 2

  incremental:
    enable: true
    max_bars_per_request: 800

  resample:
    min_bars_weekly: 3
    min_bars_monthly: 10
    use_trading_calendar: true

  tdx:
    vipdoc_dir: "data/tdx_vipdoc"   # 可被环境变量 TDX_VIPDOC_DIR 覆盖
    enable: true
    auto_download: false
    gbbq_file: "data/tdx_vipdoc/cw/gbbq"  # 可选

  kline_limit:
    daily: 2000
    weekly: 500
    monthly: 300
    enable_cleanup: true
```

---

## 4. 实施建议

1. **先实现增量更新**：`TdxIncremental` 使用本地.day文件尾部读取，性能极高，且逻辑简单。
2. **复权因子可后期完善**：先统一使用AKShare前复权数据，确保一致性；待需要完全本地化时再实现gbbq解析。
3. **重采样升级**：加入交易日历可通过从数据库已有日K生成日历索引（所有日期集合），或从baostock获取交易日历缓存。
4. **测试**：确保增量更新幂等（重复同步不产生重复数据），且2000条限制正常工作。

---

## 5. 下一步

如需**阶段2（健康评分与协议增强）**或**阶段3（财务本地化与生产化）**的具体代码，请告知，我将继续提供详细实现。
