# 完整 Hermes 开发方案：Mystery 趋势交易系统核心分析模块重构

## 1. 方案目标

基于 misteryanalyze 现有工业级数据层（多源退避、本地通达信优先、增量更新、健康熔断、日K重采样周/月K、2000条循环覆盖），对核心分析模块进行生产级重构，使其严格量化《Mistery趋势交易论》的三大心法：

- **日线多头基础滤网**：股价与 MA5/10/20/60 全部运行在 MA250 年线之上。
- **周线方向锚定**：周线稳定在 60 周线之上，斜率不向下。
- **破五反五容错**：允许跌破 MA5，但 2 个交易日内收回且 MA20 斜率向上。

同时完整保留并增强既有的四维三振共振评分（个股30 + 大盘25 + 行业25 + 资金20）。最终输出可操作信号（真三振、主升浪、综合评分、买卖建议），并与仓位管理、防守红线闭环。

## 2. 系统架构总览

```
数据层 (已完成集成)
├── tdx_local    (主源，本地.day文件，增量更新)
├── akshare      (备用源1)
├── baostock     (备用源2)
├── 健康评分与熔断
├── 日K重采样 → 周K/月K
└── SQLite缓存 (stock_kline_data, 2000条限制)

        ▼ 提供清洗后的DataFrame

分析模块 (本次重构)
├── analysis/resonance_analyzer.py   # 三振共振评分
├── analysis/mystery_logic.py        # 综合逻辑（年线、周线、破五反五、主升浪）
└── utils/data_feeder.py             # 数据接入适配器

        ▼ 输出信号字典

策略执行层
├── main.py 扫描入口
├── 仓位管理
└── 防守红线执行
```

## 3. 文件清单与实施步骤

| 文件 | 操作 | 说明 |
|------|------|------|
| `analysis/resonance_analyzer.py` | 替换 | 最终确认版四维共振评分 |
| `analysis/mystery_logic.py` | 替换 | 新增年线滤网、周线锚定、破五反五、主升浪 |
| `utils/data_feeder.py` | 新增 | 统一数据获取，适配多源客户端 |
| `main.py` 或新增扫描脚本 | 修改 | 调用分析模块，输出信号报告 |
| `config/config.yaml` | 修改 | 增加 `analysis` 配置段 |
| `tests/test_mystery_logic.py` | 新增 | 单元测试覆盖核心逻辑 |
| `backtest/three_strike_mainwave_backtest.py` | 新增 | 回测框架（可选） |

## 4. 分析模块详细设计

### 4.1 `analysis/resonance_analyzer.py` 最终确认版

**职责**：计算四维共振评分，输出真三振信号。

关键方法：
- `analyze_market_trend(index_data)` → 大盘趋势与位置（高位/中位/低位）
- `analyze_industry_trend(industry_data)` → 行业趋势与强度
- `analyze_capital_flow(stock_data)` → 资金活跃度（量比、换手、成交额放大）
- `calculate_resonance_score(...)` → 综合评分，真三振判定（≥85分且资金活跃、大盘向上、行业向上、个股OK）

**代码骨架**（可直接替换原文件）：

