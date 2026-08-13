# 基于 mootdx 的通达信本地数据源集成详解

根据您的方案，我们使用 `mootdx` 库来解析通达信本地数据包（`hsjday.zip` / `tdxfin.zip`），并将其封装为 `TdxLocalClient`，作为 **主数据源（tdx_local）** 集成到 `MarketDataClient` 的自动退避链中。以下给出完整实现代码与集成步骤，可直接落地。

---

## 1. mootdx 简介

`mootdx` 是一个纯 Python 实现的通达信数据读取库，支持：
- 读取本地通达信数据文件（`.day`、`.fin`、`.gpcw` 等）
- 解析日线、分钟线、财务数据
- 无需安装通达信客户端，只需下载官方数据包并解压

安装：
```bash
pip install mootdx
```

官方文档：https://mootdx.readthedocs.io/

---

## 2. 数据包准备

使用脚本下载并解压至指定目录，目录结构示例：

```
data/tdx_vipdoc/
├── sh/
│   └── lday/          # 上海日线 .day 文件
│       sh600000.day
│       sh600004.day
│       ...
├── sz/
│   └── lday/          # 深圳日线
├── bj/
│   └── lday/          # 北交所（若存在）
├── cw/                # 财务数据（gpcw*.dat）
└── tdxgp.cfg          # 股票列表
```

下载脚本 `scripts/download_tdx_packages.py`：

```python
import os
import requests
import zipfile
import io

BASE_URL = "https://data.tdx.com.cn/vipdoc/"
PACKAGES = {
    "hsjday": "hsjday.zip",
    "tdxfin": "tdxfin.zip",
    "tdxgp": "tdxgp.zip",
}
DEST_DIR = "data/tdx_vipdoc"

def download_and_extract(pkg_name):
    url = BASE_URL + PACKAGES[pkg_name]
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        z.extractall(DEST_DIR)
    print(f"{pkg_name} 下载解压完成")

if __name__ == "__main__":
    os.makedirs(DEST_DIR, exist_ok=True)
    for pkg in PACKAGES:
        download_and_extract(pkg)
```

---

## 3. `data/tdx_local_client.py` 完整实现

```python
import os
import pandas as pd
import logging
from mootdx.reader import Reader

logger = logging.getLogger(__name__)

class TdxLocalClient:
    """
    通达信本地数据客户端，使用 mootdx 读取官方数据包。
    支持日K线（.day）和财务数据（.fin / gpcw）。
    """
    def __init__(self, vipdoc_dir: str):
        self.vipdoc_dir = vipdoc_dir
        # mootdx Reader 工厂，自动识别市场结构
        self.reader = Reader.factory(market='std', tdxdir=vipdoc_dir)

    def normalize_stock_code(self, code: str) -> str:
        """统一转为6位数字，去除市场前缀"""
        code = code.lower().replace("sh.", "").replace("sz.", "").replace("bj.", "")
        return code.zfill(6)

    def _get_market(self, code: str) -> str:
        """根据代码判断市场：sh/sz/bj"""
        if code.startswith(("6", "9", "5")):  # 沪市A股/科创板/ETF等
            return "sh"
        elif code.startswith(("0", "2", "3")):  # 深市A股/创业板
            return "sz"
        elif code.startswith(("4", "8")):  # 北交所
            return "bj"
        else:
            return "sh"  # 默认

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None,
                       adjust="qfq") -> pd.DataFrame:
        """
        读取本地日K线数据。
        返回标准中文列名 DataFrame，与 AKShare/Baostock 一致。
        """
        code = self.normalize_stock_code(stock_code)
        market = self._get_market(code)

        try:
            # mootdx 读取日线，返回 DataFrame
            df = self.reader.daily(symbol=code, market=market)
        except Exception as e:
            logger.error(f"mootdx 读取 {code} 日线失败: {e}")
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        # mootdx 返回的列名通常是：date, open, high, low, close, volume, amount
        df = df.rename(columns={
            'date': '日期',
            'open': '开盘价',
            'high': '最高价',
            'low': '最低价',
            'close': '收盘价',
            'volume': '成交量',
            'amount': '成交额',
        })
        df['代码'] = code
        # 日期格式统一
        df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
        # 价格单位：mootdx 默认已还原为元，成交量单位为手
        # 确保数值类型
        numeric_cols = ['开盘价', '最高价', '最低价', '收盘价', '成交量', '成交额']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        # 过滤无效行
        df = df.dropna(subset=['开盘价', '收盘价'])
        # 按日期过滤
        if start_date:
            df = df[df['日期'] >= start_date]
        if end_date:
            df = df[df['日期'] <= end_date]
        # 按日期排序
        df = df.sort_values('日期')
        # 添加涨跌幅（如果缺失）
        if '涨跌幅' not in df.columns:
            df['涨跌幅'] = df['收盘价'].pct_change() * 100
        # 换手率缺失，填充 None 或 0
        if '换手率' not in df.columns:
            df['换手率'] = None
        # 统一列顺序
        return df[['日期', '代码', '开盘价', '最高价', '最低价', '收盘价',
                   '成交量', '成交额', '换手率', '涨跌幅']]

    def get_financial_data(self, stock_code: str) -> pd.DataFrame:
        """
        读取本地财务数据（.fin 文件）。
        返回标准字段：报告期、每股收益、每股净资产、净资产收益率、净利润等。
        """
        code = self.normalize_stock_code(stock_code)
        market = self._get_market(code)
        try:
            # mootdx 财务读取，需指定解析器
            from mootdx.financial import Financial
            fin = Financial(tdxdir=self.vipdoc_dir)
            df = fin.get_stock_financial(symbol=code, market=market)
        except Exception as e:
            logger.error(f"mootdx 读取 {code} 财务失败: {e}")
            return pd.DataFrame()
        return df

    def login(self):
        pass  # 本地数据无需登录

    def logout(self):
        pass
```

