# Mystery趋势交易分析系统

## 项目概述

基于《Mistery趋势交易论》的智能股票分析系统，实现数据获取、技术指标计算、Mystery理论分析、Excel和HTML报告输出等功能。

## 系统特性

### 🎯 核心功能
- **数据获取**: 基于baostock的股票数据获取
- **技术指标**: 均线系统、趋势指标、动能指标
- **Mystery理论**: 三振共振、主升浪分析、平台突破
- **形态识别**: 头肩顶/底、双重顶/底、三角形、楔形
- **智能分析**: 综合评分、投资建议、风险评估
- **报告输出**: Excel详细报告、HTML可视化报告
- **数据中枢**: SQLite本地缓存 + Cache-Aside数据引擎（毫秒级读取）
- **全市场扫描**: 全量A股多线程同步 + 自适应VAP-ATR信号捕获

### 📊 技术指标
- **均线系统**: MA5、MA10、MA20、MA60、MA250
- **趋势指标**: MACD、RSI、KDJ
- **动能指标**: ROC、威廉指标
- **成交量指标**: 量比、换手率分析

### 🎯 Mystery理论分析
- **三振共振**: 大盘趋势 + 行业趋势 + 个股趋势
- **主升浪**: 股价沿MA5上涨，不破MA5则标记为"主升持股期"
- **平台突破**: 放量突破箱体上沿，MACD零轴上金叉
- **空中加油**: 缩量横盘整理，筹码峰在低位不动

## 系统架构

```
stock_analyzer/
├── config/                 # 配置文件
│   └── config.yaml        # 主配置文件
├── data/                  # 数据获取模块
│   ├── baostock_client.py # baostock数据客户端
│   ├── akshare_client.py  # AKShare数据源客户端
│   ├── tdx_local_client.py # 通达信本地数据客户端(mootdx)
│   ├── tdx_incremental.py # 通达信增量更新器(.day尾部读取,零网络) ★
│   ├── tdx_gbbq.py        # 除权除息(gbbq)解析与复权因子计算 ★
│   ├── tdx_protocol_client.py # 通达信行情协议客户端(本地缺失时增量补充) ★
│   ├── source_health.py   # 源健康评分与动态熔断(故障源自动屏蔽) ★
│   ├── kline_resampler.py # 日K→周K/月K聚合器(交易日历感知+最少K线过滤) ★
│   ├── market_data_client.py # 统一数据入口(三级退避)
│   ├── data_processor.py  # 数据预处理
│   ├── db_manager.py      # SQLite本地缓存数据库（三表/联合主键/索引）
│   ├── data_engine.py     # Cache-Aside数据抽象层（缓存穿透回填）
│   ├── sync_all_market.py # 全市场多线程同步脚本
│   └── run_market_scan.py # 全量自适应扫描分析引擎
├── indicators/            # 技术指标模块
│   ├── ma_indicators.py   # 均线指标
│   ├── trend_indicators.py # 趋势指标
│   └── momentum_indicators.py # 动能指标
├── analysis/              # 核心分析模块
│   ├── mystery_logic.py   # Mystery理论逻辑
│   ├── resonance_analyzer.py # 三振共振分析
│   └── pattern_recognition.py # 形态识别
├── output/                # 输出模块
│   ├── excel_generator.py # Excel报告生成
│   └── html_generator.py  # HTML报告生成
├── utils/                 # 工具模块
│   ├── exception_handler.py # 异常处理
│   └── __init__.py       # 工具函数
├── main.py               # 主执行程序
├── test_system.py        # 系统测试
├── simple_demo.py        # 简化演示
└── run_analysis.py       # 快速启动脚本
```

## 快速开始

### 1. 环境准备
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖（推荐）
pip install -r requirements.txt

# 或手动安装
pip install baostock pandas numpy openpyxl pyyaml
```

### 2. 运行演示（无需外部依赖）
```bash
# 运行简化演示（不依赖 baostock/pandas，开箱即用）
python3 simple_test_v2.py