```python
import pandas as pd
import numpy as np

class ResonanceAnalyzer:
    def analyze_market_trend(self, index_data: pd.DataFrame) -> dict:
        if index_data is None or len(index_data) < 60:
            return {"trend": "未知", "position": "未知", "strength": 0}
        # 计算MA20/MA60，判断趋势
        close_col = '收盘价' if '收盘价' in index_data.columns else 'close'
        df = index_data.copy()
        df['MA20'] = df[close_col].rolling(20).mean()
        df['MA60'] = df[close_col].rolling(60).mean()
        latest = df.iloc[-1]
        # 趋势判断
        if latest[close_col] > latest['MA20'] > latest['MA60']:
            trend = "向上"
        elif latest[close_col] < latest['MA20'] < latest['MA60']:
            trend = "向下"
        else:
            trend = "震荡"
        # 位置判断
        high_120 = df[close_col].iloc[-120:].max()
        low_120 = df[close_col].iloc[-120:].min()
        pos_pct = (latest[close_col] - low_120) / (high_120 - low_120)
        position = "高位" if pos_pct >= 0.85 else ("低位" if pos_pct <= 0.2 else "中位")
        return {"trend": trend, "position": position, "strength": pos_pct}

    def analyze_capital_flow(self, stock_data: pd.DataFrame) -> dict:
        # 量比、成交额放大、换手率综合评分
        df = stock_data.copy()
        if df.empty or len(df) < 6:
            return {"active": False, "score": 0}
        vol_col = '成交量' if '成交量' in df.columns else 'volume'
        latest_vol = float(df[vol_col].iloc[-1])
        vol_ma5 = df[vol_col].iloc[-6:-1].mean()
        ratio = latest_vol / (vol_ma5 + 1e-8)
        score = 0
        if ratio >= 1.8: score += 12
        elif ratio >= 1.5: score += 8
        # 成交额放大
        if '成交额' in df.columns:
            amount_ma5 = df['成交额'].iloc[-6:-1].mean()
            if amount_ma5 > 0 and df['成交额'].iloc[-1] / amount_ma5 >= 1.6:
                score += 5
        # 换手率
        if '换手率' in df.columns and df['换手率'].iloc[-1] >= 3.0:
            score += 3
        score = min(score, 20)
        return {"active": score >= 8 or ratio >= 1.5, "score": score, "volume_ratio": ratio}

    def calculate_resonance_score(self, individual_result, market_result, industry_result, capital_result=None):
        score = 0
        # 个股30
        if individual_result.get("基础过滤") and individual_result.get("均线多头"):
            score += 30
        # 大盘25
        if market_result.get("trend") == "向上":
            score += 25
        # 行业25
        if industry_result.get("trend") == "向上":
            score += 25
        # 资金20
        capital_score = capital_result.get("score", 0) if capital_result else 0
        score += capital_score
        # 高位惩罚
        if market_result.get("position") == "高位":
            score = max(0, score - 15)
        is_true = score >= 85 and capital_result.get("active") and market_result.get("trend") == "向上" and industry_result.get("trend") == "向上" and individual_result.get("基础过滤")
        # 返回结果...
```

### 4.2 `analysis/mystery_logic.py` 完整实现

**职责**：整合基础滤网、周线锚定、破五反五、主升浪判断，调用共振分析，输出综合信号。

**核心方法**：

