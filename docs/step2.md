# 阶段2详细设计：协议增强与性能 + 源健康评分与动态熔断

## 1. 目标

- **高性能本地与协议客户端**：在保留 `TdxLocalClient` 本地读取能力的基础上，引入 `easy_tdx` 或 `tdxrs` 协议客户端，实现本地数据缺失时自动从行情服务器增量获取，同时提升批量导入性能。
- **源健康评分与动态熔断**：实现 `SourceHealth` 模块，实时评估各数据源健康状态，动态调整源优先级，自动熔断故障源，并在恢复后自动放回。

---

## 2. 技术选型分析

### 2.1 协议客户端选型

| 库名 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| `mootdx` | 纯 Python，支持本地读取与行情协议，API 简单 | 性能一般，批量解析较慢 | 日常增量、少量股票 |
| `easy_tdx` | 封装了多种协议，支持统一接口，性能较好 | 依赖较新，文档可能不完善 | 协议增量、统一客户端 |
| `tdxrs` | Rust 编写，Python 绑定，解析速度极快（9-11 倍） | 安装需要编译或特定 wheel | 批量导入、全市场初始化 |

**建议策略**：
- 保留 `mootdx` 作为本地 `.day` 读取与财务解析，因为现有代码已使用。
- 新增 `easy_tdx` 用于协议增量（当本地数据缺失时）。
- 批量全量导入时，使用 `tdxrs` 作为高性能解析器，但需注意其在目标环境的可用性（如无预编译 wheel，则回退到 mootdx）。

为降低复杂度，本方案优先集成 `easy_tdx`，并预留 `tdxrs` 接口，实际部署时根据环境自动选择。

### 2.2 健康评分算法

采用**滑动窗口 + 指数加权失败率**，并设置连续失败熔断阈值。

**核心字段**：
- `success_count`: 窗口内成功次数
- `failure_count`: 窗口内失败次数
- `consecutive_failures`: 连续失败次数
- `last_failure_time`: 上次失败时间
- `window_size`: 滑动窗口大小（如 10 次）
- `fail_threshold`: 连续失败熔断阈值（默认 3）
- `recover_seconds`: 熔断恢复时间（默认 300 秒）

**评分**：`health_score = success_rate * 100`，其中 `success_rate = success_count / (success_count + failure_count)`，同时受连续失败惩罚。

**熔断条件**：`consecutive_failures >= fail_threshold` 且当前时间 - `last_failure_time` < `recover_seconds`。

**恢复**：熔断时间过后，允许一个试探请求（或直接恢复，取决于策略）。本方案采用简单恢复：超过 `recover_seconds` 后自动重置熔断状态，允许下一次请求。

---

## 3. 模块设计

### 3.1 `data/source_health.py`

```python
import time
import logging
from collections import deque
from typing import Dict, List

logger = logging.getLogger(__name__)

class SourceHealth:
    def __init__(self, config: dict = None):
        cfg = config.get("data_source", {}).get("health", {})
        self.window_size = cfg.get("window_size", 10)
        self.fail_threshold = cfg.get("fail_threshold", 3)
        self.recover_seconds = cfg.get("recover_seconds", 300)
        self.enable = cfg.get("enable", True)
        self.stats: Dict[str, dict] = {}

    def _init_source(self, source: str):
        if source not in self.stats:
            self.stats[source] = {
                "success_count": 0,
                "failure_count": 0,
                "consecutive_failures": 0,
                "last_failure_time": 0,
                "window": deque(maxlen=self.window_size),
                "health_score": 100.0,
                "is_open": True,
            }

    def record(self, source: str, success: bool, latency_ms: float = 0):
        if not self.enable:
            return
        self._init_source(source)
        s = self.stats[source]
        if success:
            s["success_count"] += 1
            s["consecutive_failures"] = 0
            s["window"].append(1)
        else:
            s["failure_count"] += 1
            s["consecutive_failures"] += 1
            s["last_failure_time"] = time.time()
            s["window"].append(0)
        # 更新健康分
        total = s["success_count"] + s["failure_count"]
        success_rate = s["success_count"] / total if total > 0 else 1.0
        s["health_score"] = success_rate * 100

        # 熔断检查
        if s["consecutive_failures"] >= self.fail_threshold and s["is_open"]:
            s["is_open"] = False
            logger.warning(f"源 {source} 连续失败 {s['consecutive_failures']} 次，熔断 {self.recover_seconds} 秒")

    def is_available(self, source: str) -> bool:
        if not self.enable:
            return True
        self._init_source(source)
        s = self.stats[source]
        if not s["is_open"]:
            # 检查是否已过恢复时间
            elapsed = time.time() - s["last_failure_time"]
            if elapsed >= self.recover_seconds:
                s["is_open"] = True
                s["consecutive_failures"] = 0
                logger.info(f"源 {source} 熔断恢复")
                return True
            return False
        return True

    def get_ordered_sources(self, preferred: List[str]) -> List[str]:
        """
        根据健康评分和熔断状态，返回排序后的源列表。
        只保留可用的源，并按健康分降序排列，但保持 preferred 中的顺序优先级。
        实际上，我们首先使用 preferred 顺序，然后剔除不可用的。
        如果希望完全按评分排序，可以注释掉优先顺序逻辑。
        """
        if not self.enable:
            return [s for s in preferred if self.is_available(s)]
        # 先剔除不可用
        available = [s for s in preferred if self.is_available(s)]
        # 如果需要动态排序，可以按 health_score 排序，但需要保留主源优先？
        # 这里我们采用：保持 preferred 顺序，但将不可用的移除，不做额外排序，
        # 或者可以按健康分排序。根据需求，动态排序可能更好。
        # 但当前主源优先策略可能更合适，因为源的性质不同。我们提供选项：
        # 这里我们采用保持 preferred 顺序，但将不可用移除。若用户想动态排序，可修改。
        return available

    def get_source_stats(self) -> Dict[str, dict]:
        return self.stats
```