**说明**：
- `mootdx.Reader.daily()` 可直接读取 `.day` 文件，返回标准列。
- 市场判断函数根据代码前缀，确保正确读取。
- 财务数据解析较复杂，`mootdx.financial` 提供了接口，但字段可能需根据版本调整，建议优先使用 AKShare 财务接口，本地财务仅作补充。

---

## 4. 配置更新（`config/config.yaml`）

```yaml
data_source:
  primary: "tdx_local"            # 主源改为本地通达信
  fallback: ["akshare", "baostock"]  # 备用源列表
  prefer_resample: true           # 周/月K统一由日K重采样
  adjust: "qfq"
  rate_limit_akshare: 0.3
  retry_times: 3
  retry_delay: 2

  tdx:
    vipdoc_dir: "data/tdx_vipdoc" # 本地数据目录
    enable: true
    auto_download: false          # 是否自动触发下载（建议手动/定时）

  kline_limit:
    daily: 2000
    weekly: 500
    monthly: 300
    enable_cleanup: true
    cleanup_after_upsert: true
```

---

## 5. 集成到 `MarketDataClient`

修改 `data/market_data_client.py`，将 `TdxLocalClient` 加入数据源映射：

```python
from data.tdx_local_client import TdxLocalClient

class MarketDataClient:
    def __init__(self, config):
        # ...
        tdx_cfg = config.get("data_source", {}).get("tdx", {})
        self.tdx_client = TdxLocalClient(tdx_cfg.get("vipdoc_dir"))
        # 按配置构建源顺序
        primary = config.get("data_source", {}).get("primary", "akshare")
        fallback_list = config.get("data_source", {}).get("fallback", [])
        self.source_order = [primary] + fallback_list
        # ...

    def _fetch_from_source(self, src, code, period, start_date, end_date):
        if src == "tdx_local":
            # 仅支持日线，周/月由重采样完成
            if period == "daily":
                return self.tdx_client.get_daily_data(code, start_date, end_date)
            else:
                return pd.DataFrame()  # 让上层走重采样
        # 其他源...
```

注意：`TdxLocalClient` 应支持多市场文件路径，mootdx 已封装，无需自行解析。

---

## 6. 数据库 2000 条循环覆盖实现

在 `data/db_manager.py` 中增加 `trim_kline` 方法：

```python
def trim_kline(self, code, period='daily', max_rows=2000):
    """
    删除旧数据，仅保留最新 max_rows 条。
    """
    with self.get_connection() as conn:
        # SQLite 语法示例，MySQL 需调整
        conn.execute("""
            DELETE FROM stock_kline_data
            WHERE code = ? AND period = ?
              AND date NOT IN (
                  SELECT date FROM stock_kline_data
                  WHERE code = ? AND period = ?
                  ORDER BY date DESC
                  LIMIT ?
              )
        """, (code, period, code, period, max_rows))
        deleted = conn.total_changes
        return deleted
```

在 `upsert_kline` 方法末尾调用：

