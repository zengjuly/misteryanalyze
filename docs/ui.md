# Mystery 趋势交易系统前端设计文档

**文档版本**：1.0  
**目标系统**：Ubuntu 24 服务器 + misteryanalyze 后端  
**访问端口**：1888  
**核心原则**：优先使用成熟 GitHub 开源组件，避免重复造轮子  
**面向对象**：Hermes 开发

---

## 1. 目标与范围

本设计文档为 misteryanalyze 系统增加一个基于 Web 的交互式分析界面，使用户能够：

- 输入股票代码，查看深度分析（多周期共振、主升浪、年线滤网、破五反五）
- 浏览全市场扫描结果，筛选真三振 / 主升浪股票
- 查看板块强度与成分股共振情况
- 监控数据源健康状态与系统缓存信息

前端完全复用现有 Python 分析引擎，不改变后端逻辑，仅提供可视化层。

---

## 2. 技术选型

| 层级 | 推荐组件 | 理由 |
|------|----------|------|
| 前端框架 | **Streamlit** | 纯 Python、开发速度最快、股票分析社区最成熟、多页面原生支持 |
| 图表 | Plotly + streamlit-plotly | 交互式 K 线、指标叠加，开箱即用 |
| 表格 | streamlit-aggrid 或 st.dataframe | 高性能、可筛选排序 |
| K线增强 | Plotly Candlestick | 专业交易风格，支持均线叠加 |
| 布局 | Streamlit 原生 multipage + sidebar | 无需额外前端框架 |
| 认证（可选） | streamlit-authenticator | 简单账号密码保护 |
| 部署 | systemd + `streamlit run --server.port 1888` | Ubuntu 原生稳定 |

**为什么选择 Streamlit？**  
股票扫描 + 个股分析 + 板块查看是典型的“数据仪表盘”场景，Streamlit 是该场景的默认选择。  
- 开发速度最快（几小时可出原型），完全复用现有 Python 分析引擎，无需写 JS。  
- 已有大量开源股票扫描仪表盘可直接参考。

**备选方案**：NiceGUI 或 Dash（如后期需要更强交互）。

---

## 3. 整体架构与目录结构

### 3.1 架构图

```
浏览器 (http://服务器IP:1888)
        ↓
Streamlit App (port 1888)
        ↓
调用现有后端
├── analysis/mystery_logic.py        # 核心分析逻辑
├── analysis/resonance_analyzer.py   # 三振共振评分
├── utils/data_feeder.py             # 数据接入适配器
├── data/ (MarketDataClient / DBManager)
└── SQLite 缓存
```

### 3.2 目录建议

```
misteryanalyze/
├── web/                          # 新增前端目录
│   ├── app.py                    # 主入口（页面配置 + sidebar）
│   ├── pages/
│   │   ├── 1_📈_个股分析.py
│   │   ├── 2_📊_板块监控.py
│   │   ├── 3_🔍_全市场扫描.py
│   │   ├── 4_💎_真三振池.py
│   │   └── 5_⚙️_系统状态.py
│   ├── components/               # 可复用组件
│   │   ├── kline_chart.py        # K线图组件
│   │   ├── score_card.py         # 评分卡片组件
│   │   └── stock_table.py        # 股票表格组件
│   └── utils/
│       └── session.py            # 会话状态管理
├── analysis/
├── data/
└── ...
```

---

## 4. 页面功能详细设计

### 4.1 页面 1：个股深度分析（核心）

**输入**：股票代码（支持模糊搜索，如输入“600519”或“贵州茅台”）  
**按钮**：“开始分析”  
**输出内容**：

1. **评分卡片区**（4列布局）  
   - 综合评分（0-100）  
   - 真三振状态（是/否）  
   - 主升浪状态（是/否）  
   - 资金活跃度（是/否）

2. **详细状态卡片**  
   - 年线滤网：通过/未通过  
   - 周线锚定：锚定/未锚定  
   - 破五反五：符合/不符合  
   - 共振级别：真三振/二级/一级/无

