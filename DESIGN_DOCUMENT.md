# Mystery趋势交易分析系统 - 系统设计文档

## 文档信息

- **项目名称**: Mystery趋势交易分析系统
- **版本**: 1.14.0
- **创建日期**: 2026-08-09
- **更新日期**: 2026-08-15
- **文档类型**: 系统设计文档
- **目标读者**: 后续开发人员、维护人员、项目管理者

## 1. 系统概述

### 1.1 项目背景
基于《Mystery趋势交易论》的智能股票分析系统，旨在为投资者提供专业的股票技术分析和投资建议。

### 1.2 系统目标
- 实现基于 Mystery 理论的股票分析算法
- 提供多种技术指标计算功能
- 支持多种输出格式（Excel、HTML、文本）
- 具备良好的扩展性和维护性

### 1.3 核心特性
- **数据获取**: 基于 baostock 的股票数据获取（日线/周线/月线/指数/行业/财务/分红）
- **技术指标**: 均线、趋势、动能指标计算（MA/MACD/RSI/量比/OBV 等）
- **Mystery理论**: 三振共振（个股+行业+大盘）、主升浪识别、形态识别
- **自适应平台**: VAP-ATR 平台中枢（POC 筹码控制点 + 波动率自适应通道，A股涨跌停修正）
- **智能分析**: 综合评分系统、投资建议、主升浪8项指标对比表
- **多周期分析**: 日线+周线+月线共振判断
- **基本面数据**: ROE/EPS/PE/PB/股息率 + 所属板块与板块评级
- **多格式输出**: Excel、HTML、文本报告（文件名规则：单股含股票名称，每日加"每日"前缀）
- **自动同步**: 报告生成后自动 git 提交并推送远端（输出目录为独立 git 仓库）
- **定时任务**: 支持 cron 每日自动分析（周一至五 15:30）

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面层                           │
├─────────────────────────────────────────────────────────────┤
│  命令行界面 (run_analysis.py)  │  Web界面 (未来扩展)        │
└─────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────┐
│                        业务逻辑层                           │
├─────────────────────────────────────────────────────────────┤
│  主程序 (main.py)  │  汇总分析器 (summary_analyzer.py)  │
│  快速启动 (run_analysis.py)  │  配置管理 (config/)        │
└─────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────┐
│                        核心分析层                           │
├─────────────────────────────────────────────────────────────┤
│  Mystery理论 (analysis/mystery_logic.py)  │  三振共振 (analysis/resonance_analyzer.py)  │
│  形态识别 (analysis/pattern_recognition.py)  │  技术指标 (indicators/)  │
└─────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────┐
│                        数据处理层                           │
├─────────────────────────────────────────────────────────────┤
│  数据获取 (data/baostock_client.py)  │  数据处理 (data/data_processor.py)  │
│  数据存储 (未来扩展)  │  数据缓存 (未来扩展)              │
└─────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────┐
│                        输出展示层                           │
├─────────────────────────────────────────────────────────────┤
│  Excel报告 (output/excel_generator.py)  │  HTML报告 (output/html_generator.py)  │
│  文本报告 (output/text_report.py)  │  可视化图表 (未来扩展)    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分

#### 2.2.1 数据模块 (`data/`)
**职责**: 负责股票数据的获取和预处理
- `baostock_client.py`: baostock 数据获取客户端（含全局锁 BAOSTOCK_LOCK）
- `akshare_client.py`: AKShare 数据源客户端（多源退避备用源）★
- `kline_resampler.py`: 日K→周K/月K 聚合器 ★
- `tdx_local_client.py`: 通达信本地数据客户端（mootdx，主源 tdx_local）★
- `market_data_client.py`: 统一数据入口（主备退避 + 重采样选择）★
- `data_processor.py`: 数据预处理和清洗
- `db_manager.py`: SQLite 本地缓存数据库（三表/联合主键/索引/safe_upsert）★
- `data_engine.py`: Cache-Aside 数据抽象层（MysteryDataEngine，缓存穿透回填）★
- `sync_all_market.py`: 全市场多线程同步脚本（get_all_a_shares）★
- `run_market_scan.py`: 全量自适应扫描分析引擎（VAP-ATR信号捕获）★
- `__init__.py`: 模块初始化

**核心接口**（真实实现）:
```python
class BaostockClient:
    def login() -> bool                      # baostock 登录
    def logout() -> None                     # 登出
    def get_stock_name(stock_code: str) -> str   # 股票名称（query_stock_basic）
    def get_daily_data(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame   # 日线
    def get_weekly_data(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame  # 周线
    def get_monthly_data(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame # 月线
    def get_index_data(index_code: str, start_date: str, end_date: str) -> pd.DataFrame   # 指数
    def get_industry_data() -> pd.DataFrame  # 行业分类（code/code_name/industry）
    def get_financial_data(stock_code: str, current_price: float) -> dict  # ROE/EPS/PE/PB/股息率
    def normalize_stock_code(code: str) -> str   # sh600150 -> sh.600150（9位标准格式）
    @staticmethod
    def normalize_stock_code(stock_code: str) -> str

class DataProcessor:
    def __init__(self, baostock_client: BaostockClient)
    def get_all_stocks_data(stock_codes: list) -> dict   # {code: {daily/weekly/monthly}}
    def get_market_index_data() -> dict                  # 大盘指数数据
    def process_stock_data(stock_code: str) -> dict      # 单股 {daily, weekly, monthly}
```
> 注: 周线/月线仅支持基础字段（date,code,open,high,low,close,volume,amount,turn,pctChg），
> 不支持 tradestatus/isST 字段。mock 降级: baostock 不可用时自动使用 mock_baostock_client.py。

#### 2.2.2 技术指标模块 (`indicators/`)
**职责**: 计算各种技术指标
- `ma_indicators.py`: 均线指标计算
- `trend_indicators.py`: 趋势指标计算
- `momentum_indicators.py`: 动能指标计算
- `__init__.py`: 模块初始化

**核心接口**:
```python
class MAIndicators:
    def ma(data: pd.Series, period: int) -> pd.Series
    def ema(data: pd.Series, period: int) -> pd.Series
    def sma(data: pd.Series, period: int) -> pd.Series

class TrendIndicators:
    def macd(data: pd.Series, fast: int, slow: int, signal: int) -> dict
    def adx(data: pd.DataFrame, period: int) -> pd.Series
    def sar(data: pd.DataFrame, acceleration: float, maximum: float) -> pd.Series

class MomentumIndicators:
    def rsi(data: pd.Series, period: int) -> pd.Series
    def kdj(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> dict
    def roc(data: pd.Series, period: int) -> pd.Series
```

#### 2.2.3 核心分析模块 (`analysis/`)
**职责**: 实现 Mystery 理论分析和形态识别
- `mystery_logic.py`: Mystery 理论核心逻辑（基础过滤/三振共振/主升浪/平台突破/8项指标/技术细节/综合评分）
- `adaptive_platform.py`: 自适应 VAP-ATR 平台中枢（POC 筹码控制点 + 自适应通道，gemmi 优化）
- `pattern_recognition.py`: 形态识别（头肩/双重/三角形/楔形）
- `resonance_analyzer.py`: 三振共振分析（兼容保留）
- `__init__.py`: 模块初始化

**核心接口**（真实实现）:
```python
class MysteryLogic:
    def basic_filter(data: pd.DataFrame) -> Tuple[bool, List[str]]   # 基础过滤（年线/60日线/均线排列）
    def three_resonance_analysis(data, market_data: dict, industry_trend: bool) -> dict  # 三振共振
    def main_bull_wave_analysis(data: pd.DataFrame) -> dict          # 主升浪状态+判定依据
    def platform_breakthrough_analysis(data: pd.DataFrame, stock_code: str, weekly_data=None, monthly_data=None) -> dict  # 平台突破（自适应+固定+周/月线箱体）
    def main_bull_wave_checklist(data: pd.DataFrame, industry_trend: bool) -> dict   # 主升浪8项指标
    def technical_detail_capture(data: pd.DataFrame) -> dict         # 破五反五/筹码集中度
    def comprehensive_analysis(data: pd.DataFrame, market_data=None) -> dict  # 综合评分+建议

class AdaptivePlatform:  # analysis/adaptive_platform.py
    def calculate_adaptive_lookback(data, min_lookup=10, max_lookup=60) -> dict  # 换手率自适应周期
    def calculate_adaptive_vap_atr(data, n=60, atr_m=14, k=1.8, market_type) -> pd.DataFrame
    def analyze_adaptive_platform(data, stock_code, n=None, atr_m=None, k=None) -> dict  # POC/上下轨/突破/自适应周期
    def cns_adaptive_vap_atr(...)  # 兼容 docs/design.md 函数名

class PatternRecognition:
    def recognize_head_and_shoulders(data) -> dict   # 头肩顶/底（60日窗, 可靠性70）
    def recognize_double_top_bottom(data) -> dict    # 双重顶/底（40日窗, 可靠性75）
    def recognize_triangle_pattern(data) -> dict     # 三角形（30日窗, 可靠性60）
    def recognize_wedge_pattern(data) -> dict        # 楔形（25日窗, polyfit斜率）
    def recognize_all_patterns(data) -> dict         # 综合取最高可靠性为"主要形态"
```

#### 2.2.4 输出模块 (`output/`)
**职责**: 生成各种格式的分析报告
- `excel_generator.py`: Excel 报告生成（汇总表/技术指标表/个股详情表/每日汇总）
- `html_generator.py`: HTML 可视化报告 + 实时仪表板
- `__init__.py`: 模块初始化

**核心接口**（真实实现）:
```python
class ExcelGenerator:
    def generate_stock_analysis_report(analysis_results: dict, stock_data: dict) -> str
    def generate_daily_summary(analysis_results: dict, stock_data: dict) -> str
    # 文件名规则: utils.build_report_filename(analysis_results, 前缀, 后缀)
    #   单只: {前缀}_{股票名称}_{时间戳}.xlsx（如 股票分析报告_中国船舶_xxx.xlsx）
    #   多只: 每日{前缀}_...（如 每日股票分析报告_xxx.xlsx）

class HTMLGenerator:
    def generate_analysis_report(analysis_results: dict, stock_data: dict) -> str
    def generate_real_time_dashboard(analysis_results: dict) -> str
    # 卡片展示: 三振共振/多周期/主升浪指标/主升浪状态判定/平台箱体/自适应VAP-ATR/财务指标
```

