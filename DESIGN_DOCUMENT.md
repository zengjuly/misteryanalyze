# Mystery趋势交易分析系统 - 系统设计文档

## 文档信息

- **项目名称**: Mystery趋势交易分析系统
- **版本**: 1.3.0
- **创建日期**: 2026-08-09
- **更新日期**: 2026-08-12
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
- `baostock_client.py`: baostock 数据获取客户端
- `data_processor.py`: 数据预处理和清洗
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

### 3.3 三振共振分析（three_resonance_analysis）— 个股+行业+大盘

三振共振 = 个股趋势 ∧ 行业趋势 ∧ 大盘趋势，三者同时向上才成立。

**① 个股趋势**（满足任一即 True）：
- `均线排列 == 1`（多头排列）
- 或 `收盘价 > MA20`（股价站上20日线）

**② 行业趋势**（由 main.py `_analyze_industry_trend` 外部计算，非本方法内部）：
- 从行业分类表取同行业股票（排除自身，最多抽样 3 只）
- 对每只样本取**近 5 个交易日涨跌幅**均值，再对样本取平均得 `avg_pct`
- `行业趋势 = avg_pct > 0`
- 附带板块评级（见 3.9）

**③ 大盘趋势**：
- 取上证指数（或首个可用指数）日线，计算 `MA20`（若缺失则 rolling(20).mean() 现算）
- `大盘趋势 = 指数收盘价 > 指数MA20`

**④ 三级共振**：`个股 ∧ 行业 ∧ 大盘` 全部为 True。

返回：`{个股趋势, 行业趋势, 大盘趋势, 三级共振, 详情}`

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

**④ 输出**：`周线箱体/月线箱体 = {周期, 上沿, 下沿, 当前价, 位置, 状态, 距上沿%, 距下沿%, 详情}`，
汇总为 `多周期箱体状态 = "周线:突破上沿(35.6) | 月线:回踩上沿(32.1)"`

平台突破分析（`platform_breakthrough_analysis`）新增参数 `weekly_data`/`monthly_data`，
在自适应平台与固定箱体之后进行多周期箱体分析，随报告展示。

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

后续开发人员可以基于此文档进行系统开发、维护和扩展，确保项目的顺利进行和持续发展。