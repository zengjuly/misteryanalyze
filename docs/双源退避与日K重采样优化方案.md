# 最终集成方案（合并版）：AKShare + Baostock 双源退避与日K重采样

本方案在保留现有系统 `stock_kline_data` 单表结构与中文列名规范的基础上，引入 **AKShare 主源 + baostock 备用源** 的自动退避机制，并强制/优先使用日K重采样生成周K/月K，保证多周期数据严格对齐。方案整合了“模块化目录结构”与“最小侵入改造”两类思路的优点，上层分析模块无需修改，配置灵活可扩展。

---

## 1. 总体架构

```
上层分析模块（DataProcessor / MysteryDataEngine / main）
          ↓
   MarketDataClient（统一数据入口，主备切换 + 退避）
          ↓
  ┌─────────────────┬─────────────────┐
  │ Primary Source  │ Fallback Source │
  │   (AKShare)     │   (Baostock)    │
  └─────────────────┴─────────────────┘
          ↓
  统一清洗层（_clean_kline，列名映射）
          ↓
  KLineResampler（日K→周K/月K聚合）
          ↓
  SQLite Cache（现有 stock_kline_data 表）
          ↓
  返回标准中文列名 DataFrame
```

- 所有数据源输出统一为中文列：`日期` `代码` `开盘价` `最高价` `最低价` `收盘价` `成交量` `成交额` `换手率` `涨跌幅`
- 主源失败自动切换备用源，指数退避 + 日志，不中断分析流程
- 周K/月K默认由日K重采样生成，配置可切换为原生数据
- 线程安全：Baostock 复用现有全局锁，AKShare 加限速控制

---

## 2. 新增/修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `data/akshare_client.py` | 新增 | AKShare 封装，接口与 `BaostockClient` 对齐 |
| `data/kline_resampler.py` | 新增 | 日K → 周K/月K 聚合器，独立可测试 |
| `data/market_data_client.py` | 新增 | 统一数据入口，主备退避 + 周期选择 |
| `data/data_engine.py` | 修改 | 注入 `MarketDataClient`，`get_kline` 走统一逻辑 |
| `data/data_processor.py` | 修改 | 调用 `MarketDataClient`，替代原 Baostock 直接调用 |
| `config/config.yaml` | 修改 | 新增 `data_source` 配置段 |
| `requirements.txt` | 修改 | 添加 `akshare` |
| `utils/data_utils.py` | 可选新增 | 列名映射表 |

**数据库变更**：无，复用现有 `stock_kline_data` 表。

---

## 3. 配置扩展（`config/config.yaml`）

```yaml
data_source:
  primary: "akshare"           # 主源：akshare / baostock
  fallback: "baostock"         # 备用源，可与主源相同（仅用单源）
  retry_times: 3               # 每个源最大重试次数
  retry_delay: 2               # 初始退避延迟（秒），指数递增
  prefer_resample: true        # true=强制日K重采样周/月；false=优先原生数据
  adjust: "qfq"                # 复权：qfq前复权 / hfq后复权 / none不复权
  rate_limit_akshare: 0.3      # AKShare 请求间隔（秒）
  timeout: 30                  # 单次请求超时（秒）

# 保留原 baostock 配置
baostock:
  # 原有内容...
```

---

## 4. 核心模块实现

### 4.1 `data/akshare_client.py`

```python
import akshare as ak
import pandas as pd
import time

class AkshareClient:
    def __init__(self, rate_limit=0.3):
        self.rate_limit = rate_limit

    def normalize_stock_code(self, code: str) -> str:
        """转为6位数字，如 sh.600000 -> 600000，bj.430047 -> 430047"""
        return code.lower().replace("sh.", "").replace("sz.", "").replace("bj.", "").zfill(6)

    def get_daily_data(self, stock_code, start_date, end_date, adjust="qfq"):
        code = self.normalize_stock_code(stock_code)
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        time.sleep(self.rate_limit)   # 简单限速
        df = ak.stock_zh_a_hist(symbol=code, period="daily",
                                start_date=start, end_date=end, adjust=adjust)
        return self._rename_and_filter(df, code)

    def get_weekly_data(self, stock_code, start_date, end_date, adjust="qfq"):
        code = self.normalize_stock_code(stock_code)
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        time.sleep(self.rate_limit)
        df = ak.stock_zh_a_hist(symbol=code, period="weekly",
                                start_date=start, end_date=end, adjust=adjust)
        return self._rename_and_filter(df, code)

    def get_monthly_data(self, stock_code, start_date, end_date, adjust="qfq"):
        code = self.normalize_stock_code(stock_code)
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        time.sleep(self.rate_limit)
        df = ak.stock_zh_a_hist(symbol=code, period="monthly",
                                start_date=start, end_date=end, adjust=adjust)
        return self._rename_and_filter(df, code)

    def _rename_and_filter(self, df, code):
        if df is None or df.empty:
            return pd.DataFrame()
        rename_map = {
            "日期": "日期", "开盘": "开盘价", "收盘": "收盘价",
            "最高": "最高价", "最低": "最低价", "成交量": "成交量",
            "成交额": "成交额", "换手率": "换手率", "涨跌幅": "涨跌幅"
        }
        df = df.rename(columns=rename_map)
        df["代码"] = code
        df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
        # 字段类型转换
        for col in ["开盘价", "最高价", "最低价", "收盘价", "成交量", "成交额", "换手率", "涨跌幅"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["开盘价", "收盘价"])  # 移除无效行
        return df[["日期", "代码", "开盘价", "最高价", "最低价", "收盘价",
                   "成交量", "成交额", "换手率", "涨跌幅"]]

    def login(self):   # 兼容接口，无需登录
        pass

    def logout(self):
        pass
```