#### 2.2.5 配置模块 (`config/`)
**职责**: 系统配置管理
- `config.yaml`: 主配置文件（股票列表18只/输出目录/日志）
- `__init__.py`: 配置加载

**配置结构**（真实）:
```yaml
# 基础配置
output_dir: "/home/ai/ai_runner/stock/output"   # 输出目录（git仓库，自动同步远端）
log_level: "INFO"
log_file: "logs/stock_analysis.log"

# 股票配置（已去重，18只）
stocks:
  - "sh600000"  # 浦发银行
  - "sh600036"  # 招商银行
  ...

# 行业配置
industries: ["银行", "白酒", "医药", "科技"]
```

#### 2.2.6 工具模块 (`utils/`)
**职责**: 提供通用工具函数
- `exception_handler.py`: 异常处理系统
- `__init__.py`: 工具函数（safe_division、build_report_filename 等）

**核心接口**（真实实现）:
```python
def build_report_filename(analysis_results: dict, prefix: str, suffix: str) -> str:
    """
    报告文件名构建（统一命名规则）
    - 单只股票（len==1）: {prefix}_{股票名称}_{时间戳}{suffix}
      例: 股票分析报告_中国船舶_20260810_020929.xlsx
    - 多只股票（每日分析）: 每日{prefix}_{时间戳}{suffix}
      例: 每日股票分析报告_20260810_015948.xlsx
    """

class ExceptionHandler:
    def handle_exception(e: Exception, context: str) -> None
    def log_error(message: str, level: str = "ERROR") -> None
    def log_info(message: str) -> None
    def log_warning(message: str) -> None
```

## 3. 指标计算方法（含非标准指标精确定义）

> 本章给出系统中**所有指标**的精确计算方法、参数与判定规则。
> 标准指标（MA/MACD/RSI 等）采用行业通用公式；**非标准指标**（震荡平台、形态识别、三振共振、主升浪8项、筹码集中度、破五反五等）为本系统自定义规则，必须按本章定义实现，否则报告结果不可复现。

---

### 3.1 标准技术指标（indicators/）

| 指标 | 公式 | 参数（默认） | 输出列 |
|---|---|---|---|
| MA | `MA_n = Σ(收盘价_i) / n`（简单移动平均，rolling） | n ∈ {5,10,20,60,250} | `MA5/MA10/MA20/MA60/MA250` |
| 均线排列 | 1=多头(MA5>MA10>MA20>MA60)，0=混合，-1=空头(MA5<MA10<MA20<MA60) | 取最新交易日 | `均线排列` |
| MA5斜率 | `(MA5[t] - MA5[t-5]) / 5` | 周期5 | `MA5_斜率` |
| MACD | EMA12-EMA26=DIF；DIF 的 EMA9=DEA；柱=DIF-DEA | fast=12, slow=26, signal=9 | `MACD/MACD_Signal/MACD_Histogram` |
| RSI | Wilder 平滑：`100 - 100/(1+RS)`，RS=平均涨幅/平均跌幅 | 14 | `RSI` |
| 量比 | `当日成交量 / 前5日均量` | 5 | `量比` |
| 换手率 | baostock 原始字段 | - | `换手率` |
| 价格动能 | 1/5/10/20 日变化率、5/10 日加速度、波动率 | - | `价格变化率*/价格加速度*/价格动能` |
| 量价配合度 | 涨跌幅与量比变化的协同方向（-1~1） | - | `量价配合度` |
| OBV | 累计量能线：涨日+量、跌日-量 | - | `OBV/OBV_MA/OBV信号` |

---

### 3.2 基础过滤（basic_filter）— 一票否决制

满足以下**全部**条件才通过，任一不满足即排除并记录原因：

| # | 规则 | 判定条件 | 排除原因文案 |
|---|---|---|---|
| 1 | 年线过滤 | `收盘价 >= MA250`（最新交易日） | "股价未运行在250日均线上方" |
| 2 | 周线过滤（日线近似） | `收盘价 >= MA60` | "股价未运行在60日均线上方" |
| 3 | 均线多头排列 | 有`均线排列`列：`均线排列 == 1`；否则手动比较 `MA5>MA10>MA20>MA60`（相邻比较） | "均线未呈现多头顺次排列" |

返回：`(是否通过: bool, 排除原因列表: List[str])`

---

### 3.3 三振共振分析（three_resonance_analysis）— 四维共振评分 ★★（docs/3z.md）

三振共振 = 个股30 + 大盘25 + 行业25 + 资金20 = 100 分（docs/3z.md 优化版），
真三振（三级）= 四维全部向好 + 资金活跃 + 大盘非高位。

**① 个股趋势（30分）**：
- `基础过滤` 通过 且 `均线多头`（均线排列==1 或 收盘价>MA20）→ +30

**② 大盘趋势（25分，含位置评估）**：
- `analyze_market_trend`：收盘>MA20 且 >MA60 → 向上（+25）；<MA20 且 <MA60 → 向下；否则震荡
- 趋势强度 = 近20日涨幅绝对值（min 100）
- **位置评估**：近120日 `(close-low)/(high-low)`，≥85% 高位 / ≤15% 低位 / 其余中位
- **高位惩罚**：position==高位 → 总分 -15

**③ 行业趋势（25分，docs/3z.md 优化版）**：
- `analyze_industry_trend({行业名: DataFrame})`，每行业评分（-2~+3）：
  - `bias` = 最新收盘 vs MA20 偏离%；`change_n` = 近10日涨幅（持续性）；`amount_score` = 成交额放大（最新 vs 前5日均额 ≥1.5倍 → +1）
  - 评分：`bias<-5→-2`；`bias<-2→-1`；`bias>5 且 change_n>3→2+amount`；`bias>2 且 change_n>0→1+amount`；否则 0
    （⚠️ 远端分支必须先判断，`bias<-5` 若放在 `bias<-2` 之后将永远不可达）
  - 强势 = score≥2；弱势 = score≤-2；中性 = 其余
- 整体趋势：`强势数 ≥ 弱势数+2 且 强势数 ≥ max(3, 总数×25%)` → 向上（+25）；反向 → 向下；否则震荡
  （数量阈值过滤"个别行业脉冲"）
- **最强板块**：score≥2 按 (score, change_n) 降序前5 → `top_industries`（报告展示）
- 行业数据来自 main.py `_build_industry_kline_map`：行业样本股票对齐日期后平均收盘价/成交额
  （无行业 DataFrame 时降级用外部 bool industry_trend）

**④ 资金确认（20分，新增）**：
- `analyze_capital_flow(data)`：量比（最新量/前5日均量）≥1.8→+12、≥1.5→+8；
  成交额比 ≥1.6→+5；换手率 ≥3%→+3；满分20
- `active = score≥8 或 量比≥1.5`

**⑤ 定级（calculate_resonance_score）**：
- **真三振（三级）**：score≥85 且 资金活跃 且 大盘/行业向上 且 个股OK
  （建议：强烈建议关注，大资金跨层级共振）
- 二级共振 ≥70 / 一级共振 ≥45 / 无共振 <45
- 返回兼容旧字段（个股共振/市场共振/行业共振/总共振评分/共振级别）+
  新字段（score/level/advice/is_true_three_strike/details/capital_active/
  industry_top/market_position）

返回（three_resonance_analysis 合并后）：`{个股趋势, 行业趋势, 大盘趋势, 三级共振,
共振评分, 共振级别, 共振建议, 资金活跃, 最强板块, 大盘位置, 真三振, 详情}`

---

### 3.4 主升浪状态判定（main_bull_wave_analysis）

按优先级依次判定，返回 `主升浪状态` + `判定依据`（逐条列出理由，供报告展示）：

| 优先级 | 状态 | 判定规则 |
|---|---|---|
| 1 | 主升持股期 | 近 5 日收盘价 > MA5 的天数 ≥ 3（"股价沿MA5上涨，不破MA5"） |
| 2 | 空中加油 | 收盘价 > MA20 且 近20日振幅 < 15% 且 `量比 < 1.0`（缩量横盘） |
| 3 | 强势上升 | `MA5斜率 > 0` |
| 4 | 观望 | 以上均不满足 |

- 振幅公式：`(近20日最高价 - 近20日最低价) / 近20日均收盘价 × 100`
- MA5斜率公式：`(MA5[t] - MA5[t-5]) / 5`，>0.5 记"强劲"，>0 记"温和"

---

### 3.5 震荡平台（平台突破分析，platform_breakthrough_analysis）— 非标准指标 ★

**平台定义**：近 20 个交易日的箱体区间
- `平台上沿 = max(近20日最高价)`
- `平台下沿 = min(近20日最低价)`
- `振幅 = (上沿 - 下沿) / 近20日均收盘价 × 100`

**判定流程**（按顺序）：

1. **横盘识别**：`振幅 < 15%` 且 数据≥10日 → 状态"横盘整理"
2. **突破确认**（在横盘基础上）：
   - 收盘价 > MA20
   - `量比 > 1.5`（放量）
   - `MACD_信号 == 1`（MACD零轴上金叉）
   - 三者满足 → 状态"突破确认"，`突破信号=True`
3. **买横机会**（未突破时）：
   - `(收盘价 - 平台下沿) / 平台下沿 × 100 < 5%`（贴近箱体下沿）
   - → 状态"买横机会"，`买横信号=True`

**输出**：`{平台状态, 突破信号, 买横信号, 平台范围: {上沿, 下沿, 周期:20}, 详情}`

> ⚠️ 平台范围必须随报告输出，明确"平台=近20日箱体[下沿, 上沿]"。回踩/突破均以该箱体为参照。

---

### 3.5.1 自适应 VAP-ATR 平台（gemmi 优化，docs/design.md）— 非标准指标 ★★

在固定箱体基础上，叠加**自适应 VAP-ATR 平台**（模块 `analysis/adaptive_platform.py`），解决固定箱体的两大缺陷（忽略量能、忽略波动率动态变化）：

**① 筹码分布 VAP → POC（筹码控制点）**：
- 用成交量加权的价格分布替代固定箱体中轴
- 对最近 N=60 日的**筹码重心价** `P_core` 分 50 档位直方图（模拟 KDE），
  `POC = 成交量加权密度最高档位的中心价`
- **K线重心因子**（A股修正，防长上影线误导）：
  `G_t = (Close_t - Low_t) / (High_t - Low_t)`（一字板时分母取 0.001）
  `P_core_t = Low_t + G_t × (High_t - Low_t)`

