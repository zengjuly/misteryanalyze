# 阶段3详细设计：完整生产化方案

## 1. 目标

在阶段1（增量更新+复权因子+重采样升级）和阶段2（健康评分与动态熔断+协议客户端）的基础上，完成以下目标：

- **财务完整本地化**：从通达信官方财务包（`tdxfin.zip`）解析财务数据，统一存储并提供查询接口。
- **路径与环境变量优先**：所有路径解析统一支持环境变量覆盖，默认相对路径，提高跨环境可移植性。
- **可观测性**：完善日志与指标记录，生成源健康报告，便于运维监控。
- **测试与文档**：补充单元测试、集成测试，更新README和设计文档。
- **并发与同步优化**：配置化线程数，批量同步脚本支持断点续传与进度显示，提升全市场更新效率。

---

## 2. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/download_tdx_packages.py` | 新增/增强 | 下载三份官方数据包，支持参数、校验、解压到正确目录 |
| `data/tdx_local_client.py` | 扩展 | 增加财务数据读取方法，使用mootdx解析财务 |
| `data/financial_storage.py` | 新增 | 财务数据标准化与存储（独立表或JSON） |
| `utils/path_utils.py` | 新增 | 路径解析函数（环境变量优先） |
| `data/source_report.py` | 新增 | 生成源健康报告与统计 |
| `sync_all_market.py` | 修改 | 支持并发、断点、进度条 |
| `config/config.yaml` | 更新 | 增加财务相关配置、线程配置 |
| `tests/` | 新增多个测试 | 覆盖新增功能 |
| `README.md` / `DESIGN_DOCUMENT.md` | 更新 | 文档补充 |

---

## 3. 详细设计

### 3.1 财务完整本地化

#### 3.1.1 下载脚本 `scripts/download_tdx_packages.py`

增强现有下载脚本，支持：

- 命令行参数：`--force` 强制重新下载；`--only hsjday/tdxfin/tdxgp` 仅下载指定包。
- 下载后校验文件大小或MD5（可选）。
- 自动解压并整理目录结构：
  - `hsjday.zip` → `vipdoc/sh/lday/`、`vipdoc/sz/lday/`、`vipdoc/bj/lday/`
  - `tdxfin.zip` → `vipdoc/cw/`（财务数据，通常包含`gpcw*.dat`）
  - `tdxgp.zip` → `vipdoc/` 根目录（股票列表文件）

```python
# scripts/download_tdx_packages.py 伪代码
import os, sys, requests, zipfile, argparse
from utils.path_utils import resolve_path

URLS = {
    "hsjday": "https://data.tdx.com.cn/vipdoc/hsjday.zip",
    "tdxfin": "https://data.tdx.com.cn/vipdoc/tdxfin.zip",
    "tdxgp":  "https://data.tdx.com.cn/vipdoc/tdxgp.zip",
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--only', choices=list(URLS.keys()))
    args = parser.parse_args()

    vipdoc_dir = resolve_path('TDX_VIPDOC_DIR', 'data/tdx_vipdoc')
    os.makedirs(vipdoc_dir, exist_ok=True)

    for pkg, url in URLS.items():
        if args.only and args.only != pkg:
            continue
        dest_zip = os.path.join(vipdoc_dir, f'{pkg}.zip')
        if os.path.exists(dest_zip) and not args.force:
            print(f'{pkg}.zip 已存在，跳过')
            continue
        print(f'下载 {pkg}...')
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        with open(dest_zip, 'wb') as f:
            f.write(resp.content)
        # 解压
        with zipfile.ZipFile(dest_zip) as z:
            z.extractall(vipdoc_dir)
        print(f'{pkg} 下载解压完成')
```

#### 3.1.2 财务数据读取与标准化

在 `TdxLocalClient` 中扩展：