# 运行完整演示
python3 simple_demo.py
```

### 3. 配置系统
编辑 `config/config.yaml` 文件，配置要分析的股票代码和其他参数。

### 4. 运行分析
```bash
# 每日分析模式
python3 run_analysis.py --mode daily

# 单只股票分析模式
python3 run_analysis.py --mode single --stock sh600000

# 运行系统测试
python3 run_analysis.py --test
```

## 详细使用说明

### 配置文件说明

在 `config/config.yaml` 中可以配置：

- **股票列表**: 要分析的股票代码
- **大盘指数**: 市场趋势参考指数
- **技术指标**: 指标计算参数
- **Mystery理论**: 分析参数设置
- **输出配置**: 报告生成设置
- **风险控制**: 止损和仓位管理

### 主程序功能

#### main.py
系统主程序，提供完整的分析流程：
1. 数据获取
2. 数据预处理
3. 技术指标计算
4. Mystery理论分析
5. 形态识别
6. 结果汇总
7. 报告生成

#### run_analysis.py
快速启动脚本，提供简化的命令行接口：
- `--mode daily`: 每日分析模式
- `--mode single`: 单只股票分析模式
- `--stock`: 指定股票代码
- `--test`: 运行系统测试

### 数据中枢与全市场扫描

系统内置 SQLite 本地缓存（`data/mystery_cache.db`）+ Cache-Aside 数据引擎，
支持全量 A 股数据的本地化存储与毫秒级读取，解决频繁调用 baostock API 慢的问题。

#### 1. 全量数据同步

```bash
# 全量同步（默认日线，回溯1100天）
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py

# 指定周期（日/周/月线）
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py --period weekly --days 1830

# 测试模式：仅同步前500只（快速验证）
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py --limit 500 --threads 4

# 每日增量更新（闭市后）
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py --period daily --days 365
```

参数说明：
| 参数 | 说明 | 默认 |
|---|---|---|
| `--period` | 同步周期：daily/weekly/monthly | daily |
| `--days` | 回溯天数（日线1100≈3年，周线1830≈5年，月线3650≈10年） | 按周期 |
| `--threads` | 线程数。⚠️ baostock 为全局单 socket 连接，多线程并发会导致 utf-8 解码错误/数据交错，**默认 1（串行最稳定）**，最多建议 2-4 | 1 |
| `--limit` | 仅同步前N只（测试用） | 全部 |
| `--index` | 是否包含指数 | 否（仅股票） |

> 系统已内置网络容错：数据包解码错误自动重试（3次+退避）、连接损坏自动重新登录重建。若网络弱导致部分股票返回空，可重新运行同步命令补齐。

#### 2. 全市场扫描分析

```bash
# 扫描本地缓存中的所有股票（毫秒级读取）
/home/ai/ai_runner/venv/bin/python data/run_market_scan.py

# 首次使用：先同步再扫描
/home/ai/ai_runner/venv/bin/python data/run_market_scan.py --sync

# 快速测试：仅扫描前100只
/home/ai/ai_runner/venv/bin/python data/run_market_scan.py --limit 100

# 周线周期扫描 + 报告Top 50
/home/ai/ai_runner/venv/bin/python data/run_market_scan.py --period weekly --top 50
```

参数说明：
| 参数 | 说明 | 默认 |
|---|---|---|
| `--limit` | 扫描股票数量限制 | 全部 |
| `--period` | K线周期：daily/weekly/monthly | daily |
| `--sync` | 先同步数据再扫描 | 否 |
| `--top` | 报告Top N | 20 |

扫描输出（output 目录）：
- `市场扫描报告_时间戳.txt`：信号股票 Top（VAP-ATR 突破 / 筹码低位共振）+ 主升浪满足数
- `市场扫描明细_时间戳.csv`：全量明细（自适应N / POC / 自适应上下轨 / 信号等）

#### 3. 核心信号

扫描引擎捕获两类信号：
- **VAP-ATR 突破**: 收盘价 > 自适应上轨 且 阳线 且 重心>0.5（实体突破）
- **筹码低位共振**: 近20日平均换手率 < 2%（筹码高度集中 + 低位）

#### 4. 实战化运行闭环

```bash
# ① 数据初始化（首次）
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py --period daily --days 1100