**② 修正真实波幅 MTR（A股修正，防涨停 ATR 冻结）**：
- `raw_TR = max(High-Low, |High-昨收|, |Low-昨收|)`
- 若 `Close ≥ round(昨收×(1+涨停阈值), 2)`（封涨停）：`MTR = MA(raw_TR, 14)`
- 涨停阈值：主板 10%（代码 60x/00x 等）、创业板/科创板 20%（300/301/688 开头）

**③ 自适应通道**：
- `上轨 = POC + k × MATR`，`下轨 = POC - k × MATR`（k 默认 1.8）
- 低波动时箱体自动收窄（捕捉异动），高波动时箱体拓宽（过滤假突破）

**④ A股实体突破信号**（四条件同时满足）：
- `Close > 上轨` 且 `Close > Open`（阳线）且 `G_t > 0.5`（重心偏上，非长上影假突破）
- 且前一日非涨停（排除一字板复牌首日情绪溢价）

**输出**：`{平台方式: '自适应VAP-ATR', POC, 自适应上轨, 自适应下轨, ATR, 突破信号, 平台范围, 自适应周期}`

平台突破分析将自适应平台与固定箱体**双重判定**：自适应突破信号优先（更精确），固定箱体逻辑保留作补充校验。`平台范围` 字段输出自适应箱体（含 POC）。

---

### 3.5.2 自适应检测周期（gemmi_an.md 优化）— 非标准指标 ★★

检测周期不固定，而由**换手率循环**决定（时间周期只是表象，资金换手周期才是本质）：

**① 基础公式（筹码换手周期）**：
- `日均换手率 D̄ = mean(近20日换手率)`
- `理论N = 70% / D̄`（取70%换手而非100%，考虑A股锁仓筹码）
- `自适应N = clip(理论N, 10, 60)`（防妖股周期太短失真 / 防蓝筹周期太长滞后）
- 例：妖股换手15% → N=10；白马换手0.8% → N=60；中等换手3% → N=23

**② 双周期嵌套（快窗口 + 慢窗口）**：
- 慢窗口（POC 筹码分布）：`n = 自适应N`（锚定筹码控制点）
- 快窗口（ATR 波动率）：`atr_m = clip(round(n/4), 10, 14)`（捕捉近两周波动率异动）

**③ 波动率乘数 k 自适应**：
- 日均换手率 ≥10%（活跃股/妖股）→ k=2.2（放宽箱体容忍剧烈洗盘）
- 日均换手率 3~10% → k=1.8（默认）
- 日均换手率 <3%（蓝筹/白马）→ k=1.5（收紧箱体提高灵敏度）

**④ 多周期共振架构**（T+1 必修课，工程架构）：
- 周线（Window≈26）：确认大趋势（8项指标得分 > 0.6）
- 日线（Window=自适应N）：定位自适应 VAP 箱体，等待 `Close > 上轨`
- 30/60分钟（Window≈20）：突破瞬间量能"三振"确认（分时数据，系统当前未接入，预留）

**输出**：`自适应周期 = {adaptive_n, atr_m, k, avg_turnover, theoretical_n}`（随报告展示）

---

### 3.5.3 多周期箱体分析（周线/月线）— 非标准指标 ★★

在日线平台基础上，叠加**周线/月线箱体**（`_analyze_cycle_box`），识别多周期级别的突破/回踩/触底信号：

**① 箱体定义**：
- 周线箱体：近 20 根周K 的 `[最低价最小值, 最高价最大值]`（约 5 个月）
- 月线箱体：近 20 根月K 的 `[最低价最小值, 最高价最大值]`（约 20 个月）
- 当前价 = 最新一期收盘价

**② 位置判断**（容差 2%）：
- `当前 > 上沿×1.02` → 上沿上方
- `当前 ≥ 上沿×0.98` → 上沿附近
- `当前 ≤ 下沿×1.02` → 下沿附近
- `当前 < 下沿×0.98` → 下沿下方
- 其他 → 箱体内

**③ 状态识别**：
| 状态 | 触发条件 | 含义 |
|---|---|---|
| 突破上沿 | 位置=上沿上方 且 前一期收盘 ≤ 上沿 | 刚突破箱体上沿（买入信号） |
| 回踩上沿 | 位置=上沿附近 | 突破后回踩上沿不破（确认支撑） |
| 跌到下沿 | 位置=下沿附近 | 跌至箱体下沿（观察支撑/买横） |
| 跌破下沿 | 位置=下沿下方 | 有效跌破箱体（风险信号） |
| 箱体内震荡 | 其他 | 箱体内部整理 |

**④ 输出**：`周线箱体/月线箱体 = {周期, 上沿, 下沿, 当前价, 位置, 状态, 距上沿%, 距下沿%, 自适应周期, 详情}`，
汇总为 `多周期箱体状态 = "周线:突破上沿(35.6) | 月线:回踩上沿(32.1)"`

**⑤ 自适应周期输出**：周线/月线箱体结果含 `自适应周期 = {adaptive_n, avg_turnover}`
（日线换手率驱动的检测周期，见 3.5.2），随报告在周线/月线箱体行展示
（如 `周线箱体...自适应N: 35日`）。

平台突破分析（`platform_breakthrough_analysis`）新增参数 `weekly_data`/`monthly_data`，
在自适应平台与固定箱体之后进行多周期箱体分析，随报告展示。

**⑥ 报告格式**：
- Excel 个股详情工作表名：`个股{股票名称}_{股票代码}`（如 `个股中国船舶_sh600150`，超31字符截断）
- Excel 周线/月线箱体区块含：上沿/下沿/当前价/状态/距上沿%/距下沿%/自适应周期N
- HTML 多周期箱体区块含：下沿~上沿/当前/状态/自适应N
- 终端 `📐` 行含箱体范围/状态 + `⏱️` 行含自适应周期

---

### 3.6 主升浪8项指标对比表（main_bull_wave_checklist）— 非标准指标 ★

逐项判定（True/False），统计满足数量（满分8）：

| # | 指标 | 判定规则 |
|---|---|---|
| 1 | 长期横盘3个月以上 | 近 60 日振幅 < 25%（振幅公式见 3.5） |
| 2 | 60日均线开始向上 | `MA60[t] - MA60[t-5] > 0` |
| 3 | 股价突破平台 | `收盘价 >= 近20日最高价`（创20日新高） |
| 4 | 放量超20日均量2倍 | `当日成交量 / 近20日均量 >= 2.0` |
| 5 | 回踩不破+MACD零轴金叉 | ① 前一日最低价 ≥ 近20日最低价×0.98（回踩平台下沿未破，允许2%误差）② MACD上穿信号线（金叉）或 MACD>信号线 且 `|MACD| < 收盘价×1%`（零轴附近） |
| 6 | RSI>50继续走强 | `RSI > 50` 且 `RSI[t] >= RSI[t-5]` |
| 7 | 主力资金连续流入 | 近 3 日中 ≥ 2 日 `涨跌幅 > 0`（无主力资金接口，用涨跌近似） |
| 8 | 行业板块同步走强 | 行业趋势为 True（见 3.3②） |

**综合判断**：满足 ≥6 → "主升浪高概率"；≥4 → "主升浪中概率"；≥2 → "关注观察"；否则"暂不参与"。

输出含 `平台范围`（近20日箱体，同 3.5）供回踩/突破说明引用。

---

### 3.7 技术细节（technical_detail_capture）— 非标准指标 ★

**① 破五反五**（洗盘信号）：
- 昨日：`收盘价 < MA5`（破五）
- 今日：`收盘价 > MA5` 且 `量比 > 1.5`（放量收回，反五）
- 两者满足 → `破五反五 = True`

**② 筹码集中度**（用换手率估算）：
- `近20日平均换手率 = mean(换手率[-20:])`，记为 `chip_val`
- 分级：<2% → "高度集中"；2~5% → "相对集中"；5~10% → "分散"；≥10% → "高度分散"
- **数值必须随报告输出**：`筹码集中度数值 = chip_val`
- **筹码趋势**：`近10日均换手率 < 前10日均换手率` → "趋于集中"，否则"趋于分散"

---

### 3.8 形态识别（pattern_recognition.py）— 非标准指标 ★

**通用流程**：找局部极值（相邻±2日内的最高/最低）→ 匹配形态 → 输出 `{形态类型, 形态状态, 可靠性, 目标价位, 详情}`。`recognize_all_patterns` 取 4 类形态中可靠性最高者为"主要形态"。

**① 头肩顶/底**（窗口：最近60日）：
- 局部高点：`最高价[i] > 最高价[i±1] 且 > 最高价[i±2]`
- 三点间隔：`头-左肩 > 5日` 且 `右肩-头 > 5日`
- 头肩顶：`头高 > 左肩高 且 头高 > 右肩高`；颈线=中间波谷最低价
- 头肩底：对称（用最低价判断）
- 可靠性：70；目标价：顶=`颈线 - (头高-颈线)`，底=`颈线 + (颈线-头低)`

**② 双重顶/底**（窗口：最近40日）：
- 局部极值（相邻±1日）
- 两顶/两底间隔：`5 ≤ 间隔 ≤ 15日`
- 价格差：`|P1-P2|/P1 × 100 < 5%`
- 颈线=两顶之间最低价（顶）/两底之间最高价（底）
- 可靠性：75；目标价：顶=`颈线 - 高度`，底=`颈线 + 深度`

**③ 三角形整理**（窗口：最近30日）：
- 30日波动率 < 15%，且后半段波动 < 前半段波动（收敛）
- 类型判定（首尾最高/最低比较）：
  - 高点降+低点升 → 对称三角形
  - 高点降+低点降 → 下降三角形（看跌）
  - 高点升+低点升 → 上升三角形（看涨）
  - 其他 → 三角形整理
- 收敛程度 = `(前半波动-后半波动)/前半波动 × 100`
- 可靠性：60；突破方向：上升三角→向上、下降三角→向下、对称→按近5日收盘趋势

**④ 楔形**（窗口：最近25日）：
- 对最高价、最低价分别做线性拟合（np.polyfit 一次），得 `high_slope`、`low_slope`
- 双斜率为正 → 上升楔形（看跌）；双斜率为负 → 下降楔形（看涨）；一正一负 → 混合楔形
- 可靠性 = `min(|high_slope-low_slope| × 1000, 80)`

---

### 3.9 板块评级（_analyze_industry_trend）— 非标准指标 ★