3. **操作建议**  
   以醒目方式展示 `操作建议` 字段，如“强烈关注（真三振 + 主升浪）”。

4. **交互式K线图**  
   - 日K线（蜡烛图）  
   - 叠加 MA5、MA10、MA20、MA60、MA250 均线  
   - 成交量副图  
   - 支持缩放、悬停提示

5. **分析详情文本**  
   列出所有触发条件明细（如“年线多头排列完整”、“破五后2日内收回且MA20向上”等）。

6. **最近N日数据表格**  
   显示最近20个交易日的 OHLCV 及技术指标。

---

### 4.2 页面 2：板块监控

**功能**：
- 展示行业/概念板块列表（数据来自通达信或申万）  
- 板块强度排名（按涨跌幅、资金净流入排序）  
- 点击某板块 → 显示该板块成分股的三振情况（真三振数量、主升浪数量）  
- 支持导出 CSV

**实现提示**：  
板块数据需要从后端获取，可复用现有 `DataFeeder.get_industry_data()` 或扩展。

---

### 4.3 页面 3：全市场扫描

**参数设置**：
- 是否只看真三振
- 是否只看主升浪
- 评分阈值（默认 85）
- 扫描范围（全部A股 / 自定义股票池）

**按钮**：“开始扫描”  
**过程**：后台循环调用分析逻辑，显示进度条（`st.progress`）  
**结果表格**：
- 股票代码、名称、综合评分、真三振、主升浪、资金活跃、建议  
- 支持排序、筛选、导出 CSV  
- 真三振股票高亮显示

**性能考虑**：  
扫描全市场可能耗时较长，建议：
- 使用 `st.cache_data` 缓存已分析结果  
- 分批处理，避免阻塞主线程（可用 `st.status` 上下文）  
- 可考虑使用 `threading` 后台执行，但 Streamlit 原生不支持异步，简单循环即可（配合进度条）。

---

### 4.4 页面 4：真三振池

**功能**：
- 展示最近一次扫描产生的真三振股票列表  
- 支持加入自选股（存储到本地文件或数据库）  
- 每只股票旁边提供“一键分析”按钮，跳转到个股分析页面并自动填入代码  
- 显示真三振触发时间、评分、共振详情

**数据来源**：  
扫描结果存储到 SQLite 或内存中，页面从该处读取。

---

### 4.5 页面 5：系统状态

**功能**：
- 数据源健康状态：tdx_local / akshare / baostock 的成功率、熔断状态、健康分  
- SQLite 缓存信息：`stock_kline_data` 表行数、最后更新时间  
- 最近日志预览（可选）  
- 数据源报告生成按钮（调用 `source_report.py`）

---

## 5. 核心组件设计

### 5.1 K线图组件（`components/kline_chart.py`）

```python
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

def plot_kline(df: pd.DataFrame, title: str = "日K线"):
    """绘制带均线的K线图 + 成交量"""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.05, row_heights=[0.8, 0.2])
    # 蜡烛图
    fig.add_trace(go.Candlestick(
        x=df['日期'], open=df['开盘价'], high=df['最高价'],
        low=df['最低价'], close=df['收盘价'],
        name='日K'
    ), row=1, col=1)
    # 均线
    for ma in ['MA5', 'MA10', 'MA20', 'MA60', 'MA250']:
        if ma in df.columns:
            fig.add_trace(go.Scatter(
                x=df['日期'], y=df[ma], mode='lines', name=ma, line=dict(width=1)
            ), row=1, col=1)
    # 成交量
    colors = ['red' if row['收盘价'] >= row['开盘价'] else 'green' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df['日期'], y=df['成交量'], marker_color=colors, name='成交量'), row=2, col=1)
    fig.update_layout(title=title, xaxis_rangeslider_visible=False, height=600)
    return fig
```

### 5.2 评分卡片组件（`components/score_card.py`）

使用 `st.metric` 展示关键指标，可配合 `st.columns` 实现多卡片布局。