### 4.2 `data/kline_resampler.py`

```python
import pandas as pd

class KLineResampler:
    def resample(self, daily_df: pd.DataFrame, period: str = "weekly") -> pd.DataFrame:
        """从日K聚合为周K(weekly)或月K(monthly)"""
        if daily_df.empty:
            return pd.DataFrame()

        df = daily_df.copy()
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期").drop_duplicates(subset=["日期"], keep="last")
        df = df.set_index("日期")

        rule = "W-FRI" if period == "weekly" else "M"
        agg = {
            "开盘价": "first",
            "最高价": "max",
            "最低价": "min",
            "收盘价": "last",
            "成交量": "sum",
            "成交额": "sum",
            "换手率": "sum",          # 也可按成交量加权，视业务需求
        }
        resampled = df.resample(rule).agg(agg).dropna(subset=["收盘价"])
        # 重新计算涨跌幅
        resampled["涨跌幅"] = resampled["收盘价"].pct_change() * 100
        # 补齐代码列
        if "代码" in df.columns:
            resampled["代码"] = df["代码"].iloc[0]
        else:
            resampled["代码"] = ""
        resampled = resampled.reset_index()
        resampled["日期"] = resampled["日期"].dt.strftime("%Y-%m-%d")
        return resampled[["日期", "代码", "开盘价", "最高价", "最低价", "收盘价",
                          "成交量", "成交额", "换手率", "涨跌幅"]]
```

### 4.3 `data/market_data_client.py`（统一入口 + Fallback）

```python
import time
import logging
import pandas as pd
from data.akshare_client import AkshareClient
from data.baostock_client import BaostockClient
from data.kline_resampler import KLineResampler

class MarketDataClient:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        ds_cfg = config.get("data_source", {})
        self.ak_client = AkshareClient(rate_limit=ds_cfg.get("rate_limit_akshare", 0.3))
        self.bs_client = BaostockClient()
        self.resampler = KLineResampler()
        self.primary = ds_cfg.get("primary", "akshare")
        self.fallback = ds_cfg.get("fallback", "baostock")
        self.retry_times = ds_cfg.get("retry_times", 3)
        self.retry_delay = ds_cfg.get("retry_delay", 2)
        self.prefer_resample = ds_cfg.get("prefer_resample", True)
        self.adjust = ds_cfg.get("adjust", "qfq")

    def fetch_daily(self, code, start_date, end_date):
        return self._fetch_with_fallback(code, "daily", start_date, end_date)

    def fetch_weekly(self, code, start_date, end_date):
        if self.prefer_resample:
            daily = self.fetch_daily(code, start_date, end_date)
            return self.resampler.resample(daily, "weekly")
        return self._fetch_with_fallback(code, "weekly", start_date, end_date)

    def fetch_monthly(self, code, start_date, end_date):
        if self.prefer_resample:
            daily = self.fetch_daily(code, start_date, end_date)
            return self.resampler.resample(daily, "monthly")
        return self._fetch_with_fallback(code, "monthly", start_date, end_date)

    def _fetch_with_fallback(self, code, period, start_date, end_date):
        sources = [self.primary]
        if self.fallback and self.fallback != self.primary:
            sources.append(self.fallback)

        last_error = None
        for src in sources:
            for attempt in range(self.retry_times):
                try:
                    df = self._fetch_from_source(src, code, period, start_date, end_date)
                    if not df.empty:
                        self.logger.info(f"[{src}] {code} {period} 获取成功，{len(df)} 条")
                        return df
                except Exception as e:
                    last_error = e
                    wait = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"[{src}] {code} {period} 第{attempt+1}次失败: {e}，{wait:.1f}s后重试")
                    time.sleep(wait)
            self.logger.error(f"[{src}] {code} {period} 重试耗尽，切换下一数据源")
        self.logger.error(f"{code} {period} 所有数据源均失败，最后错误: {last_error}")
        return pd.DataFrame()

    def _fetch_from_source(self, src, code, period, start_date, end_date):
        adjust = self.adjust
        if src == "akshare":
            if period == "daily":
                return self.ak_client.get_daily_data(code, start_date, end_date, adjust=adjust)
            elif period == "weekly":
                return self.ak_client.get_weekly_data(code, start_date, end_date, adjust=adjust)
            elif period == "monthly":
                return self.ak_client.get_monthly_data(code, start_date, end_date, adjust=adjust)
        elif src == "baostock":
            # 复权映射
            adjustflag = {"qfq": "2", "hfq": "1", "none": "3"}.get(adjust, "2")
            if period == "daily":
                return self.bs_client.get_daily_data(code, start_date, end_date, adjustflag=adjustflag)
            elif period == "weekly":
                return self.bs_client.get_weekly_data(code, start_date, end_date, adjustflag=adjustflag)
            elif period == "monthly":
                return self.bs_client.get_monthly_data(code, start_date, end_date, adjustflag=adjustflag)
        else:
            raise ValueError(f"未知数据源: {src}")
```