```python
# data/tdx_local_client.py 内新增方法
def get_financial_data(self, stock_code: str) -> pd.DataFrame:
    """
    读取本地财务数据，返回标准化字段：
    报告期、每股收益、每股净资产、净资产收益率、净利润、营业收入等
    """
    code = self.normalize_stock_code(stock_code)
    market = self._get_market(code)
    try:
        # 使用 mootdx.financial
        from mootdx.financial import Financial
        fin = Financial(tdxdir=self.vipdoc_dir)
        # 获取最新或全部财务指标
        df = fin.get_stock_financial(symbol=code, market=market)
        if df is None or df.empty:
            return pd.DataFrame()
        # 列名映射（根据实际字段调整）
        rename_map = {
            'date': '报告期',
            'eps': '每股收益',
            'bps': '每股净资产',
            'roe': '净资产收益率',
            'net_profit': '净利润',
            'revenue': '营业收入',
            # 更多字段...
        }
        df = df.rename(columns=rename_map)
        # 单位转换、过滤等
        return df
    except Exception as e:
        logger.error(f"读取财务数据失败 {code}: {e}")
        return pd.DataFrame()
```

**注意**：通达信财务数据格式复杂，不同版本字段可能不同。建议参考 mootdx 文档或现有开源实现进行字段映射，并存储到独立表 `stock_financial_data`（结构可设计为 `code, report_date, field, value` 或宽表）。为简化，本方案先以宽表返回，后续可按需存储。

#### 3.1.3 财务数据存储（可选）

新增 `data/financial_storage.py`，负责将财务数据写入数据库表 `stock_financial`，主键 `(code, report_date)`。如果现有系统不需要历史财务，可以只提供接口，由上层决定是否缓存。

### 3.2 路径与环境变量优先

新建 `utils/path_utils.py`：

```python
import os

def resolve_path(env_key: str, config_value: str = None, default: str = 'data/tdx_vipdoc') -> str:
    """环境变量优先，其次配置值，最后默认值"""
    if env_key in os.environ:
        return os.environ[env_key]
    if config_value:
        return config_value
    return default
```

在 `config.py` 或配置加载模块中，使用该函数解析所有路径：

```python
from utils.path_utils import resolve_path
vipdoc_dir = resolve_path('TDX_VIPDOC_DIR', config.get('data_source', {}).get('tdx', {}).get('vipdoc_dir'), 'data/tdx_vipdoc')
```

同理，数据库路径、日志路径等均可采用此模式，提高环境可移植性。

### 3.3 可观测性

#### 3.3.1 日志增强

在 `MarketDataClient` 中已经记录每次请求的源、耗时、结果。为了更好观测，增加：

- 请求总数、成功数、失败数、平均耗时。
- 每次 Fallback 切换时记录原因。
- 数据源健康状态变化日志。

#### 3.3.2 源健康报告

新增 `data/source_report.py`：

```python
import json, time
from data.source_health import SourceHealth

def generate_report(source_health: SourceHealth, output_dir='logs'):
    stats = source_health.get_source_stats()
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'sources': {}
    }
    for src, s in stats.items():
        report['sources'][src] = {
            'success_count': s['success_count'],
            'failure_count': s['failure_count'],
            'consecutive_failures': s['consecutive_failures'],
            'health_score': s['health_score'],
            'is_open': s['is_open'],
        }
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f'source_report_{time.strftime("%Y%m%d")}.json')
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return filename
```

可以集成到每日任务结束后自动调用。

### 3.4 测试与文档

#### 3.4.1 单元测试

新增以下测试文件：

- `tests/test_resampler.py`：测试重采样边界（不足min_bars、跨周期、交易日历过滤）。
- `tests/test_incremental.py`：测试增量更新幂等性、从本地文件读取尾部数据。
- `tests/test_trim_kline.py`：测试2000条限制和循环覆盖。
- `tests/test_fallback.py`：测试主源失败切换、健康熔断。
- `tests/test_path_utils.py`：测试环境变量覆盖。

#### 3.4.2 文档更新