# ② 每日闭市后：增量同步 + 全市场扫描
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py --period daily --days 365
/home/ai/ai_runner/venv/bin/python data/run_market_scan.py

# ③ 成果查看：output/ 目录报告
```

### 多源数据退避（通达信本地 + AKShare + Baostock）

系统采用**三级数据源退避链**：通达信本地数据（主源，离线毫秒级）→ AKShare（网络备用）→ Baostock（最终兜底），
任一源失败自动切换下一级，不中断分析流程。周K/月K 统一由日K重采样生成，保证多周期对齐。

#### 1. 数据源配置（config/config.yaml）

```yaml
data_source:
  primary: "tdx_local"              # 主源：tdx_local(通达信本地) / akshare / baostock
  fallback: ["akshare", "baostock"] # 备用源列表（依次退避）
  prefer_resample: true             # true=强制日K重采样周/月
  adjust: "qfq"                     # 复权：qfq前复权 / hfq后复权 / none不复权
  retry_times: 3                    # 每个源最大重试次数
  retry_delay: 2                    # 初始退避延迟（秒），指数递增
  tdx:
    vipdoc_dir: "/home/ai/ai_runner/stock/data/tdx_vipdoc"  # 本地数据目录(仓库外)
    enable: true
    auto_download: false
    gbbq_file: "/home/ai/ai_runner/stock/data/tdx_vipdoc/cw/gbbq"  # 除权文件(可选)
    server_host: "119.147.212.81"  # 通达信行情服务器（协议增量补充）
    server_port: 7709
  health:                          # 源健康评分与动态熔断（step2.md）
    enable: true                   # 故障源自动屏蔽、恢复后放回
    window_size: 10                # 滑动窗口大小
    fail_threshold: 3              # 连续失败熔断阈值
    recover_seconds: 300           # 熔断恢复时间（秒）
    sort_by_health: false          # true=按健康分动态排序源
  incremental:                      # 增量更新（.day尾部读取，毫秒级零网络）
    enable: true                    # fetch_daily 优先本地增量
    max_bars_per_request: 800       # 单次最大增量条数
    gap_threshold: 0.11             # 除权断裂检测阈值（超阈值回退在线源）
  resample:                         # 重采样升级（step1.md）
    min_bars_weekly: 3              # 周K最少日K根数（最新周期豁免）
    min_bars_monthly: 10            # 月K最少日K根数（最新周期豁免）
    use_trading_calendar: true      # 仅保留交易日（日历来自缓存日K并集）
    keep_latest_period: true        # 最新周期豁免（进行中的周/月K保留）
  kline_limit:                      # K线保留条数（循环覆盖控制存储）
    daily: 2000
    weekly: 500
    monthly: 300
    enable_cleanup: true
```

#### 2. 通达信本地数据准备

```bash
# ① 下载官方数据包（hsjday日线/tdxfin财务/tdxgp股票列表），解压至 tdx_vipdoc
/home/ai/ai_runner/venv/bin/python scripts/download_tdx_packages.py

# 仅下载日线数据包
/home/ai/ai_runner/venv/bin/python scripts/download_tdx_packages.py --pkg hsjday

# 修复历史遗留扁平结构（旧版解压bug产生的反斜杠文件名→标准目录结构，幂等）
/home/ai/ai_runner/venv/bin/python scripts/download_tdx_packages.py --fix-flat

