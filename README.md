# Mystery趋势交易分析系统

## 项目概述

基于《Mistery趋势交易论》的智能股票分析系统，实现数据获取、技术指标计算、Mystery理论分析、Excel和HTML报告输出等功能。

## 系统特性

### 🎯 核心功能
- **数据获取**: 🥇同花顺扶摇(ths_official) → 🥈tdx-api容器 → 🥉tdx_local 三源退避链
  （akshare/baostock 保留代码静默兼容，docs/0821.md）
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
│   ├── source_report.py   # 源健康报告生成(JSON, 可观测性) ★
│   ├── financial_storage.py # 财务数据标准化存储门面(SQLite宽表) ★
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
│   ├── path_utils.py      # 路径解析(环境变量优先) ★
│   └── __init__.py       # 工具函数
├── tests/                 # 单元测试(unittest) ★
│   ├── test_path_utils.py / test_resampler.py / test_incremental.py
│   └── test_trim_kline.py / test_fallback.py
├── web/                   # Web 前端（Streamlit 多页面，docs/ui.md）★
│   ├── app.py             # 主入口（侧边栏导航）
│   ├── pages/             # 5 个页面（个股分析/板块监控/全市场扫描/真三振池/系统状态）
│   ├── components/        # K线图/评分卡片/股票表格组件
│   └── utils/session.py   # 会话状态 + 后端单例
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
- `--watchlist`: 每日分析使用自选股列表（替代 config 股票列表；从生产库
  watchlist 表读取，约66只。**非交互/cron 环境必须先
  `export MYSTERY_DB_PATH=/home/ai/ai_runner/stock/data/db/mystery_cache.db`**，
  否则 .bashrc 不加载、自选股读空）
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

# 更长历史（日线2000天≈8年）
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py --period daily --days 2000

# 测试模式：仅同步前500只（快速验证）
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py --limit 500 --threads 4

# 每日增量更新（闭市后）
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py --period daily --days 365

# 忽略断点强制全量重同步（--days/--period 变更时断点自动失效，一般无需 --force）
/home/ai/ai_runner/venv/bin/python data/sync_all_market.py --period daily --days 2000 --force
```

参数说明：
| 参数 | 说明 | 默认 |
|---|---|---|
| `--period` | 同步周期：daily/weekly/monthly | daily |
| `--days` | 回溯天数（日线1100≈3年，2000≈8年；周线1830≈5年，月线3650≈10年） | 按周期 |
| `--threads` | 线程数。⚠️ baostock 为全局单 socket 连接，多线程并发会导致 utf-8 解码错误/数据交错，**默认读 config sync.threads（baostock=1 串行最稳定）**，最多建议 2-4 | config |
| `--limit` | 仅同步前N只（测试用） | 全部 |
| `--index` | 是否包含指数 | 否（仅股票） |
| `--checkpoint` | 断点文件路径（JSON，中断后重新运行跳过已完成，支持续传） | config sync.checkpoint_file |
| `--no-progress` | 关闭 tqdm 进度条 | 显示进度条 |
| `--force` | 忽略断点强制全量重同步（一般无需：`--days`/`--period` 变更时断点自动失效） | 否 |

> 系统已内置网络容错：数据包解码错误自动重试（3次+退避）、连接损坏自动重新登录重建。若网络弱导致部分股票返回空，可重新运行同步命令补齐（断点续传会自动跳过已完成）。
>
> 💡 **断点续传参数感知**：断点文件（sync_checkpoint.json）记录 `days`/`periods` 元数据。
> 再次运行若参数与断点不一致（如 `--days 1100` → `--days 2000`），断点**自动失效并全量重同步**
> （避免长历史被旧断点跳过）；参数一致则续传跳过已完成。旧格式断点（无元数据）同样自动失效。
>
> 💡 **同步范围说明**：`sync_all_market.py` 负责**行情 K 线**同步（本地优先 .day + 增量路径，
> 全量 5208 只首次建缓存约 12 分钟）；**财务**（PE/PB/ROE/股息率）与**行业板块分类**为
> **按需自动拉取**——个股分析页打开时自动获取并缓存（FinancialStorage / DataFeeder），
> 无需单独同步命令。
>
> 💡 **重建数据库（清缓存）**：`scripts/rebuild_db.py` 一键清除本地所有缓存并重建空库——
> `--dry-run` 预览 / `--sync` 重建后全量重同步 / `--days 2000` 指定回溯天数 /
> `--yes` 无人值守（建议先 `sudo systemctl stop mystery-web` 再执行）。
>
> 💡 **性能说明**：同步优先走**通达信本地数据源**（.day 文件）+ 增量路径（缓存直读，毫秒级），
> 仅本地缺失时才回退 akshare/baostock 网络。全量 5208 只首次建缓存约 **12 分钟**；
> 每日增量同步（缓存已有）更快（分钟级）。可安装通达信数据包进一步加速：
> `python scripts/download_tdx_packages.py`。

#### 2. 全市场扫描分析

```bash
# 扫描本地缓存中的所有股票（毫秒级读取）
/home/ai/ai_runner/venv/bin/python data/run_market_scan.py