```python
import pandas as pd
from .resonance_analyzer import ResonanceAnalyzer

class MysteryLogic:
    def __init__(self):
        self.resonance_analyzer = ResonanceAnalyzer()

    def basic_filter(self, df: pd.DataFrame) -> dict:
        """年线多头排列检查"""
        required = ['收盘价', 'MA5', 'MA10', 'MA20', 'MA60', 'MA250']
        if df is None or len(df) < 250:
            return {"通过": False, "原因": "数据不足250日"}
        latest = df.iloc[-1]
        conditions = [
            latest['收盘价'] > latest['MA250'],
            latest['MA5'] > latest['MA10'] > latest['MA20'] > latest['MA60'] > latest['MA250']
        ]
        passed = all(conditions)
        return {"通过": passed, "原因": "年线多头排列完整" if passed else "未站稳年线或多头排列破坏"}

    def weekly_anchor_check(self, weekly_df: pd.DataFrame) -> dict:
        """周线锚定检查"""
        if weekly_df is None or len(weekly_df) < 60:
            return {"锚定": False, "原因": "周线数据不足60周"}
        weekly_df = weekly_df.copy()
        weekly_df['MA60_W'] = weekly_df['收盘价'].rolling(60).mean()
        latest = weekly_df.iloc[-1]
        prev = weekly_df.iloc[-2] if len(weekly_df) > 1 else latest
        above = latest['收盘价'] > latest['MA60_W']
        slope_ok = latest['MA60_W'] >= prev['MA60_W']  # 允许走平
        anchored = above and slope_ok
        return {"锚定": anchored, "原因": "周线稳居60周线之上" if anchored else "周线跌破或60周线拐头向下"}

    def check_po5_fan5(self, df: pd.DataFrame, lookback: int = 5) -> dict:
        """破五反五判定"""
        if df is None or len(df) < 5:
            return {"破五反五": False, "原因": "数据不足"}
        df = df.copy()
        df['MA5'] = df['收盘价'].rolling(5).mean()
        df['MA20'] = df['收盘价'].rolling(20).mean()
        recent = df.iloc[-lookback:]
        # 是否曾跌破MA5
        broke_mask = recent['收盘价'] < recent['MA5']
        if not broke_mask.any():
            return {"破五反五": False, "原因": "未破五"}
        last_broke_idx = recent.index[broke_mask][-1]
        # 是否已收回
        latest = df.iloc[-1]
        if latest['收盘价'] <= latest['MA5']:
            return {"破五反五": False, "原因": "仍处破五状态"}
        # 收回天数
        days_since_break = len(df.loc[last_broke_idx:]) - 1
        # MA20斜率向上
        ma20_slope_up = df['MA20'].iloc[-1] >= df['MA20'].iloc[-3] if len(df) >= 3 else False
        valid = days_since_break <= 2 and ma20_slope_up
        return {
            "破五反五": valid,
            "破五天数": days_since_break,
            "原因": "破五后2日内收回且MA20向上" if valid else "破五后未快速收回或MA20走平"
        }

    def main_bull_wave_analysis(self, df: pd.DataFrame, weekly_df: pd.DataFrame = None) -> dict:
        basic = self.basic_filter(df)
        weekly = self.weekly_anchor_check(weekly_df) if weekly_df is not None else {"锚定": True}
        po5 = self.check_po5_fan5(df)
        price_above_ma5 = df.iloc[-1]['收盘价'] > df.iloc[-1]['MA5']
        is_main = basic["通过"] and weekly["锚定"] and (price_above_ma5 or po5["破五反五"])
        return {
            "主升浪": is_main,
            "年线滤网": basic["通过"],
            "周线锚定": weekly["锚定"],
            "破五反五": po5["破五反五"],
            "详情": [basic["原因"], weekly["原因"], po5["原因"]]
        }

    def three_resonance_analysis(self, data, market_data=None, industry_data=None, industry_trend=None):
        # 计算个股结果
        basic = self.basic_filter(data)
        individual_result = {"基础过滤": basic["通过"], "均线多头": basic["通过"]}
        # 大盘
        if market_data:
            index_df = market_data.get("上证指数") or next(iter(market_data.values()))
            market_result = self.resonance_analyzer.analyze_market_trend(index_df)
        else:
            market_result = {"trend": "未知", "position": "未知"}
        # 行业
        if industry_data:
            industry_result = self.resonance_analyzer.analyze_industry_trend(industry_data)
        else:
            industry_result = {"trend": "向上" if industry_trend else "未知"}
        # 资金
        capital_result = self.resonance_analyzer.analyze_capital_flow(data)
        # 评分
        resonance = self.resonance_analyzer.calculate_resonance_score(
            individual_result=individual_result,
            market_result=market_result,
            industry_result=industry_result,
            capital_result=capital_result
        )
        return resonance

    def comprehensive_analysis(self, data, weekly_data=None, market_data=None, industry_data=None):
        basic = self.basic_filter(data)
        if not basic["通过"]:
            return {"综合评分": 0, "操作建议": "观望（未通过年线滤网）", "主升浪": False, "真三振": False, "详情": [basic["原因"]]}
        main_wave = self.main_bull_wave_analysis(data, weekly_data)
        resonance = self.three_resonance_analysis(data, market_data, industry_data)
        score = resonance["score"] * 0.6 + (40 if main_wave["主升浪"] else 0) * 0.4
        # 建议
        if resonance["is_true_three_strike"] and main_wave["主升浪"]:
            advice = "强烈关注（真三振 + 主升浪）"
        elif resonance["is_true_three_strike"]:
            advice = "重点关注（真三振）"
        elif main_wave["主升浪"]:
            advice = "可关注（主升浪持股期）"
        else:
            advice = resonance["advice"]
        return {
            "综合评分": round(score, 1),
            "操作建议": advice,
            "主升浪": main_wave["主升浪"],
            "年线滤网": main_wave["年线滤网"],
            "周线锚定": main_wave["周线锚定"],
            "破五反五": main_wave["破五反五"],
            "真三振": resonance["is_true_three_strike"],
            "共振评分": resonance["score"],
            "共振级别": resonance["level"],
            "资金活跃": resonance["capital_active"],
            "最强板块": resonance.get("industry_top", []),
            "详情": main_wave["详情"] + resonance.get("details", [])
        }
```