- 样本：同行业股票（排除自身，最多3只），取近 5/10/20 日均涨跌幅
- `avg_5d`=样本近5日平均涨跌幅，`trend_10`、`trend_20` 同理
- 评级规则：
  - `avg_5d > 0.5 且 trend_10 > 0 且 trend_20 > 0` → "强势上涨"
  - `avg_5d > 0 且 trend_10 > 0` → "稳步走强"
  - `avg_5d > 0` → "短期走强"
  - `avg_5d < -0.5 且 trend_10 < 0` → "弱势下跌"
  - `avg_5d < 0` → "短期走弱"
  - 其他 → "震荡整理"

---

### 3.10 多周期分析（_analyze_multi_period）— 非标准指标 ★

**周线**（weekly）：计算 `MA5/MA10/MA20`（周线收盘价 rolling）
- 多头排列：`MA5 > MA10 > MA20` 且 `收盘价 > MA20`
- 空头排列：`MA5 < MA10 < MA20`
- 其他：震荡整理

**月线**（monthly）：计算 `MA5/MA10`
- 多头排列：`MA5 > MA10` 且 `收盘价 > MA10`
- 空头排列：`MA5 < MA10`
- 其他：震荡整理

**多周期共振**：周线多头 ∧ 月线多头（日线趋势见 3.3①）。

---

### 3.11 综合评分与建议（comprehensive_analysis）

| 维度 | 分值 |
|---|---|
| 基础过滤通过 | +20 |
| 三振共振成立 | +30 |
| 主升浪状态 ∈ {主升持股期, 空中加油, 强势上升} | +25 |
| 平台状态 ∈ {突破确认, 买横机会} | +15 |
| 破五反五 | +10 |

- 总分封顶 100
- 建议：≥80 "强烈买入"；≥60 "买入"；≥40 "关注"；否则"观望"
- 止损位：`MA20 × 0.95`（MA20 的 95%）

### 3.11.1 三大心法综合信号（comprehensive_signal_analysis）— ★★（docs/refact1.md）

严格量化《Mistery趋势交易论》三大心法，与四维共振闭环输出可操作信号：

**心法① 日线多头基础滤网（basic_filter 增强）**：
- 原有：收盘 > MA250、收盘 > MA60、均线多头排列（MA5>MA10>MA20>MA60）
- **新增**：MA5/MA10/MA20/MA60 **全部运行在 MA250 年线之上**
  （股价站上年线 ≠ 均线体系站稳年线；空头环境下均线在年线下方即使股价反弹也视为弱）

**心法② 周线方向锚定（weekly_anchor_check）**：
- 周线收盘 > 60 周均线（MA60_W），且 MA60_W 斜率不向下（允许走平，3周对比窗口）
- 数据不足 60 周时用可用窗口；无周线数据跳过（视为锚定）

**心法③ 破五反五容错（check_po5_fan5）**：
- 允许跌破 MA5：近5日内曾破五 → 收回且 2 个交易日内收回 + MA20 斜率向上（3日窗口）
- 返回：破五反五/破五天数/MA20斜率/原因

**主升浪信号（main_bull_wave_signal）**：`年线滤网 ∧ 周线锚定 ∧ (股价>MA5 ∨ 破五反五)`

**综合评分（comprehensive_signal_analysis）**：
- 未通过年线滤网 → 综合评分 0，操作建议"观望（未通过年线滤网）"
- 通过后：`综合评分 = 共振评分×0.6 + 主升浪信号40×0.4`
- 建议：真三振+主升浪 → "强烈关注"；真三振 → "重点关注"；主升浪 → "可关注（主升浪持股期）"；否则用共振建议

**数据适配（utils/data_feeder.py 新增）**：DataFeeder 统一接口（get_daily 附 MA5-250 /
get_weekly 附 MA60_W / get_market_index），可独立用于扫描脚本。

**配置（config.yaml analysis 段）**：ma_params / break_five（recover_days=2, ma20_slope_lookback=3）/
resonance（score_threshold=85, position_penalty=15）/ position（仓位管理参数）

**集成**：main.py `_perform_mystery_analysis` 调用 comprehensive_signal_analysis
（weekly_data 取 processed_data 周K），新增字段：核心信号/操作建议/年线滤网/周线锚定/
破五反五/主升浪信号/综合信号详情（不影响旧版 comprehensive_analysis 及报告字段）

---

### 3.12 财务指标（get_financial_data）— 非标准指标 ★

- `ROE`：baostock `query_profit_data` 最新报告期 `roeAvg` 字段
- `EPS`：同上 `epsTTM` 字段
- `PE`：`当前股价 / EPS`
- `PB`：`当前股价 / (EPS / ROE)`（每股净资产 BPS = EPS/ROE 推算）
- `股息率`：`最近年度每股税前股息(dividCashPsBeforeTax) / 当前股价 × 100`

## 4. 数据流设计

### 4.1 数据获取流程（真实）
```
用户输入股票代码
  → baostock login()
  → 获取日线/周线/月线历史数据（normalize_stock_code 标准化为 sh.600150 9位格式）
  → 获取大盘指数数据（上证指数/深证成指/沪深300/创业板指）
  → 获取行业分类数据（code→所属板块映射，板块样本股近5/10/20日涨跌）
  → 获取财务数据（query_profit_data: ROE/EPS；query_dividend_data: 股息率）
  → 获取股票名称（query_stock_basic: 中国船舶）
  → 数据预处理（去重/排序/缺失值处理）
  → 技术指标计算（MA/MACD/RSI/量比/动能/量价）
  → Mystery理论分析（基础过滤/三振共振/主升浪/平台突破[自适应+固定]/8项指标/技术细节）
  → 形态识别（头肩/双重/三角形/楔形）→ 多周期分析（周线/月线）
  → 综合评分 → 生成报告（Excel/HTML/汇总/仪表板）
  → git add/commit/push 同步远端
  → logout()
```

### 4.2 数据处理流程
```
原始数据 → 数据清洗（去重/排序）→ 缺失值处理 → 
技术指标计算（rolling窗口）→ 特征提取 → 分析结果
```

### 4.3 输出流程（真实）
```
分析结果 → 文件名规则构建（单只含名称/每日加前缀）
  → Excel生成（汇总表/技术指标表/个股详情表）
  → HTML生成（卡片式报告/实时仪表板）
  → 文本汇总报告
  → git同步（_sync_output_to_git: add → commit → push 443端口）
```

### 4.4 数据中枢与全量自动化分析（gemmi_an.md）— ★★

**整体架构**（四大支柱）：
```
[交易所/BaoStock API] ──→ [sync_all_market.py 批量同步脚本]
                                │ (增量安全写入 safe_upsert)
                                ▼
                        [SQLite本地缓存 mystery_cache.db]
                                │ (Sub-ms高速读取)
                                ▼
[run_market_scan.py 全量扫描] ←── [data_engine.py Cache-Aside抽象层]
        │
        ├──→ 生成报告（output/）
        └──→ 核心信号: 自适应VAP-ATR突破 / 筹码低位共振
```

**① 数据库设计（data/db_manager.py, mystery_cache.db）**：
- `stock_industry_info`：证券代码/名称/类型/行业分类（主键 `code`，type=1股票 2指数）
- `stock_kline_data`：核心行情表，联合主键 `(code, date, period)` 合并存储日/周/月线，
  含高开低收/成交量额/换手率/复权因子，支持前/后复权
- `stock_financial_data`：基本面快照，联合主键 `(code, report_date)`
- 覆盖索引 `idx_kline_fast_query (code, period, date)` → 百万级数据毫秒级 Pandas 加载
- WAL 模式 + `check_same_thread=False` + RLock → 多线程安全读写
- `upsert_kline` 使用 `INSERT OR REPLACE` 实现线程安全增量覆盖（safe_upsert）

**② 数据抽象层（data/data_engine.py, MysteryDataEngine）**：
- **Cache-Aside 旁路缓存模式**：读取先查本地缓存 → 未命中请求 baostock → 清洗后回填
- `get_kline(code, period)`：毫秒级缓存读取，未命中自动穿透 baostock 并增量回填
- `sync_stock_list()`：全市场证券列表同步（query_stock_basic 全量，默认过滤指数）
- `_clean_kline`：中文列名→英文标准化 + 去重列 + 排序（防重复列导致 Series 歧义）
- `get_financial()`：财务数据 Cache-Aside

**③ 全量同步脚本（data/sync_all_market.py）**：
- `get_all_a_shares()`：动态获取市场所有 A 股（5208 只上市股票）
- 多线程 `ThreadPoolExecutor` 并行同步（默认 8 线程），`sync_worker` 单股增量拉取
- 参数：`--period`（daily/weekly/monthly）、`--days` 回溯、`--limit` 测试限制、`--threads`
- 用法：`python data/sync_all_market.py --period daily --days 1100`

**④ 全量扫描分析（data/run_market_scan.py）**：
- `load_local_cached_tickers()`：从缓存加载股票列表（未缓存自动同步）
- `scan_single_stock()`：自适应换手周期 → 技术指标 → 自适应 VAP-ATR 平台 → 主升浪8项 → 信号捕获
- **核心信号**：① VAP-ATR 突破（Close>上轨且阳线且重心>0.5）② 筹码低位共振（近20日均换手<2%）
- 输出：市场扫描报告 .txt（信号股票Top）+ 市场扫描明细 .csv
- 用法：`python data/run_market_scan.py --limit 500 --sync`

**⑤ 实战化运行闭环**：
1. 数据初始化：`python data/sync_all_market.py`（全量更新本地缓存）
2. 每日分析：闭市后 `python data/run_market_scan.py`（增量计算+信号捕获）
3. 成果查看：output 目录报告，支持自动化决策

### 4.5 双源退避与日K重采样（docs/sources.md）— ★★

**总体架构**：
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
  SQLite Cache（stock_kline_data 表）