- `README.md`：增加“首次部署 Checklist”、“环境变量说明”、“数据源配置示例”。
- `DESIGN_DOCUMENT.md`：补充健康评分算法、增量更新原理、重采样规则、财务数据说明。

### 3.5 并发与同步优化

#### 3.5.1 配置化线程

在 `config.yaml` 中增加：

```yaml
sync:
  threads:
    tdx_local: 8
    akshare: 4
    baostock: 1   # baostock 有全局锁，不宜多线程
  batch_size: 50
  checkpoint_file: "data/sync_checkpoint.json"
```

#### 3.5.2 修改 `sync_all_market.py`

- 使用 `concurrent.futures.ThreadPoolExecutor` 按数据源类型限制并发。
- 读取断点文件（JSON），记录已完成的股票代码，支持中断后继续。
- 使用 `tqdm` 显示进度条。
- 单只股票同步时调用 `MarketDataClient.fetch_daily`（内部已走健康源）。

示例骨架：

```python
import json, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from data.market_data_client import MarketDataClient
from data.db_manager import DBManager

def sync_stock(code, client):
    try:
        df = client.fetch_daily(code, start_date=None, end_date=None)
        # 周/月可通过 resampler 生成并写入，或按需
        return code, len(df)
    except Exception as e:
        return code, -1

def main():
    config = load_config()
    client = MarketDataClient(config)
    db = DBManager(config)
    stock_list = db.get_all_stock_codes()  # 从股票列表或数据库获取

    checkpoint_file = config['sync']['checkpoint_file']
    done_codes = set()
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file) as f:
            done_codes = set(json.load(f))

    pending_codes = [c for c in stock_list if c not in done_codes]
    threads = config['sync']['threads'].get('tdx_local', 8)  # 简化，统一使用一个线程池
    results = []
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(sync_stock, code, client): code for code in pending_codes}
        for future in tqdm(as_completed(futures), total=len(futures)):
            code, count = future.result()
            results.append(code)
            # 更新断点文件
            done_codes.add(code)
            with open(checkpoint_file, 'w') as f:
                json.dump(list(done_codes), f)
    print(f"同步完成，成功 {sum(1 for r in results if r != -1)} 只")
```

实际项目中，可能需要按数据源分组使用不同线程池，或限制全局并发。

---

## 4. 实施步骤

1. **更新依赖**：`pip install tqdm`，确认 `mootdx` 财务模块可用。
2. **实现路径工具**：创建 `utils/path_utils.py`，并在配置加载处应用。
3. **增强下载脚本**：按 3.1.1 完善，测试下载和解压。
4. **扩展 TdxLocalClient**：实现 `get_financial_data`，测试财务读取。
5. **新增 source_report.py**：实现报告生成，集成到主流程。
6. **修改同步脚本**：加入并发、断点、进度条。
7. **编写单元测试**：覆盖新增模块。
8. **更新文档**：补充使用说明和部署指南。
9. **全链路验证**：在测试环境模拟各种故障，验证健康熔断、增量更新、财务读取。

---

## 5. 验证清单

- [ ] 下载脚本能够成功下载三份包并解压到正确目录。
- [ ] `TdxLocalClient.get_financial_data` 对典型股票返回非空且字段正确。
- [ ] 环境变量 `TDX_VIPDOC_DIR` 可以覆盖默认路径。
- [ ] 健康报告 JSON 文件生成，包含各源状态。
- [ ] 批量同步支持断点续传（中断后重新运行，跳过已完成）。
- [ ] 单元测试通过率 100%。
- [ ] 全市场增量同步耗时显著降低（目标 <15 分钟）。

---

## 6. 预期效果

- 财务数据实现本地化，离线可用，数据完整。
- 部署灵活性大幅提升，一套代码适配不同环境。
- 系统运行状态透明，故障可快速定位。
- 批量更新速度提升，运维效率提高。
- 代码质量和可维护性增强，为后续迭代打下基础。

完成阶段3后，整个优化方案全部落地，系统达到生产级标准。