### 4.4 修改 `data/data_engine.py`

```python
class MysteryDataEngine:
    def __init__(self, config):
        self.db = DBManager(config)
        self.market_client = MarketDataClient(config)
        # 其他原有初始化...

    def get_kline(self, code, period="daily", start_date=None, end_date=None,
                  force_refresh=False, auto_backfill=True):
        # 1. 缓存查询（原有逻辑）
        if not force_refresh:
            cached = self.db.load_kline(code, period, start_date, end_date)
            if cached is not None and not cached.empty:
                return cached

        # 2. 通过统一客户端获取数据
        if period == "daily":
            df = self.market_client.fetch_daily(code, start_date, end_date)
        elif period == "weekly":
            df = self.market_client.fetch_weekly(code, start_date, end_date)
        elif period == "monthly":
            df = self.market_client.fetch_monthly(code, start_date, end_date)
        else:
            raise ValueError(f"不支持的周期: {period}")

        # 3. 清洗 + 写缓存（复用现有 _clean_kline）
        if not df.empty:
            df = self._clean_kline(df, code, period)
            self.db.upsert_kline(df, code, period)
        return df
```

### 4.5 修改 `data/data_processor.py`

```python
class DataProcessor:
    def __init__(self, config):
        self.market_client = MarketDataClient(config)
        # 其他原有初始化...

    def process_stock_data(self, code, start_date, end_date):
        # 直接使用统一客户端
        daily = self.market_client.fetch_daily(code, start_date, end_date)
        weekly = self.market_client.fetch_weekly(code, start_date, end_date)
        monthly = self.market_client.fetch_monthly(code, start_date, end_date)
        # 后续处理...
```

---

## 5. 数据流示例

1. 上层调用 `MysteryDataEngine.get_kline(code, period="weekly")`
2. `get_kline` 先查询缓存，未命中则调 `MarketDataClient.fetch_weekly`
3. `fetch_weekly` 因 `prefer_resample=true`，先调 `fetch_daily` 获取日K（内部走主备退避）
4. 日K获取成功后，调 `KLineResampler.resample` 聚合出周K
5. 清洗后写入 `stock_kline_data` 表（`period='weekly'`）
6. 返回标准 DataFrame 给上层

---

## 6. 集成实施步骤

1. **依赖安装**：`pip install akshare`，`requirements.txt` 添加 `akshare`
2. **新增文件**：按第 4 节创建 `akshare_client.py`、`kline_resampler.py`、`market_data_client.py`
3. **修改现有文件**：在 `data_engine.py` 和 `data_processor.py` 中注入 `MarketDataClient`，替换原 Baostock 直接调用
4. **更新配置**：在 `config.yaml` 中添加 `data_source` 段（见第 3 节）
5. **单元测试**：
   - `AkshareClient` 单只股票返回格式与列名
   - `KLineResampler` 用已知日K验证周/月聚合正确性
   - `MarketDataClient` 模拟主源失败切换
6. **集成测试**：运行现有分析流程（如三振共振、平台突破），确认结果一致
7. **性能测试**：批量更新时观察 AKShare 限速与 Baostock 锁是否冲突
8. **文档更新**：说明新配置项与使用方式

---

## 7. 风险与优化

- **AKShare 稳定性**：本质为爬虫，易受网站改版影响。保持双源 Fallback + 缓存优先。
- **复权差异**：不同数据源前复权算法存在细微差异，建议统一使用 `qfq`，或同时存不复权数据供对比。
- **批量更新性能**：AKShare 串行请求 + `rate_limit` 可能导致耗时较长。可引入线程池（按源隔离）但需注意 Baostock 全局锁。
- **北交所支持**：AKShare 对北交所支持有限，若需覆盖可后续扩展专门源。
- **扩展性**：未来新增 Tushare、efinance 等，仅需实现与 `AkshareClient` 相同的接口并注册到 `MarketDataClient`。

---

## 8. 预期效果

- **高可用**：主备源自动切换，数据获取成功率大幅提升。
- **周期对齐**：周/月K由日K重采样生成，与日K完全对齐，提升多周期共振分析准确性。
- **向后兼容**：上层分析模块无需改动，原有 `get_kline` 接口保持不变。
- **灵活配置**：主备源、重采样策略、复权方式均可通过配置文件调整。

---

此方案已合并原方案与新参考方案的优点，可直接指导开发。若需要某个文件的完整可运行代码（含异常处理细节），可进一步提供。