```

**① 数据源封装（data/akshare_client.py, AkshareClient）**：
- 接口与 `BaostockClient` 对齐：login/logout/get_daily/weekly/monthly_data
- 输出统一中文列：`日期/代码/开盘价/最高价/最低价/收盘价/成交量/成交额/换手率/涨跌幅`
- 内置限速（rate_limit 默认0.3s），AKShare 为爬虫源需防高频被封

**② 日K重采样（data/kline_resampler.py, KLineResampler）**：
- 周K：`W-FRI` 聚合（周五收）；月K：`ME` 聚合（月末，pandas3.0）
- 聚合规则：开=first 高=max 低=min 收=last 量=sum 额=sum 换手=sum
- 涨跌幅用收盘价 pct_change 重算，保证多周期数据与日K严格对齐

**③ 统一入口（data/market_data_client.py, MarketDataClient）**：
- 主备源退避：主源重试 `retry_times` 次（指数退避 `retry_delay×2^n`）→ 失败切备用源
- `prefer_resample=true`：周/月K 由日K重采样生成（默认，周期对齐）
- baostock 调用复用全局锁 `BAOSTOCK_LOCK`（线程安全）；AKShare 内置限速

**④ 配置（config/config.yaml, data_source 段）**：
```yaml
data_source:
  primary: "akshare"        # 主源：akshare / baostock
  fallback: "baostock"      # 备用源
  retry_times: 3            # 每源最大重试次数
  retry_delay: 2            # 初始退避延迟（秒），指数递增
  prefer_resample: true     # true=强制日K重采样周/月
  adjust: "qfq"             # 复权：qfq/hfq/none
  rate_limit_akshare: 0.3   # AKShare 请求间隔（秒）
  timeout: 30               # 单次请求超时（秒）
```

**⑤ 集成方式**：`MysteryDataEngine(db_path, config)` 传入含 `data_source` 段的 config 即启用双源模式；
不传 config 保持原 baostock 单源逻辑（向后兼容）。

### 4.6 通达信本地数据源（docs/tdx.md）— ★★

**方案概述**：使用 `mootdx` 解析通达信官方数据包（hsjday.zip 解压的 .day 文件），封装为 `TdxLocalClient`
作为**主数据源（tdx_local）**，形成三级退避链：`tdx_local → akshare → baostock`。
本地读取毫秒级、离线高可用，网络源兜底。

**① 数据目录**：
- 默认 `/home/ai/ai_runner/stock/data/tdx_vipdoc`（**Git 仓库外**，避免大体积二进制入库）
- 环境变量 `TDX_VIPDOC_DIR` 可覆盖（加载优先级：环境变量 > 配置 > 默认绝对路径）
- 目录结构：`sh/lday/sh600000.day`、`sz/lday/`、`bj/lday/`（北交所）
- `.gitignore` 已添加 `data/tdx_vipdoc/`、`*.zip`、`*.day`、`*.fin`

**② TdxLocalClient（data/tdx_local_client.py）**：
- 接口与 BaostockClient/AkshareClient 对齐：login/logout/get_daily_data（兼容周/月接口返回空）
- 市场判定：`6/9/5→sh`（沪市A股/科创板/ETF）、`0/2/3→sz`（深市/创业板）、`4/8→bj`（北交所）
- 仅支持日线（.day 文件无换手率→None、涨跌幅 pct_change 重算）；周/月K由上层 `KLineResampler` 重采样
- 财务数据 mootdx 0.11.7 不支持本地解析 → 返回空由 AKShare/baostock 兜底

**③ MarketDataClient 三级退避**：
- `fallback` 支持**列表**：`primary + [akshare, baostock]`，`source_order` 自动构建去重
- `tdx_local` 仅处理 daily，周/月走 prefer_resample 重采样
- 实测退避链：tdx 空数据 → akshare 网络失败 → baostock 成功（依次降级不中断）

**④ 数据包下载（scripts/download_tdx_packages.py）**：
```bash
python scripts/download_tdx_packages.py             # 下载全部(hsjday/tdxfin/tdxgp)
python scripts/download_tdx_packages.py --pkg hsjday  # 仅日线包
TDX_VIPDOC_DIR=/path python scripts/download_tdx_packages.py  # 自定义目录
```
数据包源：`https://data.tdx.com.cn/vipdoc/`（hsjday 历史日线 / tdxfin 财务 / tdxgp 股票列表）

**⑤ 数据库循环覆盖（kline_limit）**：
- `db_manager.trim_kline(code, period, max_rows)`：删除旧数据仅保留最新 N 条
- `upsert_kline(df, code, period, max_rows)` 写入后自动裁剪
- `data_engine` 从 config 读取 `kline_limit`：日线 2000 / 周线 500 / 月线 300
- 实测：120 条日K 写入 max_rows=100 → 保留最新 100 条

**⑥ 配置（config/config.yaml data_source 段）**：
```yaml
data_source:
  primary: "tdx_local"              # 主源：tdx_local / akshare / baostock
  fallback: ["akshare", "baostock"] # 备用源列表（依次退避）
  tdx:
    vipdoc_dir: "/home/ai/ai_runner/stock/data/tdx_vipdoc"  # 仓库外，可被TDX_VIPDOC_DIR覆盖
    enable: true
    auto_download: false
  kline_limit:
    daily: 2000
    weekly: 500
    monthly: 300
    enable_cleanup: true
```

### 4.7 增量更新与复权因子（docs/step1.md 阶段1优化）— ★★

**方案概述**：基于 step1.md 实施指南，实现**本地 .day 文件增量更新**（毫秒级、零网络）、
**除权除息复权因子**（gbbq 解析 + 前复权计算）与**重采样升级**（交易日历感知 + 最少K线数过滤），
将"每日分析全量网络拉取"优化为"本地增量 + 缓存直读"。

**① 增量更新器（data/tdx_incremental.py，新增）**：
- 直接 `struct.unpack('<IIIIIfII')` 解析 .day 文件（32字节/条），不依赖 mootdx，性能极高
- `fetch_delta(code, last_date)`：仅读取 **last_date 之后** 的尾部记录（幂等，重复同步不重复）
- 兼容两种目录结构：标准 `{vipdoc}/{market}/lday/` 与历史遗留扁平文件名
  `sh\lday\sh600150.day`（旧版 extractall 把 zip 内反斜杠路径当文件名的 bug，见 ⑥）
- 返回标准中文列名 DataFrame；成交量 股→手（/100，与 AKShare 一致）；涨跌幅 pct_change 重算
- 市场判定 `6/9/5→sh、0/2/3→sz、4/8→bj`

**② 复权因子（data/tdx_gbbq.py，新增）**：
- 解析通达信 gbbq 文件（60字节/条：date+code+送股/配股/配股价/转增/派息）→ 除权事件表
- `calc_qfq_factor(daily_df, events)`：前复权因子（**除权日实际价格比**算法，数学上等价于精确前复权；
  最新交易日因子=1，自最新向最早遍历除权日，除权日之前价格 ×= 除权日收盘/前一日收盘）
- `calc_hfq_factor`：后复权因子（从最早累计向上调整）
- `apply_adjust(code, daily_df, adjust)`：统一应用复权（仅处理存在的价格列，缺列安全）
- **无 gbbq 文件时 graceful 降级**（factors_available=False），由上层连续性检查兜底

**③ 重采样升级（data/kline_resampler.py）**：
- `set_calendar(calendar)`：注入交易日历（来源 `db.get_trading_calendar()` = 缓存日K日期并集）
- 最少K线数过滤：周K≥`min_bars_weekly`(3)、月K≥`min_bars_monthly`(10) 根日K，不足剔除
- `keep_latest_period=true`（默认）：**最新周期豁免**（进行中的周/月K必须保留，否则最新分析数据缺失）
- 向后兼容：不传 config 时使用默认参数

**④ MarketDataClient 增量集成（data/market_data_client.py）**：
- `fetch_daily` 增量优先：查 `db.get_last_date` → 读 .day 尾部增量 →
  - 无增量 → **直接返回缓存**（零网络，毫秒级）
  - 有增量 → 复权处理 → 缓存+增量合并（同日期以增量为准）→ 返回完整序列
  - 无缓存锚点 / 除权断裂 / 异常 → 返回 None 回退在线源（原三级退避不变）
- 复权一致性决策树（`_adjust_delta`）：
  1. gbbq 因子可用 → 直接应用复权调整
  2. 否则连续性检查：`|增量首收盘/缓存末收盘 - 1| > gap_threshold(0.11)` → 疑似除权 → 回退在线源
  3. 增量内部跳变 > 阈值 → 疑似窗口内除权 → 回退在线源
  4. 通过 → 直接合并（前复权不改变最新价，增量原始价与缓存前复权价在最新段基准一致）；
     仅当增量首日与缓存末日**重叠**时才做比例对齐
- `db_manager` 扩展：`get_last_date`（增量锚点）、`get_trading_calendar`、`upsert_kline` 兼容中文列名
- `data_engine` 双源模式 upsert 补传 `max_rows`（循环覆盖在双源模式同样生效）
- 实测：600150 每日分析从 18.8s（akshare 重试+退避）→ **0.11s**（缓存直读，零网络）

**⑤ 配置（config/config.yaml data_source 段新增）**：
```yaml
data_source:
  incremental:
    enable: true               # 增量更新开关（fetch_daily 优先本地增量）
    max_bars_per_request: 800  # 单次最大增量条数
    gap_threshold: 0.11        # 除权断裂检测阈值
  resample:
    min_bars_weekly: 3
    min_bars_monthly: 10
    use_trading_calendar: true
    keep_latest_period: true
  tdx:
    gbbq_file: "/home/ai/ai_runner/stock/data/tdx_vipdoc/cw/gbbq"  # 可选
```

**⑥ 数据包解压修复（scripts/download_tdx_packages.py）**：
- 历史 bug：`zipfile.extractall` 把通达信 zip 内反斜杠路径（`sh\lday\sh600150.day`）直接当文件名解压，
  产生 12345 个扁平文件，mootdx/TdxLocalClient 目录结构读取失效（tdx_local 主源从未真正命中）
- 修复：`_safe_extract()` 反斜杠→正斜杠按目录解压 + zip slip 防护；`fix_flat_structure()` 幂等修复遗留扁平结构
- 用法：`python scripts/download_tdx_packages.py --fix-flat`（修复遗留文件，无需重新下载）

### 4.8 协议增强与源健康熔断（docs/step2.md 阶段2优化）— ★★

**方案概述**：基于 step2.md 实施指南，实现**通达信行情协议客户端**（本地数据缺失时协议增量补充）
与**源健康评分与动态熔断**（SourceHealth 模块，自动屏蔽故障源、恢复后自动放回）。

**① 源健康评分（data/source_health.py，新增）**：
- 核心字段：success_count / failure_count / consecutive_failures / last_failure_time /
  window(滑动窗口 maxlen=window_size) / health_score / is_open / avg_latency_ms