# 首次使用：先同步再扫描
/home/ai/ai_runner/venv/bin/python data/run_market_scan.py --sync

# 快速测试：仅扫描前100只
/home/ai/ai_runner/venv/bin/python data/run_market_scan.py --limit 100

# 忽略缓存强制重扫（同交易日行情未更新时默认直接复用上次结果）
/home/ai/ai_runner/venv/bin/python data/run_market_scan.py --limit 100 --no-cache

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
| `--no-cache` | 忽略扫描结果缓存（行情未更新时默认复用上次结果） | 否 |

扫描输出（output 目录 + 独立库 scan_results.db）：
- `市场扫描报告_时间戳.txt`：信号股票 Top（VAP-ATR 突破 / 筹码低位共振）+ 主升浪满足数
- `市场扫描明细_时间戳.csv`：全量明细（自适应N / POC / 自适应上下轨 / 信号等）
- `市场扫描明细_时间戳.xlsx`：Excel 多 sheet（汇总 / 全部明细 / 信号股票 / 真三振）
- `scan_results.db`：任务状态（scan_jobs 表）+ 每只股票结果明细（scan_results 表），
  独立于行情库；页3 扫描任务历史 / 页5 系统状态可查看
- 每次扫描完成后 Excel/CSV/TXT 自动 git 提交推送至 output 远端仓库

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
系统分析四个层面的趋势共振（docs/3z.md 四维共振评分，总分100）：
1. **个股趋势（30分）**: 基础过滤 + 均线多头（收盘价>MA20 或均线多头排列）
2. **大盘趋势（25分）**: 指数收盘>MA20且>MA60 为向上；含近120日位置评估（高位惩罚-15）
3. **行业趋势（25分）**: 优化版评分（MA20偏离+近10日涨幅+成交额放大），强势行业数量过滤
4. **资金确认（20分）**: 量比≥1.5 / 成交额放大 / 换手率≥3%

**真三振（三级）**: 评分≥85 且资金活跃 且 大盘/行业向上 且 个股OK（大资金跨层级共振）
二级共振 ≥70 / 一级共振 ≥45 / 无共振。报告展示"最强板块"与四维评分明细。

### 三大心法综合信号（docs/refact1.md）
严格量化《Mistery趋势交易论》核心心法，输出可操作信号：
1. **年线滤网**: 股价与 MA5/10/20/60 全部运行在 MA250 年线之上（一票否决）
2. **周线锚定**: 周线收盘 > 60 周均线，且 60 周均线斜率不向下
3. **破五反五**: 允许跌破 MA5，但 2 个交易日内收回且 MA20 斜率向上

**主升浪信号** = 年线滤网 ∧ 周线锚定 ∧ (股价>MA5 ∨ 破五反五)
**综合评分** = 四维共振评分×0.6 + 主升浪信号40×0.4（未过年线滤网直接观望）

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

## Web 前端界面（docs/ui.md）

Streamlit 多页面 Web 界面（端口 1888），完全复用现有分析引擎：

