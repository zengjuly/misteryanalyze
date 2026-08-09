# Mystery趋势交易分析系统 - 系统设计文档

## 文档信息

- **项目名称**: Mystery趋势交易分析系统
- **版本**: 1.0.0
- **创建日期**: 2026-08-09
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
- **数据获取**: 基于 baostock 的股票数据获取
- **技术指标**: 均线、趋势、动能指标计算
- **Mystery理论**: 三振共振、主升浪识别、形态识别
- **智能分析**: 综合评分系统、投资建议
- **多格式输出**: Excel、HTML、文本报告

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

**核心接口**:
```python
class BaostockClient:
    def login() -> bool
    def get_stock_data(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame
    def get_indicators_data(stock_code: str, indicator_list: list) -> pd.DataFrame
    def logout() -> None

class DataProcessor:
    def clean_data(df: pd.DataFrame) -> pd.DataFrame
    def calculate_basic_indicators(df: pd.DataFrame) -> pd.DataFrame
    def normalize_data(df: pd.DataFrame) -> pd.DataFrame
```

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
- `mystery_logic.py`: Mystery 理论核心逻辑
- `resonance_analyzer.py`: 三振共振分析
- `pattern_recognition.py`: 形态识别
- `__init__.py`: 模块初始化

**核心接口**:
```python
class MysteryLogic:
    def identify_main_wave(data: pd.DataFrame) -> dict
    def identify_platform_breakout(data: pd.DataFrame) -> dict
    def identify_air_refuel(data: pd.DataFrame) -> dict

class ResonanceAnalyzer:
    def analyze_market_resonance(stock_data: dict) -> dict
    def analyze_industry_resonance(stock_data: dict) -> dict
    def calculate_resonance_score(resonance_data: dict) -> float

class PatternRecognition:
    def identify_head_shoulder(data: pd.DataFrame) -> dict
    def identify_double_top(data: pd.DataFrame) -> dict
    def identify_triangle(data: pd.DataFrame) -> dict
```

#### 2.2.4 输出模块 (`output/`)
**职责**: 生成各种格式的分析报告
- `excel_generator.py`: Excel 报告生成
- `html_generator.py`: HTML 报告生成
- `__init__.py`: 模块初始化

**核心接口**:
```python
class ExcelGenerator:
    def generate_report(analysis_results: dict, output_path: str) -> bool
    def create_summary_sheet(df: pd.DataFrame) -> None
    def create_indicators_sheet(df: pd.DataFrame) -> None
    def create_analysis_sheet(analysis_data: dict) -> None

class HTMLGenerator:
    def generate_report(analysis_results: dict, output_path: str) -> bool
    def create_summary_section(analysis_data: dict) -> str
    def create_indicators_section(df: pd.DataFrame) -> str
    def create_analysis_section(analysis_data: dict) -> str
```

#### 2.2.5 配置模块 (`config/`)
**职责**: 系统配置管理
- `config.yaml`: 主配置文件
- `__init__.py`: 配置加载

**配置结构**:
```yaml
# 数据源配置
data_source:
  provider: "baostock"
  timeout: 30
  retry_count: 3

# 技术指标参数
indicators:
  ma_periods: [5, 10, 20, 60, 250]
  macd_params: {fast: 12, slow: 26, signal: 9}
  rsi_period: 14
  kdj_period: 9

# 分析参数
analysis:
  resonance_threshold: 0.7
  breakout_volume_threshold: 1.5
  main_wave_ma_period: 5

# 输出配置
output:
  formats: ["excel", "html", "text"]
  output_dir: "output"
  template_dir: "templates"
```

#### 2.2.6 工具模块 (`utils/`)
**职责**: 提供通用工具函数
- `exception_handler.py`: 异常处理系统
- `__init__.py`: 工具函数

**核心接口**:
```python
class ExceptionHandler:
    def handle_exception(e: Exception, context: str) -> None
    def log_error(message: str, level: str = "ERROR") -> None
    def log_info(message: str) -> None
    def log_warning(message: str) -> None
```

## 3. 核心算法设计

### 3.1 Mystery 理论算法

#### 3.1.1 主升浪识别算法
```python
def identify_main_wave(data: pd.DataFrame) -> dict:
    """
    识别主升浪形态
    1. MA5趋势向上
    2. 股价在MA5之上
    3. 成交量放大
    4. MACD金叉
    """
    ma5 = ma(data['close'], 5)
    trend_up = ma5.diff() > 0
    above_ma5 = data['close'] > ma5
    volume_increase = data['volume'] > data['volume'].rolling(5).mean()
    macd_signal = check_macd_golden_cross(data)
    
    main_wave = trend_up & above_ma5 & volume_increase & macd_signal
    
    return {
        'is_main_wave': main_wave.iloc[-1],
        'confidence': calculate_confidence([trend_up, above_ma5, volume_increase, macd_signal]),
        'details': {
            'ma5_trend': 'up' if trend_up.iloc[-1] else 'down',
            'price_position': 'above' if above_ma5.iloc[-1] else 'below',
            'volume_status': 'high' if volume_increase.iloc[-1] else 'normal',
            'macd_status': 'golden_cross' if macd_signal else 'no_cross'
        }
    }
```