# 自定义目录（环境变量覆盖，默认 /home/ai/ai_runner/stock/data/tdx_vipdoc）
TDX_VIPDOC_DIR=/path/to/tdx_vipdoc /home/ai/ai_runner/venv/bin/python scripts/download_tdx_packages.py
```

> ⚠️ 历史 bug 说明：旧版解压脚本 `extractall` 会把通达信 zip 内的反斜杠路径（`sh\lday\sh600150.day`）
> 直接当文件名解压成扁平文件，导致 mootdx 目录读取失效。已修复解压逻辑（`_safe_extract`），
> 遗留扁平文件可用 `--fix-flat` 一键修复（TdxIncremental 增量读取同时兼容扁平结构，修复前也能工作）。

数据目录结构（Git 仓库外，.gitignore 已忽略 *.day/*.zip）：
```
tdx_vipdoc/
├── sh/lday/sh600000.day      # 上海日线
├── sz/lday/sz000001.day      # 深圳日线
├── bj/lday/                  # 北交所（若存在）
└── tdxgp.cfg                 # 股票列表
```

#### 3. 数据源切换与验证

```bash
# 验证当前数据源配置生效（打印源顺序）
/home/ai/ai_runner/venv/bin/python -c "
import sys; sys.path.insert(0, '.')
import yaml
from data.market_data_client import MarketDataClient
config = yaml.safe_load(open('config/config.yaml', encoding='utf-8'))
mdc = MarketDataClient(config)
print('源顺序:', mdc.source_order)   # ['tdx_local', 'akshare', 'baostock']
print('通达信就绪:', mdc.tdx_client.login_success)
"