```bash
pip install streamlit plotly
streamlit run web/app.py --server.port 1888 --server.headless true
```

页面功能：
1. **📈 个股分析**：代码/名称模糊搜索 → 评分卡片 + 三大心法 + 操作建议 + 财务（PE/PB/ROE/股息率）+ Excel对齐明细（震荡区间/筹码/主升浪8项/周月K箱体）+ K线（MACD+周期切换+震荡区间）+ 分析缓存
2. **📊 板块监控**：板块强度（MA20偏离×0.4+近10日涨幅×0.3+成交额×0.3）Top15 条形图 + 成分股钻取（真三振龙头高亮）
3. **🔍 全市场扫描**：参数化扫描 + 股票池选择（全市场/自选池/自定义）+ 进度条 + 当日结果缓存 + 真三振高亮表格
4. **💎 真三振池**：最近扫描结果 + 模糊搜索添加自选股
5. **⚙️ 系统状态**：数据源健康 + SQLite 缓存信息 + 源健康报告生成

分析结果缓存（mystery_analysis_cache 表）：个股以 (代码, 最新K线日期) 为键、扫描以当日为键，行情未更新不重复分析。

全市场扫描结果独立存储（scan_results.db，与主行情库同目录）：任务状态 + 每只股票
明细入库；以最新交易日为缓存键，行情未更新时同参数扫描直接命中缓存不重复执行
（实测二次扫描耗时 0s）。后台扫描状态/历史任务/结果明细可在 Web 页3「全市场扫描」
与页5「系统状态」查看。

生产部署：`sudo cp scripts/mystery-web.service /etc/systemd/system/ && sudo systemctl enable --now mystery-web`（防火墙开放 1888 端口）。

## 版本信息

- **版本**: 1.22.0
- **作者**: Mystery Team
- **更新时间**: 2026-08-22
- **Python版本**: 3.12（venv: /home/ai/ai_runner/venv）

## 首次部署 Checklist

1. **环境准备**：`python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
   （另需 `pip install tqdm`；`easy_tdx` 可选，未安装自动降级 mootdx Quotes）
2. **配置**：编辑 `config/config.yaml`（股票列表、数据源、增量/健康/同步参数）
3. **下载通达信本地数据包**（离线主源，可选但推荐）：
   ```bash
   python scripts/download_tdx_packages.py            # 下载 hsjday/tdxfin/tdxgp
   python scripts/download_tdx_packages.py --fix-flat # 修复旧版扁平结构（历史遗留）
   ```
4. **全市场同步**（构建 SQLite 缓存，首次约需较长时间）：
   ```bash
   python data/sync_all_market.py --days 1100         # 断点续传+进度条
   ```
5. **冒烟测试**：`python run_analysis.py --mode single --stock sh600150`
6. **单元测试**：`python -m unittest discover -s tests`（32/32 通过）
7. **定时任务**：每日 15:30 运行每日分析（Hermes cron '股票每日分析'）；闭市后可增量同步+扫描
   ```bash
   python data/sync_all_market.py --period daily --days 365  # 每日增量（断点续传）
   python data/run_market_scan.py                            # 全市场扫描
   ```

## 环境变量说明

| 环境变量 | 说明 | 默认 |
|---|---|---|
| `TDX_VIPDOC_DIR` | 通达信本地数据目录（.day 文件） | /home/ai/ai_runner/stock/data/tdx_vipdoc |
| `MYSTERY_DB_PATH` | SQLite 缓存数据库路径 | data/mystery_cache.db |
| `SOURCE_REPORT_DIR` | 源健康报告输出目录 | logs/ |

> 路径解析统一规则（docs/step3.md）：**环境变量 > 配置值 > 默认值**，见 `utils/path_utils.py`。

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 项目主页: https://github.com/mystery-team/stock-analyzer
- 问题反馈: https://github.com/mystery-team/stock-analyzer/issues
- 邮箱: mystery-team@example.com

---

**免责声明**: 本系统仅供学习和研究使用，不构成投资建议。投资有风险，请谨慎决策。