#### 3.1.2 三振共振分析算法
```python
def analyze_market_resonance(stock_data: dict) -> dict:
    """
    分析大盘、行业、个股的三振共振
    1. 大盘趋势分析
    2. 行业趋势分析
    3. 个股趋势分析
    4. 共振强度计算
    """
    market_trend = analyze_market_trend(stock_data['market'])
    industry_trend = analyze_industry_trend(stock_data['industry'])
    stock_trend = analyze_stock_trend(stock_data['stock'])
    
    # 计算共振强度
    resonance_score = calculate_resonance_score([
        market_trend['strength'],
        industry_trend['strength'],
        stock_trend['strength']
    ])
    
    return {
        'resonance_score': resonance_score,
        'market_trend': market_trend,
        'industry_trend': industry_trend,
        'stock_trend': stock_trend,
        'resonance_level': get_resonance_level(resonance_score)
    }
```

### 3.2 形态识别算法

#### 3.2.1 头肩顶形态识别
```python
def identify_head_shoulder(data: pd.DataFrame) -> dict:
    """
    识别头肩顶形态
    1. 左肩：局部高点
    2. 头：更高的高点
    3. 右肩：较低的高点
    4. 颈线：连接左右肩低点
    """
    # 寻找局部极值点
    highs = find_local_highs(data['high'])
    lows = find_local_lows(data['low'])
    
    # 识别头肩顶模式
    pattern = detect_head_shoulder_pattern(highs, lows)
    
    return {
        'pattern_detected': pattern['found'],
        'pattern_type': 'head_shoulder_top',
        'left_shoulder': pattern['left_shoulder'],
        'head': pattern['head'],
        'right_shoulder': pattern['right_shoulder'],
        'neckline': pattern['neckline'],
        'breakout_point': pattern['breakout_point'],
        'confidence': pattern['confidence']
    }
```

## 4. 数据流设计

### 4.1 数据获取流程
```
用户输入股票代码 → 登录baostock → 获取历史数据 → 数据预处理 → 
技术指标计算 → Mystery理论分析 → 形态识别 → 综合评分 → 
生成报告 → 输出结果
```

### 4.2 数据处理流程
```
原始数据 → 数据清洗 → 缺失值处理 → 异常值处理 → 
标准化处理 → 技术指标计算 → 特征提取 → 分析结果
```

### 4.3 输出流程
```
分析结果 → 模板渲染 → 格式转换 → 文件生成 → 
质量检查 → 最终输出
```

## 5. 接口设计

### 5.1 用户接口

#### 5.1.1 命令行接口
```bash
# 单只股票分析
python3 run_analysis.py --mode single --stock sh600000

# 多只股票分析
python3 run_analysis.py --mode batch --stocks sh600000,sz000001

# 每日分析
python3 run_analysis.py --mode daily

# 系统测试
python3 run_analysis.py --test

# 配置管理
python3 run_analysis.py --config config/custom.yaml
```

#### 5.1.2 编程接口
```python
from main import StockAnalysisSystem

# 创建分析系统
system = StockAnalysisSystem()

# 分析单只股票
result = system.analyze_stock('sh600000')

# 分析多只股票
results = system.analyze_stocks(['sh600000', 'sz000001'])

# 生成报告
system.generate_report(result, 'output/report.xlsx')
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

### 9.1 系统要求
- **Python版本**: 3.8+
- **依赖库**: pandas, numpy, baostock, openpyxl, pyyaml
- **内存**: 最小 512MB，推荐 2GB+
- **存储**: 最小 1GB，推荐 10GB+

### 9.2 部署步骤
1. **环境准备**: 安装 Python 和依赖库
2. **配置部署**: 配置系统参数
3. **数据准备**: 准备必要的数据文件
4. **测试验证**: 运行系统测试
5. **正式运行**: 启动系统服务

### 9.3 运行维护
- **日志监控**: 监控系统运行日志
- **性能监控**: 监控系统性能指标
- **数据更新**: 定期更新股票数据
- **版本升级**: 定期升级系统版本

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

### 12.1 版本控制
- **Git管理**: 使用 Git 进行版本控制
- **分支策略**: 采用 Git Flow 分支策略
- **版本号**: 遵循语义化版本号

### 12.2 发布流程
- **代码审查**: 代码审查和测试
- **版本打包**: 打包发布版本
- **文档更新**: 更新相关文档
- **发布通知**: 发布通知和公告

## 13. 总结

本系统设计文档详细描述了 Mystery 趋势交易分析系统的架构设计、核心算法、接口设计、错误处理、性能优化、扩展性设计、部署设计、测试设计和文档设计等内容。

通过模块化设计、接口标准化、错误处理完善、性能优化、扩展性考虑等设计策略，确保了系统的可靠性、可维护性、可扩展性和高性能。

后续开发人员可以基于此文档进行系统开发、维护和扩展，确保项目的顺利进行和持续发展。