- `record(source, success, latency_ms)`：每次请求后记录；健康分 = 滑动窗口成功率×100
- **熔断**：`consecutive_failures >= fail_threshold(3)` → is_open=False，告警熔断
- **恢复**：超过 `recover_seconds(300)` 后自动重置熔断状态，允许试探请求
- `get_ordered_sources(preferred)`：剔除熔断源；`sort_by_health=true` 时按健康分降序动态排序
- **空数据记成功**（step2.md 明确）：停牌股/无数据范围不触发误熔断
- 配置（config.yaml data_source.health）：enable / window_size / fail_threshold /
  recover_seconds / sort_by_health

**② 协议客户端（data/tdx_protocol_client.py，新增）**：
- 从通达信行情服务器（TCP 7709）实时获取日K，用于本地 .day 缺失时增量补充
- 自动降级链：`easy_tdx`（UnifiedTdxClient）→ `mootdx Quotes`（Quotes.factory）→ 无客户端（仅本地）
- `fetch_daily(code, start_date, end_date, adjust)` 输出标准中文列名（与 TdxLocalClient 对齐）
- 协议数据为不复权原始价，复权由上层处理
- 本机环境：easy_tdx 未安装（pip sha256 校验失败）→ 自动降级 mootdx Quotes；
  行情服务器 119.147.212.81:7709 不可达（网络限制）→ 协议补充为空，退避链兜底

**③ MarketDataClient 健康集成**：
- `__init__` 注入 `SourceHealth(config)`；`TdxLocalClient` 传入 config（含协议客户端）
- `_fetch_with_fallback`：源列表先经 `get_ordered_sources` 健康过滤（熔断剔除），
  每次请求计时 → `record(成功/失败, latency_ms)`；日志含耗时（ms）
- 成功（非空）→ 记成功；空数据 → 记成功（避免误熔断）；异常 → 记失败（连续失败触发熔断）
- 与 step1 增量路径共存：增量优先（零网络），增量不可用时退避链带健康熔断

**④ TdxLocalClient 协议补充**：
- `__init__(vipdoc_dir, enable, config)`：config 非空时创建 `TdxProtocolClient`
- `get_daily_data`：本地读取失败/无数据 → `_fetch_protocol`（需 start_date/end_date）
  从行情服务器补充，返回标准中文列名

**⑤ 配置（config/config.yaml data_source 段新增）**：
```yaml
data_source:
  health:
    enable: true
    window_size: 10
    fail_threshold: 3
    recover_seconds: 300
    sort_by_health: false
  tdx:
    server_host: "119.147.212.81"   # 通达信行情服务器
    server_port: 7709
```

**⑥ 依赖**：requirements.txt 新增可选 `easy_tdx`（注释掉，未安装时自动降级 mootdx Quotes）

**⑦ 集成修复（step2 实现中暴露的问题）**：
- **重采样日历过滤修复**（kline_resampler.py）：交易日历来自缓存日K并集，可能**落后于增量数据**
  （缓存 08-13 vs .day 增量 08-14）→ 原逻辑会误删最新交易日 → 周/月K最新收盘错误（33.78≠33.42）。
  修复：保留"日历中日期 ∪ 日历最大日期之后的日期"，仅剔除日历范围内非交易日
- **keep 索引对齐**（kline_resampler.py）：`resampled[keep]` 在 dropna 后索引错位产生
  UserWarning → `keep.reindex(resampled.index, fill_value=False)` 对齐
- **增量行换手率缺失**（market_data_client.py）：.day 文件无换手率 → 增量合并后最新行换手率 None →
  分析打印/HTML 生成崩溃（NoneType.format）。修复：合并后 `换手率.ffill()`（用缓存最近值近似）；
  main.py 技术指标打印 + html_generator `_val` 加 `or 0` 防御
- 实测：修复后 600150 完整单股分析无异常（最新价 33.42/换手率 0.87% 近似值/周月线 33.42）

### 4.9 生产化增强（docs/step3.md 阶段3优化）— ★★

**方案概述**：基于 step3.md 实施指南，完成**财务数据本地化接口**、**路径环境变量优先**、
**可观测性（源健康报告）**、**单元测试**与**并发同步优化（断点续传+进度条）**，达到生产级标准。

**① 路径与环境变量优先（utils/path_utils.py，新增）**：
- `resolve_path(env_key, config_value, default)`：**环境变量 > 配置值 > 默认值**
- `resolve_path_abs`：相对路径转绝对（base_dir 可指定）
- 应用点：`TDX_VIPDOC_DIR`（tdx_local_client/market_data_client 的 vipdoc 路径）、
  `MYSTERY_DB_PATH`（db_manager 数据库路径）、`SOURCE_REPORT_DIR`（源健康报告目录）

**② 财务数据本地化接口（tdx_local_client + financial_storage）**：
- `TdxLocalClient.get_financial_data(stock_code)`：本地财务读取接口（标准化字段）；
  说明：通达信 gpcw*.dat 为专有二进制格式，mootdx 0.11.7 financial 为空包 → 暂不解析，
  返回空由 AKShare/Baostock 在线源兜底（现有流程已覆盖并缓存 SQLite）
- `financial_source_status()`：探测本地财务包状态（gpcw*.zip 数量），可观测性用
- `data/financial_storage.py`（新增）：财务标准化存储门面——封装 `stock_financial_data`
  宽表（主键 code+report_date）：save_financial（中文/英文列名兼容）/ load_latest /
  load_history / is_cached / local_source_status（gpcw 探测）

**③ 可观测性（data/source_report.py，新增）**：
- `generate_source_report(source_health, output_dir)`：导出源健康 JSON 报告
  （时间戳 + 摘要：总源数/熔断数/平均健康分 + 各源：成功/失败/连续失败/健康分/is_open/平均耗时）
- CLI：`python data/source_report.py`（从真实 MarketDataClient 生成）或 `--stats-json`

**④ 并发与同步优化（sync_all_market.py 增强）**：
- **断点续传**：`--checkpoint` 或 config `sync.checkpoint_file`；JSON 记录已完成股票代码，
  中断后重新运行自动跳过（原子写入 .tmp + os.replace 防损坏）；全部完成时直接跳过
- **进度条**：tqdm（`--no-progress` 关闭，tqdm 未安装自动降级日志进度）
- **配置化线程**：config `sync.threads`（tdx_local=8 / akshare=4 / baostock=1——
  baostock 全局单 socket 必须串行），`--threads` 可覆盖
- 配置（config.yaml sync 段）：threads / batch_size / checkpoint_file

**⑤ 单元测试（tests/，新增，unittest 标准库）**：
- `test_path_utils.py`：环境变量覆盖/配置兜底/默认兜底/相对转绝对
- `test_resampler.py`：min_bars 边界/keep_latest 豁免/日历过滤（周末剔除）/
  日历落后增量（最新交易日保留）/月K聚合/空输入
- `test_incremental.py`：增量幂等/尾部读取/价格解析/扁平结构兼容/市场判定
- `test_trim_kline.py`：循环覆盖（120→100）/中文列 upsert/get_last_date/交易日历
- `test_fallback.py`：健康熔断/恢复/空数据不误熔断/排序/disable + 主源失败切换回归
- 运行：`python -m unittest discover -s tests`（32/32 通过）

**⑥ 重采样日历过滤再升级**（kline_resampler.py）：
- 规则细化：保留"日历中日期 ∪ 日历最大日期之后的工作日"（pandas 3.0 用 `dt.dayofweek`），
  无日历时仅剔除周末——既支持增量最新交易日，也剔除混入的周末数据

**⑧ 换手率完整性修复（数据质量，3z 资金维度依赖换手率）**：
- 问题：.day 文件无换手率字段；历史 sync 走 tdx_local 写入的缓存存在大量 `turn IS NULL` 行
  （全库 16万行/718只，config 18只中 8 只全 None）→ 分析退化：换手率 0.00%、
  筹码集中度未知、自适应周期 N=30 退化、三振资金维度失效
- 四层防御：
  1. `tdx_local_client.get_daily_data`：本地数据换手率全 None → 从 db 缓存按日期补齐 + ffill
  2. `data_engine.get_kline`：upsert 前 turn ffill（防未来污染）
  3. `_fetch_with_incremental`：缓存换手率全 None（脏锚点，无法 ffill）→ 回退在线源
  4. `_fetch_with_fallback`：tdx_local 返回换手率全 None → 视为无效，切换 akshare/baostock
- 存量修复：在线源重写脏缓存（验证 8/8 修复，600519 换手率 0.24%/筹码集中度高度集中）

**⑦ 全市场同步性能优化（实战提速 1.9小时 → ~12分钟）**：
- **根因修复**：sync_all_market 原来 `MysteryDataEngine()` 未传 config → 无 market_client →
  纯 baostock 单源网络拉取（每只1-3秒）。改为 `MysteryDataEngine(config=cfg)` 启用
  tdx_local 双源退避 + 增量路径（本地毫秒级）
- **协议客户端延迟初始化**（tdx_local_client）：mootdx Quotes.factory 连接不可达行情服务器
  时 TCP 超时 15s+，阻塞 MarketDataClient 构造（每次同步 16s 固定开销）→ 首次真正需要时才
  连接，失败一次本会话禁用（_protocol_disabled）
- **证券列表缓存跳过**（get_all_a_shares）：本地已有 ≥1000 只时跳过 query_stock_basic
  全市场网络拉取（省 30s+）
- **增量写入只写变化行**（data_engine 双源分支）：date 不在缓存中的增量行才 upsert，
  避免"增量0条全量重写数百行/增量1条重写全部"（全市场同步最大开销）
- **.day 二分定位**（tdx_incremental）：定长 32 字节记录按日期升序 → 二分定位 last_date
  之后起始位置，增量场景只解析尾部几条（不再全量遍历 6000+ 条）；去掉 datetime.strptime
- **无缓存写前截断**（data_engine）：全量写入前 tail(max_rows)，避免写 6000 行再 trim 删 4000
- **trim 快速路径**（db_manager）：COUNT ≤ max_rows 直接返回，避免每次同步执行大 DELETE 解析
- **logging force=True**（sync_all_market）：覆盖其他模块 import 时的 root handler 配置，
  保证 INFO 进度/数据源日志可见
- 实测：单只增量 0.02-0.13s；500 只 65s；1000 只 144s（8线程）→ 全量 5208 只约 12 分钟
  （首次建缓存）；每日增量同步（缓存已有）更快