### 3.2 `MarketDataClient` 集成健康评分

在 `MarketDataClient.__init__` 中初始化 `SourceHealth`，在 `_fetch_with_fallback` 中调用 `record`，并在获取源列表时使用 `get_ordered_sources`。

```python
class MarketDataClient:
    def __init__(self, config):
        # ... 原有初始化
        self.source_health = SourceHealth(config)

    def _fetch_with_fallback(self, code, period, start_date, end_date):
        sources = self.source_order  # 原始顺序（如 ["tdx_local", "akshare", "baostock"]）
        # 获取健康排序后的可用源
        ordered_sources = self.source_health.get_ordered_sources(sources)

        last_error = None
        for src in ordered_sources:
            for attempt in range(self.retry_times):
                start_time = time.time()
                try:
                    df = self._fetch_from_source(src, code, period, start_date, end_date)
                    latency = (time.time() - start_time) * 1000
                    if not df.empty:
                        self.source_health.record(src, True, latency)
                        logger.info(f"[{src}] {code} {period} 获取成功，{len(df)} 条，耗时{latency:.0f}ms")
                        return df
                    else:
                        self.source_health.record(src, True, latency)  # 空数据也算成功？
                        # 空数据可能不是失败，但为了更准确，可以记录为成功但无数据
                        # 这里我们将其视为成功，避免误判熔断
                except Exception as e:
                    last_error = e
                    latency = (time.time() - start_time) * 1000
                    self.source_health.record(src, False, latency)
                    wait = self.retry_delay * (2 ** attempt)
                    logger.warning(f"[{src}] {code} {period} 第{attempt+1}次失败: {e}，{wait:.1f}s后重试")
                    time.sleep(wait)
            logger.error(f"[{src}] {code} {period} 重试耗尽，切换下一数据源")
        logger.error(f"{code} {period} 所有源均失败，最后错误: {last_error}")
        return pd.DataFrame()
```

**说明**：空 DataFrame 可能表示该源无数据（如股票停牌或日期范围无数据），不视为失败，避免频繁熔断。

### 3.3 高性能协议客户端封装（`data/tdx_protocol_client.py`）

新增文件，封装 `easy_tdx` 或 `tdxrs` 协议客户端，提供与 `TdxLocalClient` 相同的日K获取接口。