# 临时切换主源（如网络环境差时用 baostock）
# config.yaml: primary: "baostock", fallback: ["akshare"]
```

> 提示：通达信本地源仅提供日K（周/月K由日K重采样），财务数据由 AKShare/Baostock 兜底获取。
> 本地数据包需定期重新下载更新（建议每日定时任务）。

#### 4. 增量更新（docs/step1.md 阶段1优化）

每日分析优先走**本地增量**：`fetch_daily` 查缓存最新日期 → 读 `.day` 文件尾部增量 → 缓存+增量合并。
- 缓存已最新（无增量）→ **直接返回缓存**，毫秒级零网络（实测 600150 从 18.8s → 0.11s）
- 有增量 → 复权一致性处理（gbbq 因子可用则应用复权；否则连续性检查
  `|增量首收/缓存末收-1| > 11%` 或增量内部跳变超阈值 → 疑似除权 → 回退在线源保证复权一致）
- 无缓存锚点 / 异常 → 自动回退原三级退避链（行为不变）
- 重采样升级：周/月K按交易日历过滤 + 最少K线数过滤（周≥3、月≥10，最新周期豁免保留）

#### 5. 源健康评分与动态熔断（docs/step2.md 阶段2优化）

`SourceHealth` 模块实时评估各数据源健康状态，自动屏蔽故障源、恢复后自动放回：
- **健康分**：滑动窗口成功率×100（空数据记成功，停牌股不误熔断）
- **熔断**：连续失败 ≥ fail_threshold(3) → 熔断该源；超过 recover_seconds(300) 自动恢复
- **动态排序**：默认保持源优先级仅剔除熔断源；`sort_by_health: true` 时按健康分降序
- **协议增量**：`TdxProtocolClient`（easy_tdx → mootdx Quotes 自动降级）在本地 .day 缺失时
  从行情服务器（119.147.212.81:7709）补充；服务器不可达时退避链兜底

> 依赖说明：`easy_tdx` 为可选依赖（requirements.txt 注释），未安装自动降级 mootdx Quotes。
> 本机环境 easy_tdx 安装失败（pip sha256 校验异常）且行情服务器不可达（网络限制），
> 协议补充为空由 akshare/baostock 兜底——健康熔断会记录这些故障源的状态。
>
> 集成修复：① 重采样交易日历可能落后于增量数据（缓存 vs .day），已修复为保留
> "日历 ∪ 日历之后"（最新交易日不被误删）；② .day 增量无换手率字段 → 合并后
> 前向填充近似（用缓存最近值），保证最新交易日换手率/量比可计算。

### 输出文件说明

#### Excel报告
包含多个工作表：
- **汇总报告**: 所有股票的总体分析结果
- **个股详细**: 每只股票的详细分析
- **技术指标**: 关键技术指标数据
- **形态识别**: 形态识别结果
- **历史数据**: 最近30天的历史数据

#### HTML报告
可视化报告，包含：
- **总体统计**: 市场概况和统计
- **个股分析**: 每只股票的详细分析卡片
- **投资建议**: 基于分析结果的建议
- **风险提示**: 相关风险提示

#### 文本报告
简洁的文本格式报告，包含：
- 分析结果摘要
- 详细的个股分析
- 投资建议
- 风险提示

## 核心算法说明

### 三振共振分析
系统分析三个层面的趋势共振：
1. **大盘趋势**: 市场整体走势
2. **行业趋势**: 所属行业表现
3. **个股趋势**: 个股技术走势

当三个层面都呈现上升趋势时，形成"三振共振"。

### 主升浪识别
识别主升浪的关键特征：
- 股价沿MA5上涨
- 不破MA5，保持上升趋势
- 成交量配合放大
- 筹码相对集中

### 平台突破分析
识别平台突破的条件：
- 股价在箱体内整理
- 成交量高于前均量1.5倍
- MACD在零轴上金叉
- 突破箱体上沿

### 形态识别
支持多种技术形态识别：
- **头肩顶/底**: 趋势反转形态
- **双重顶/底**: 中继整理形态
- **三角形**: 收敛整理形态
- **楔形**: 倾斜整理形态

## 异常处理系统

系统包含完整的异常处理机制：
- **自定义异常类**: 针对不同类型的错误
- **异常处理器**: 统一的异常处理逻辑
- **错误日志**: 详细的错误记录
- **重试机制**: 自动重试失败的操作
- **性能监控**: 记录系统性能数据

## 测试系统

系统包含完整的测试套件：
- **配置加载测试**: 验证配置文件正确性
- **异常处理测试**: 验证异常处理机制
- **数据获取测试**: 验证数据获取功能
- **指标计算测试**: 验证技术指标计算
- **分析逻辑测试**: 验证分析算法
- **输出生成测试**: 验证报告生成功能
- **性能测试**: 验证系统性能

## 扩展开发

### 添加新的技术指标
1. 在 `indicators/` 目录下创建新的指标文件
2. 实现指标计算方法
3. 在主程序中集成新指标

### 添加新的分析算法
1. 在 `analysis/` 目录下创建新的分析文件
2. 实现分析逻辑
3. 在Mystery逻辑中集成新算法

### 添加新的输出格式
1. 在 `output/` 目录下创建新的输出模块
2. 实现输出生成逻辑
3. 在主程序中集成新输出格式

## 性能优化

系统包含多种性能优化措施：
- **批量处理**: 批量获取和处理数据
- **缓存机制**: 缓存计算结果
- **并行计算**: 多线程处理
- **内存管理**: 合理的内存使用

## 安全考虑

- **数据安全**: 安全的数据获取和存储
- **错误处理**: 完善的错误处理机制
- **日志记录**: 详细的操作日志
- **权限控制**: 合理的文件权限设置

## 故障排除

### 常见问题

1. **依赖包缺失**
   ```bash
   pip install baostock pandas numpy openpyxl pyyaml
   ```

2. **数据获取失败**
   - 检查网络连接
   - 验证baostock账号状态
   - 检查股票代码格式

3. **报告生成失败**
   - 检查输出目录权限
   - 确保有足够的磁盘空间
   - 验证数据完整性

### 日志分析

系统日志位于 `logs/` 目录：
- `stock_analysis_YYYYMMDD.log`: 系统运行日志
- `errors.log`: 错误日志
- `performance.log`: 性能日志

## 版本信息

- **版本**: 1.8.0
- **作者**: Mystery Team
- **更新时间**: 2026-08-14
- **Python版本**: 3.12（venv: /home/ai/ai_runner/venv）

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 项目主页: https://github.com/mystery-team/stock-analyzer
- 问题反馈: https://github.com/mystery-team/stock-analyzer/issues
- 邮箱: mystery-team@example.com

---

**免责声明**: 本系统仅供学习和研究使用，不构成投资建议。投资有风险，请谨慎决策。