- 线程策略：主源 tdx_local 本地读取可 8 线程（sync.threads.tdx_local=8）；baostock 兜底
  有全局锁保护（sync.threads.baostock=1）；实测 1/8 线程差异不大（受 SQLite 锁/GIL 限制）

### 4.10 Web 前端界面（docs/ui.md，Streamlit 多页面）— ★★

**技术选型**：Streamlit 1.61 + Plotly 6.9（纯 Python，复用现有分析引擎，无 JS）。

**目录结构**（web/）：
- `web/app.py`：主入口（侧边栏导航 + 项目说明）
- `web/pages/1_📈_个股分析.py`：个股深度分析（核心）
- `web/pages/2_📊_板块监控.py`：板块强度排名 + 成分股
- `web/pages/3_🔍_全市场扫描.py`：参数化扫描 + 进度条 + 结果表格
- `web/pages/4_💎_真三振池.py`：扫描结果池 + 自选股管理
- `web/pages/5_⚙️_系统状态.py`：数据源健康/缓存信息/源健康报告
- `web/components/`：kline_chart（蜡烛图+均线+成交量副图）/ score_card（st.metric 卡片）/
  stock_table（真三振高亮 + CSV 导出）
- `web/utils/session.py`：会话状态 + 后端单例（DataFeeder/MysteryLogic）+ 扫描结果/自选股 JSON 持久化

**后端对接**：
- `DataFeeder(config)`（传 config 启用多源退避+缓存，否则单源 baostock 慢——已修复）
  - get_daily（附 MA5-250）/ get_weekly（附 MA60_W）/ get_market_index / get_industry_data
    （行业分类：多源客户端 → db stock_industry_info 兜底）
- `MysteryLogic.comprehensive_signal_analysis`（三大心法 + 四维共振综合信号）
- 个股页输出：评分卡片（综合评分/真三振/主升浪/资金活跃）+ 三大心法状态卡片 +
  操作建议 + 交互式K线（跳过周末）+ 分析详情 + 最近20日数据 + CSV 导出

**运行**：`streamlit run web/app.py --server.port 1888 --server.headless true`
（systemd 部署示例见 scripts/mystery-web.service）

**验证**：AppTest 6/6 页面渲染 + 个股分析按钮点击完整链路（8 metric + K线图 +
"分析完成"提示）；HTTP 200 实测启动成功

### 4.10.1 Web 前端升级（docs/ui2.md）— ★★

**① 个股分析升级**：
- **模糊搜索**：streamlit-searchbox（开源组件），匹配代码/名称（`DataFeeder.get_all_stock_code_name`
  从 db stock_industry_info 加载 5208 只代码-名称字典），返回 "sh600150 - 中国船舶" 格式
- **Excel 对齐展示**：自适应平台（POC/上轨/下轨）+ 平台箱体（震荡区间）+
  筹码分析（集中度/趋势）+ 主升浪8项指标对比表（✅/❌）+ 周/月K箱体（重采样后近N周期高低）
- **财务数据**：FinancialStorage.load_latest → PE/PB/股息率/最新ROE 四卡片 +
  近三年 ROE 历史表（load_history）
- **K线图 v2**（kline_chart.py 重写）：3 行子图（蜡烛+MA+震荡区间矩形 /
  成交量 / MACD 三线），日/周/月周期切换（kline_resampler 重采样），
  震荡区间上沿/下沿/POC 以矩形+虚线绘制

**② 分析结果缓存（mystery_analysis_cache 表）**：
- 建表：`(stock_code, period, last_trade_date, report_json, created_at)` 联合主键
- MysteryDB.get_analysis_cache / set_analysis_cache（JSON 序列化，INSERT OR REPLACE）
- 个股分析：以 (code, 'daily', 最新K线日期) 为键，行情未更新直接复用（页面显示
  "⚡ 命中分析缓存"）
- 全量扫描：以 ('__all__', 'full_scan', 当日日期) 为键，当日重复扫描直接复用

**③ 板块监控升级**：
- 板块得分 = MA20偏离×0.4 + 近10日涨幅×0.3 + 成交额放大倍数×0.3
- Top15 横向条形图（Plotly Express）+ 全量排名表 + CSV 导出
- 成分股钻取：对板块成分股逐一 comprehensive_signal_analysis，
  真三振/评分≥85 龙头高亮 + 一键查看

**④ 股票池配置**：
- 全局股票池选择器（全市场A股 / 核心自选池 / 自定义），扫描页复用
- 真三振池页模糊搜索添加自选股（streamlit-searchbox），watchlist.json 持久化

**验证**：AppTest 6/6 渲染 + 缓存读写 5 项断言 + K线 v2（10 trace/MACD三线/4 shape）+
代码-名称字典（5208 只）——17/17 通过

### 4.10.2 Web UI 修复（用户反馈，v1.13.1）— ★★

**① 财务数据 NA 修复**：
- 根因1：`FinancialStorage.ensure_financial` 内 MultiSourceClient 未 login → baostock
  接口缺 user_id 上下文 → 返回全 None dict（被 `if not data` 放行并缓存）
- 根因2：PE/PB/股息率 计算依赖 `current_price`（get_financial_data 第二参数，main.py
  从日K最新收盘取）——ensure 未传 → 全 None
- 根因3：修复前存入的半脏缓存（ROE/EPS 有值但 PE/PB None）被"报告期有值即有效"
  判定命中 → 永不刷新 → 清空 stock_financial_data 全表重填（18 只，17 只有 PE）
- 修复后：600150 报告期 2026-03-31 / ROE 3.30% / PE 22.24 / PB 0.73 / 股息率 0.75%

**② 行业板块数据（baostock 翻页兼容，pandas 3.0）**：
- 根因：baostock 0.9.3 `rs.get_data()` 翻页用 `df.append()`（pandas 3.0 已移除）→
  query_stock_industry（5206 行=3 页）崩溃；且 `rs.next()` 在 cur_row_num 未消费时
  恒返回 True → 死循环
- 修复：`get_industry_data` 手动翻页（`cur_row_num=len(data)` 消费后 next()，页数上限8）+
  pd.concat 拼接；翻页前确保 login（user_id 上下文）
- `DataFeeder.get_industry_data`：优先 db 缓存 → 在线源拉取并 `update_industries` 自动
  填充 db（83 行业 / 5206 只，证监会行业分类——本机无通达信行业文件时的可行替代）；
  MarketDataClient 无行业接口，须用 MultiSourceClient
- 效果：板块监控（之前为空）、扫描指定板块、个股所属板块全部可用

**③ 页面修复（5 处）**：
- 个股分析：显示所属板块；财务用 ensure_financial（无缓存自动拉取+缓存）；
  一次分析完成日/周/月K（三个 tab，各含 K 线 + 箱体 + 最新价）
- 全市场扫描：支持指定板块筛选（行业板块下拉，按通达信/证监会行业分类）；
  扫描结果显示行业板块列（_run_scan 加'行业板块'字段）
- 板块监控：行业数据修复后自然有数据（83 板块强度排名 + 得分）
- 真三振池：自选股列表显示"代码 - 名称"（get_all_stock_code_name）
- stock_table：增加行业板块列

**验证**：21/21（行业填充/config 18 只全有板块/财务 PE-PB-股息率/6 页渲染/
板块强度 83 个/自选股名称）

### 4.11 数据层"本地优先+过期回退"（docs/tdx2.md）— ★★

**目标**：本地数据新鲜则零网络；过期/缺失自动回退 akshare → baostock。最小改动贴合现有框架。

**路径规则（tdx_path_resolver.py 新建）**：
- `resolve_home()`：TDX_HOME env > config tdx.home_dir > 默认 /mnt/bigdata/tdx/files/new_tdx
- `resolve_vipdoc_for_kline()`：**{home}/vipdoc（含lday）> 显式 vipdoc_dir（含lday）>
  TDX_VIPDOC_DIR > 默认**——本机为 vipdoc/{sh,sz,bj}/lday 独立结构，走第二优先级
- `resolve_vipdoc_for_fin()`：仅 TDX_VIPDOC_DIR（env > config > 默认）——**财务绝不读 TDX_HOME**
- 优先级细节：**env 覆盖 config**（tdx2 验收用例）
- 板块：仅 {home}/T0002/blocknew、hq_cache（本机无 TDX_HOME → 空，由 db 行业分类兜底）

**新鲜度判定**：
- 日K：`.day` 文件末根K线日期（读尾部 32 字节定长记录）距今 ≤ max_age_days+2（周末缓冲）
  → 新鲜；文件缺失/超期 → 过期 → 协议补充 → 失败回退在线源
- 财务：最新 gpcw 报告期（扫描 {fin_dir} 与 {fin_dir}/cw/）在 max_age_days+45（季报滞后）内
  或包 mtime 新鲜；无包 → 过期 → 在线源
- 配置：config tdx.freshness（kline 1 / block 3 / financial 30 天）

**tdx_local_client.py 改动**：
- __init__：日K目录用 resolve_vipdoc_for_kline（self.vipdoc_dir），财务用
  resolve_vipdoc_for_fin（self.fin_dir，mootdx Financial 与 gpcw 探测均只读 fin_dir）
- get_daily_data：入口加 `is_kline_fresh(day_file)` 检查——过期打
  `[TDX本地-过期→fallback]` 日志后走协议补充（失败返回 None → 上层 akshare/baostock）