```python
def upsert_kline(self, df, code, period, max_rows=None):
    # 原有 INSERT OR REPLACE 逻辑...
    # 然后限制条数
    if max_rows and period == 'daily':
        self.trim_kline(code, period, max_rows)
```

配置中的 `kline_limit.daily=2000` 将传递到此。

---

## 7. 集成测试与验证

1. **本地数据读取测试**  
   ```python
   from data.tdx_local_client import TdxLocalClient
   client = TdxLocalClient("data/tdx_vipdoc")
   df = client.get_daily_data("600000", "2024-01-01", "2024-12-31")
   print(df.head())
   ```

2. **多源退避测试**  
   临时将主源设为 `akshare`，模拟失败，观察是否切换到 `tdx_local` 或 `baostock`。

3. **周/月重采样测试**  
   对比原生周K与重采样周K差异，确认对齐。

4. **数据库清理测试**  
   插入超过 2000 条日K，调用 `trim_kline`，确认旧记录被删除。

---

## 8. 注意事项

- **市场判断**：mootdx 需要明确市场，代码前缀判断需覆盖北交所、科创板等。
- **财务数据字段**：mootdx 财务解析可能因版本不同字段名有差异，建议结合 AKShare 财务接口使用。
- **数据更新**：本地数据包需定期重新下载，可设置每日定时任务。
- **线程安全**：mootdx 读取本地文件一般无并发问题，但多线程时注意文件句柄管理。
- **性能**：本地读取速度极快，适合作为首选源；AKShare 放在后备可避免网络延迟。

---

## 9. 总结

通过引入 `mootdx` 和通达信官方数据包，系统实现了：
- **离线高可用**：主源为本地数据，不受网络波动影响。
- **多级退避**：本地 → AKShare → Baostock，确保数据获取成功率。
- **统一周期对齐**：周/月K由日K重采样生成。
- **数据库精简**：日K保留 2000 条循环覆盖，控制存储成本。

该方案已完整覆盖需求，可直接编码落地。如需特定文件的完整可运行代码（含异常处理和日志），请告知。



收到，已确认本地通达信数据目录 `tdx_vipdoc` 需要可定制，且默认位置在 Git 仓库外：

```
/home/ai/ai_runner/stock/data/tdx_vipdoc
```

针对该要求，对方案做出以下调整：

---

## 1. 配置文件默认值更新

在 `config/config.yaml` 中，将 `tdx.vipdoc_dir` 的默认值改为绝对路径：

```yaml
data_source:
  tdx:
    vipdoc_dir: "/home/ai/ai_runner/stock/data/tdx_vipdoc"   # 默认绝对路径，可被环境变量覆盖
    enable: true
    auto_download: false
```

同时支持环境变量覆盖，在代码中加载配置时优先读取环境变量：

```python
import os
vipdoc_dir = os.getenv("TDX_VIPDOC_DIR", config["data_source"]["tdx"].get("vipdoc_dir", "/home/ai/ai_runner/stock/data/tdx_vipdoc"))
```

---

## 2. 目录创建与权限

在 `TdxLocalClient` 初始化时，若目录不存在且 `enable=True`，可自动创建（但通常由下载脚本提前创建）：

```python
import os
os.makedirs(vipdoc_dir, exist_ok=True)
```

---

## 3. Git 忽略规则

由于数据目录在仓库外，本身不会被纳入版本控制，但若开发者将路径改为相对路径（如 `data/tdx_vipdoc`），建议在 `.gitignore` 中添加：

```gitignore
data/tdx_vipdoc/
*.zip
*.day
*.fin
```

避免大体积数据文件误提交。

---

## 4. 下载脚本调整

`scripts/download_tdx_packages.py` 中的 `DEST_DIR` 改为从配置或环境变量读取：

```python
import os
DEST_DIR = os.getenv("TDX_VIPDOC_DIR", "/home/ai/ai_runner/stock/data/tdx_vipdoc")
```

---

## 5. 系统集成说明

- **默认路径**：`/home/ai/ai_runner/stock/data/tdx_vipdoc`
- **生产环境**：建议由运维在服务器上创建该目录并赋予运行用户读写权限，确保脚本可正常下载解压。
- **开发环境**：可通过环境变量 `TDX_VIPDOC_DIR` 指到本地任意路径，避免硬编码。

---

以上调整已包含在完整方案中，其他模块无需改动，`TdxLocalClient` 会自动从配置或环境变量获取正确的目录路径。如有其他定制需求，可继续提出。