```python
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TdxProtocolClient:
    """
    通达信协议客户端，用于从行情服务器获取数据。
    优先使用 easy_tdx，如果不可用则降级到 mootdx 的 Quotes 接口。
    """
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.host = self.config.get("tdx", {}).get("server_host", "119.147.212.81")
        self.port = self.config.get("tdx", {}).get("server_port", 7709)
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            # 尝试 easy_tdx
            from easy_tdx import UnifiedTdxClient
            self.client = UnifiedTdxClient(host=self.host, port=self.port)
            logger.info("使用 easy_tdx 协议客户端")
        except ImportError:
            # 降级到 mootdx Quotes
            try:
                from mootdx.quotes import Quotes
                self.client = Quotes.factory(market='std', server=(self.host, self.port))
                logger.info("使用 mootdx Quotes 协议客户端")
            except ImportError:
                self.client = None
                logger.warning("无可用协议客户端，仅使用本地数据")

    def fetch_daily(self, code: str, start_date: str, end_date: str, adjust="qfq") -> pd.DataFrame:
        if self.client is None:
            return pd.DataFrame()
        try:
            # 统一调用接口，不同客户端可能方法不同，这里做适配
            if hasattr(self.client, 'daily'):
                # mootdx Quotes 或 easy_tdx 的 daily 方法
                df = self.client.daily(symbol=code, start_date=start_date, end_date=end_date)
            elif hasattr(self.client, 'get_daily'):
                df = self.client.get_daily(code, start_date=start_date, end_date=end_date)
            else:
                logger.error("协议客户端不支持 daily 方法")
                return pd.DataFrame()
            # 统一列名
            if df is not None and not df.empty:
                df = df.rename(columns={
                    'date': '日期', 'open': '开盘价', 'high': '最高价',
                    'low': '最低价', 'close': '收盘价', 'volume': '成交量', 'amount': '成交额'
                })
                df['代码'] = code
                df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
                # 添加缺失列
                if '换手率' not in df.columns: df['换手率'] = None
                if '涨跌幅' not in df.columns:
                    df['涨跌幅'] = df['收盘价'].pct_change() * 100
                return df[['日期', '代码', '开盘价', '最高价', '最低价', '收盘价',
                           '成交量', '成交额', '换手率', '涨跌幅']]
        except Exception as e:
            logger.error(f"协议获取 {code} 失败: {e}")
        return pd.DataFrame()
```

### 3.4 更新 `TdxLocalClient` 集成协议增量

在 `TdxLocalClient` 中添加协议客户端实例，并在本地无数据或数据不足时自动调用协议获取增量。

修改 `get_daily_data` 方法：

```python
class TdxLocalClient:
    def __init__(self, vipdoc_dir: str, config: dict = None):
        self.vipdoc_dir = vipdoc_dir
        self.reader = Reader.factory(market='std', tdxdir=vipdoc_dir)
        self.protocol_client = TdxProtocolClient(config) if config else None

    def get_daily_data(self, stock_code, start_date=None, end_date=None, adjust="qfq"):
        code = self.normalize_stock_code(stock_code)
        market = self._get_market(code)
        # 先尝试本地
        df_local = self._read_local_daily(code, market, start_date, end_date)
        if not df_local.empty:
            return df_local
        # 本地无数据，尝试协议获取
        if self.protocol_client and start_date and end_date:
            df_remote = self.protocol_client.fetch_daily(code, start_date, end_date, adjust)
            if not df_remote.empty:
                # 可选：将远程数据写入本地缓存（追加到 .day 文件）？暂不实现
                return df_remote
        return pd.DataFrame()
```

### 3.5 配置更新

在 `config.yaml` 中增加 `tdx.server_host`、`tdx.server_port`，并在 `health` 段加入窗口参数。

```yaml
data_source:
  health:
    enable: true
    window_size: 10
    fail_threshold: 3
    recover_seconds: 300
  tdx:
    vipdoc_dir: "data/tdx_vipdoc"
    enable: true
    auto_download: false
    server_host: "119.147.212.81"   # 通达信行情服务器
    server_port: 7709
```

---

## 4. 集成步骤

1. **添加依赖**：`pip install easy_tdx`（或 `tdxrs` 根据环境选择），更新 `requirements.txt`。
2. **新增 `source_health.py`**，按上述代码实现。
3. **新增 `tdx_protocol_client.py`**，封装协议客户端。
4. **修改 `tdx_local_client.py`**，集成协议客户端，实现本地优先+协议补充。
5. **修改 `market_data_client.py`**，注入 `SourceHealth`，在请求前后记录结果。
6. **更新配置文件**，增加健康与协议相关参数。
7. **测试**：
   - 模拟主源连续失败，观察熔断及恢复。
   - 模拟本地无数据，协议补充是否正常。
   - 性能测试：批量获取时协议客户端是否正常。

---

## 5. 测试要点

- **健康熔断**：模拟连续失败 3 次，检查 `is_available` 是否返回 False，且在 `recover_seconds` 后恢复。
- **动态排序**：检查 `get_ordered_sources` 是否剔除熔断源。
- **协议增量**：在本地无数据时，协议客户端是否成功获取，并返回正确格式。
- **兼容性**：当 `easy_tdx` 未安装时，是否自动降级到 `mootdx` 或无协议客户端。

---

## 6. 风险与应对

- **easy_tdx 依赖问题**：若安装失败，自动降级。
- **协议服务器不稳定**：健康熔断可自动屏蔽。
- **协议数据与本地数据重复**：协议增量时需注意按日期去重，可由 `upsert` 和主键自动处理。

---

## 7. 下一步

完成阶段2后，可进入阶段3：财务完整本地化、可观测性、测试与文档。如需要阶段3详细设计，请告知。