### 5.3 股票表格组件（`components/stock_table.py`）

使用 `st.dataframe` 或 `streamlit-aggrid` 展示股票列表，支持排序、筛选、高亮真三振行。

---

## 6. 后端接口对接

前端通过以下方式获取数据并调用分析逻辑：

```python
from analysis.mystery_logic import MysteryLogic
from utils.data_feeder import DataFeeder

# 初始化
feeder = DataFeeder()      # 内部实例化 MarketDataClient 和数据库管理
logic = MysteryLogic()

# 个股分析
code = "600519"
daily = feeder.get_daily(code, count=300)     # 自动计算均线
weekly = feeder.get_weekly(code)
market_data = feeder.get_market_index()
industry_data = feeder.get_industry_data()

result = logic.comprehensive_analysis(
    data=daily,
    weekly_data=weekly,
    market_data=market_data,
    industry_data=industry_data
)
```

**关键约定**：
- `get_daily` / `get_weekly` 返回的 DataFrame 应包含中文列名（日期、代码、开盘价、最高价、最低价、收盘价、成交量、成交额、换手率、涨跌幅，以及 MA 列）。
- `comprehensive_analysis` 返回字典，字段见之前重构文档，包括：综合评分、操作建议、主升浪、真三振、年线滤网、周线锚定、破五反五、资金活跃、最强板块、详情等。
- 板块数据 `get_industry_data()` 需根据实际情况实现，可返回空字典（前端页面显示暂无数据）。

---

## 7. Ubuntu 24 部署方案（生产级）

### 7.1 安装依赖

```bash
cd /path/to/misteryanalyze
python3 -m venv venv
source venv/bin/activate
pip install streamlit plotly streamlit-aggrid pandas numpy
```

### 7.2 创建 systemd 服务

```bash
sudo nano /etc/systemd/system/mystery-web.service
```

内容：

```ini
[Unit]
Description=Mystery Analyze Web UI
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/path/to/misteryanalyze
Environment="PATH=/path/to/misteryanalyze/venv/bin"
ExecStart=/path/to/misteryanalyze/venv/bin/streamlit run web/app.py --server.port 1888 --server.address 0.0.0.0 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动并设置开机自启：

```bash
sudo systemctl daemon-reload
sudo systemctl enable mystery-web
sudo systemctl start mystery-web
```

防火墙开放端口：

```bash
sudo ufw allow 1888/tcp
```

访问：`http://服务器公网IP:1888`

---

## 8. 参考开源仓库

以下项目可作为开发参考：

- [Stock_Score_App](https://github.com/sehgalaryan1/Stock_Score_App) — 多页面股票评分
- [Streamlit-Multi-Page-Stock-Dashboard](https://github.com/Cawinchan/Streamlit-Multi-Page-Stock-Dashboard) — 多页面股票仪表盘
- [StockAnalysisApp](https://github.com/antonio-catalano/StockAnalysisApp) — 经典个股分析
- [Streamlit-Scanner-App](https://github.com/DoRmAmMu1997/Streamlit-Scanner-App) — 扫描器风格（最接近需求）

---

## 9. 实施优先级建议

| 阶段 | 内容 | 预计时间 |
|------|------|----------|
| P0 | 个股分析页面 + 基础K线 + 四维评分展示 | 1 天 |
| P1 | 全市场扫描页面 + 结果表格 | 1 天 |
| P2 | 真三振池 + 板块监控 | 1 天 |
| P3 | 系统状态 + 简单登录 | 0.5 天 |
| P4 | 美化与性能优化 | 持续 |

---

## 10. 总结

采用 **Streamlit 多页面架构** 是当前最省力、最贴合需求、开源组件最丰富的方案，能够在 2–3 天内上线可用版本，且与现有 Python 后端无缝集成。

前端设计文档已覆盖从技术选型到部署的完整流程，Hermes 可直接按此文档进行开发。如有需要，可进一步输出具体页面的完整可运行代码。