## 5. 数据接入层 (`utils/data_feeder.py`)

适配现有数据层，提供统一接口：

```python
from data.market_data_client import MarketDataClient

class DataFeeder:
    def __init__(self):
        self.client = MarketDataClient()  # 已集成的多源客户端

    def get_daily(self, code, count=300):
        # 调用 client.fetch_daily，自动包含均线计算？
        # 建议在获取后计算常用均线，供分析模块直接使用
        df = self.client.fetch_daily(code, start_date=None, end_date=None)
        if df is not None and not df.empty:
            for w in [5, 10, 20, 60, 250]:
                df[f'MA{w}'] = df['收盘价'].rolling(w).mean()
            return df
        return None

    def get_weekly(self, code):
        df = self.client.fetch_weekly(code)
        if df is not None and not df.empty:
            df['MA60_W'] = df['收盘价'].rolling(60).mean()
            return df
        return None

    def get_market_index(self):
        indices = {"上证指数": "sh.000001", "深证成指": "sz.399001"}
        result = {}
        for name, code in indices.items():
            df = self.get_daily(code, count=300)
            if df is not None:
                result[name] = df
        return result
```

## 6. 主程序/扫描入口改造

新增 `analysis/run_screen.py` 或修改 `main.py`：

```python
from data.market_data_client import MarketDataClient
from analysis.mystery_logic import MysteryLogic
from utils.data_feeder import DataFeeder
import pandas as pd

def main():
    feeder = DataFeeder()
    logic = MysteryLogic()
    stock_list = get_stock_list()  # 从数据库或文件读取
    results = []
    for code in stock_list:
        daily = feeder.get_daily(code)
        weekly = feeder.get_weekly(code)
        if daily is None:
            continue
        market = feeder.get_market_index()
        result = logic.comprehensive_analysis(daily, weekly, market_data=market)
        result['code'] = code
        results.append(result)
    df = pd.DataFrame(results)
    df.to_excel('output/scan_report.xlsx', index=False)
```

## 7. 配置扩展

在 `config/config.yaml` 中新增：

```yaml
analysis:
  ma_params:
    short: [5, 10, 20, 60]
    long: 250
    weekly_long: 60
  break_five:
    recover_days: 2
    ma20_slope_lookback: 3
  resonance:
    score_threshold: 85
    position_penalty: 15
  position:
    first_entry_pct: 0.1
    add_position_pct: 0.2
    max_total_pct: 0.3
```

## 8. 测试计划

- **单元测试**：覆盖 `basic_filter`、`weekly_anchor_check`、`check_po5_fan5`、`calculate_resonance_score` 的边界情况。
- **集成测试**：从数据层真实获取数据，运行 `comprehensive_analysis`，检查输出结构。
- **回测验证**：使用 `backtest/three_strike_mainwave_backtest.py` 框架，验证信号历史表现。
- **全市场扫描**：每日闭市后运行，输出信号报告。

## 9. 实施步骤

1. 备份现有 `analysis/` 目录。
2. 替换 `resonance_analyzer.py` 和 `mystery_logic.py`。
3. 新增 `utils/data_feeder.py`，调整导入路径。
4. 更新 `config.yaml`。
5. 编写并运行单元测试。
6. 编写扫描脚本，集成到定时任务。
7. 全链路验证（数据获取→分析→信号输出）。
8. 上线并监控日志。

## 10. 风险提示

- 分析结果仅供参考，不构成投资建议。
- 需根据实盘表现持续优化参数。
- 数据层需保持稳定，多源退避确保数据可用。

此方案完全基于现有工程和《Mistery趋势交易论》，可直接指导 Hermes 开发，无需重复造轮子。如有需要可提供完整代码文件或进一步细化。