- get_financial_data：`is_financial_fresh(fin_dir)` 不新鲜直接返回空（在线源兜底）
- get_block_data（新增）：TDX_HOME/T0002/*.blk 解析（市场#代码格式，gbk 编码），
  无 home 返回空
- multi_source 无需改动（tdx_local 返回 None/空 → 原 fallback 链自然生效，日志在源头）

**单测**：tests/test_tdx_path_resolver.py 10 项（新鲜/过期/周末缓冲/文件缺失/
home优先/lday结构/财务隔离/财务新鲜/路径结构）——套件 56/56 通过

**⑧ 分析卡顿修复（指数获取优化，用户反馈"正在分析...一直没有结果"）**：
- **根因**：get_market_index 每次分析都拉 3 个指数（sh.000001/sz.399001/sz.399006）
  ——tdx_local 对指数代码无 .day → 协议客户端连行情服务器（TCP 15s+ 超时）× 重试3次
  + akshare 退避（2+4+8s）→ 每指数 20-30s，3 个指数 90s+ → UI 卡死
- **修复1**：tdx_local.get_daily_data 指数快速失败——sh.000xxx/sz.399xxx 无本地 .day
  直接返回空走在线源（跳过协议重试），日志 `[TDX本地-指数无本地数据→fallback]`
- **修复2**：DataFeeder.get_market_index db 缓存（指数日K upsert 至 stock_kline_data，
  最新日期 3 天内直接复用 → 二次读取 0.11s，首次 25s 写缓存）
- **修复3**：页面1 market_data 会话缓存（st.session_state，一次分析后复用）
- **实测**：600000 全链路（日K/周K/指数/信号/财务/板块/缓存）10/10 通过，
  指数缓存 0.11s；分析全缓存秒级返回

## 5. 接口设计

### 5.1 用户接口

#### 5.1.1 命令行接口（真实）
```bash
# 单只股票分析（文件名含股票名称，如 股票分析报告_中国船舶_xxx）
/home/ai/ai_runner/venv/bin/python run_analysis.py --mode single --stock sh600150

# 每日分析（config 中 18 只股票，文件名加"每日"前缀）
/home/ai/ai_runner/venv/bin/python run_analysis.py --mode daily

# 指定配置文件
/home/ai/ai_runner/venv/bin/python run_analysis.py --mode daily --config config/config.yaml

# 系统测试
/home/ai/ai_runner/venv/bin/python run_analysis.py --test

# 快捷脚本（激活 venv 后运行每日分析）
bash daily.sh
```

> 注意：必须使用 `/home/ai/ai_runner/venv/bin/python`（系统 python3 缺少 baostock/pandas 依赖）。

#### 5.1.2 编程接口（真实）
```python
from main import StockAnalysisSystem

# 创建分析系统
system = StockAnalysisSystem('config/config.yaml')

# 分析多只股票（返回 analysis_results/stock_data/summary/recommendations）
results = system.analyze_stocks(['sh600150', 'sz000001'])

# 单只股票分析（生成报告+git同步）
system.analyze_single_stock('sh600150')

# 每日分析（config 股票列表，自动 git 同步远端）
system.run_daily_analysis()
```

### 5.2 内部接口

#### 5.2.1 数据获取接口
```python
class BaostockClient:
    def get_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame
    def get_indicators_data(self, stock_code: str, indicator_list: list) -> pd.DataFrame
    def get_industry_data(self, industry_code: str) -> pd.DataFrame
```

#### 5.2.2 分析引擎接口
```python
class AnalysisEngine:
    def calculate_technical_indicators(self, data: pd.DataFrame) -> dict
    def apply_mystery_theory(self, data: pd.DataFrame) -> dict
    def recognize_patterns(self, data: pd.DataFrame) -> dict
    def generate_investment_advice(self, analysis_result: dict) -> dict
```

## 6. 错误处理设计

### 6.1 异常类型
- **数据获取异常**: 网络连接失败、API限制、数据格式错误
- **计算异常**: 数据不足、参数错误、算法失败
- **输出异常**: 文件写入失败、模板错误、格式转换失败
- **配置异常**: 配置文件错误、参数缺失

### 6.2 错误处理策略
- **重试机制**: 对于网络请求等临时性错误
- **降级处理**: 对于非关键功能失败
- **日志记录**: 详细记录错误信息
- **用户提示**: 友好的错误提示信息

### 6.3 异常处理示例
```python
class ExceptionHandler:
    def handle_data_fetch_error(self, error: Exception, context: str):
        """处理数据获取错误"""
        if isinstance(error, ConnectionError):
            self.retry_with_backoff(context)
        elif isinstance(error, TimeoutError):
            self.reduce_timeout_and_retry(context)
        else:
            self.log_error(f"数据获取失败: {error}", context)
    
    def handle_calculation_error(self, error: Exception, context: str):
        """处理计算错误"""
        if isinstance(error, ValueError):
            self.validate_input_data(context)
        elif isinstance(error, ZeroDivisionError):
            self.handle_zero_division(context)
        else:
            self.log_error(f"计算失败: {error}", context)
```

## 7. 性能设计

### 7.1 性能优化策略
- **数据缓存**: 缓存常用数据和计算结果
- **并行计算**: 多线程处理多只股票
- **算法优化**: 优化核心算法的计算复杂度
- **内存管理**: 合理使用内存，避免内存泄漏

### 7.2 性能监控
- **执行时间**: 记录各模块执行时间
- **内存使用**: 监控内存使用情况
- **网络延迟**: 监控数据获取延迟
- **错误率**: 统计错误发生频率

## 8. 扩展性设计

### 8.1 模块化设计
- **松耦合**: 各模块之间通过接口通信
- **高内聚**: 每个模块专注于特定功能
- **可插拔**: 支持模块的动态加载和卸载

### 8.2 配置驱动
- **参数化**: 通过配置文件控制系统行为
- **环境隔离**: 支持不同环境的配置
- **动态更新**: 支持运行时配置更新

### 8.3 扩展点设计
- **新的数据源**: 支持添加新的数据提供商
- **新的技术指标**: 支持添加新的技术指标
- **新的分析算法**: 支持添加新的分析算法
- **新的输出格式**: 支持添加新的输出格式

## 9. 部署设计

### 9.1 系统要求（真实环境）
- **Python版本**: 3.12（venv: /home/ai/ai_runner/venv）
- **依赖库**: baostock 0.9.3, pandas 3.0.5, numpy 2.5.1, openpyxl 3.1.5, PyYAML 6.0.3
- **网络**: baostock 数据服务（行情）+ github.com:443（SSH，22端口被屏蔽）
- **存储**: 输出目录 /home/ai/ai_runner/stock/output（git 仓库，远端 misteryresult）

### 9.2 部署步骤（真实）
1. **环境准备**: 使用现有 venv（`/home/ai/ai_runner/venv`），依赖已装齐
2. **配置部署**: `config/config.yaml`（股票列表18只、output_dir）
3. **输出仓库**: `/home/ai/ai_runner/stock/output` 为独立 git 仓库，
   远端 `ssh://git@ssh.github.com:443/zengjuly/misteryresult.git`（SSH over 443）
4. **测试验证**: `/home/ai/ai_runner/venv/bin/python run_analysis.py --test`
5. **正式运行**: 单股 `--mode single --stock sh600150`；每日 `--mode daily`

### 9.3 运行维护（真实）
- **自动同步**: 每次生成报告后自动 git add/commit/push（`_sync_output_to_git`），
  输出目录与远端保持同步
- **SSH 通道**: github.com:22 被网络屏蔽，remote 使用 443 端口
  （`ssh://git@ssh.github.com:443/...`）；如需全局生效可在 `~/.ssh/config` 配置
- **定时任务**: Hermes cron 任务"股票每日分析"（job_id: 1d056599e065），
  周一至五 15:30 自动运行 `run_analysis.py --mode daily`，
  可用 `cronjob action='run'` 手动触发，`cronjob action='list'` 查看状态
- **日志监控**: logs/stock_analysis.log（INFO 级别）
- **数据更新**: 每日定时任务自动获取最新行情
- **版本升级**: git 管理源码（stock_analyzer）+ 结果（output）双仓库

## 10. 测试设计

### 10.1 测试策略
- **单元测试**: 测试各个模块的功能
- **集成测试**: 测试模块之间的交互
- **系统测试**: 测试整个系统的功能
- **性能测试**: 测试系统的性能指标

### 10.2 测试用例
- **数据获取测试**: 测试数据获取功能
- **指标计算测试**: 测试技术指标计算
- **分析算法测试**: 测试分析算法准确性
- **输出生成测试**: 测试报告生成功能

### 10.3 测试数据
- **历史数据**: 使用历史股票数据
- **测试集**: 准备标准测试数据集
- **边界数据**: 准备边界条件测试数据

## 11. 文档设计

### 11.1 文档类型
- **用户文档**: 用户使用指南
- **开发文档**: 开发者指南
- **API文档**: 接口文档
- **部署文档**: 部署指南

### 11.2 文档内容
- **功能说明**: 详细的功能说明
- **使用示例**: 具体的使用示例
- **配置说明**: 配置参数说明
- **故障排除**: 常见问题解决方案

## 12. 版本管理

### 12.1 版本控制（真实）
- **源码仓库**: `/home/ai/ai_runner/stock/stock_analyzer`（git，分支 main）
- **结果仓库**: `/home/ai/ai_runner/stock/output`（git，远端 `ssh://git@ssh.github.com:443/zengjuly/misteryresult.git`）
- **提交规范**: 源码用 feat:/fix:/docs:/chore: 前缀；结果仓库自动提交"📊 股票分析报告更新 {时间戳}"
- **版本号**: 设计文档版本 1.1.0（随系统迭代更新）

### 12.2 发布流程
- **代码审查**: 代码审查和测试
- **版本打包**: 打包发布版本
- **文档更新**: 更新相关文档
- **发布通知**: 发布通知和公告

## 13. 总结

本系统设计文档详细描述了 Mystery 趋势交易分析系统的架构设计、核心算法（含非标准指标精确计算方法）、接口设计、错误处理、性能优化、扩展性设计、部署设计、测试设计和文档设计等内容。

通过模块化设计、接口标准化、错误处理完善、性能优化、扩展性考虑等设计策略，确保了系统的可靠性、可维护性、可扩展性和高性能。

**系统当前能力**：
- 三振共振（个股+行业+大盘真实数据）判断
- 自适应 VAP-ATR 平台中枢（POC 筹码控制点 + 波动率自适应通道，A股涨跌停修正）
- 自适应检测周期（换手率驱动: N=70%/日均换手, 双周期嵌套快ATR窗口, k自适应）
- 多周期箱体分析（周线/月线上下沿，识别突破上沿/回踩上沿/跌到下沿/跌破下沿）
- 主升浪状态判定（带判定依据）+ 主升浪8项指标对比表
- 多周期（日/周/月线）共振分析
- 基本面数据（ROE/EPS/PE/PB/股息率）+ 板块评级
- 报告自动生成（Excel/HTML/文本/仪表板）+ git 自动同步远端
- 每日定时任务（周一至五 15:30）自动分析
- **数据中枢**（SQLite缓存 + Cache-Aside数据引擎 + 全量多线程同步 + 全市场扫描信号捕获）
- **多源退避**（通达信本地主源 + AKShare + baostock 三级退避 + 日K重采样周/月K对齐）
- **通达信本地数据**（mootdx 解析官方数据包，离线毫秒级读取，K线循环覆盖控制存储）

后续开发人员可以基于此文档进行系统开发、维护和扩展，确保项目的顺利进行和持续发展。