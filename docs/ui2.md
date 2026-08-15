分析工程实现 https://github.com/zengjuly/misteryanalyze ， 分析实现以下内容的方案。尽量复用github的开源免费工程。

一、个股深度分析 
支持输入股票名称
股票池选择 支持显示股票名称、支持模糊搜索
分析结果显示内容要和excel分析结果一致（如震荡区间、周K 月K分析、筹码分析、主升浪8项指标对比等）

K线图增加macd指标
支持切换为周K月K
震荡区间在K线图中绘制出来

分析结构增加财务数据
PB、PE、最近连续三年的ROE、股息率

二、分析结果要缓存
只要行情没有更新，不要重复分析，包括 个股分析、全量扫描结果

三、板块监控
内容为空

四、支持股票池配置，配置时支持模糊匹配


grok分析结果请参考：


针对你提出的 4 点需求，结合 `zengjuly/misteryanalyze` 仓库现有结构（Streamlit 多页面、`analysis/mystery_logic.py`、`data/kline_resampler.py`、SQLite 缓存等），以下是一套可直接落地的实现方案。尽量复用现有模块与开源组件，减少重复开发。

---

## 一、个股深度分析模块

### 1. 股票输入与模糊搜索
**现状**：仓库已有通达信股票列表解析（`tdx_local_client.py` / `db_manager.py`）。  
**方案**：
- 初始化时加载全市场股票代码-名称字典。
- 前端使用 `streamlit-searchbox` 组件（开源免费）实现模糊搜索，匹配代码或名称。
- 搜索返回 `"600150.SH - 中国船舶"` 格式，选中后解析出代码。

```python
# web/utils/session.py 中缓存字典
@st.cache_resource
def get_all_stock_names_dict():
    feeder = get_feeder()
    return feeder.get_all_stock_code_name()  # 返回 {code: name}
```

```python
from streamlit_searchbox import st_searchbox
stock_dict = get_all_stock_names_dict()

def search_stock(term: str):
    term = term.lower().strip()
    if not term:
        return [f"{c} - {n}" for c, n in list(stock_dict.items())[:50]]
    return [f"{c} - {n}" for c, n in stock_dict.items()
            if term in c.lower() or term in n.lower()]

selected = st_searchbox(search_stock, key="stock_search", label="🔍 代码/名称模糊搜索")
if selected:
    code = selected.split(" - ")[0]
```

### 2. 分析结果与 Excel 对齐
**现状**：`analysis/mystery_logic.py` 已返回完整分析字典，包含震荡区间、周/月K箱体、筹码集中度、主升浪8项 checklist 等。  
**方案**：前端直接解析该字典，用 `st.metric`、`st.dataframe`、Markdown 表格还原 Excel 报告。

- **震荡区间卡片**：展示上沿、下沿、POC、当前位置。
- **主升浪8项对比表**：从 `checklist` dict 转换为 DataFrame 展示 ✅/❌。
- **筹码分析**：展示集中度数值与趋势。

### 3. K线图升级（MACD + 周期切换 + 震荡区间绘制）
**现状**：`web/components/kline_chart.py` 仅有蜡烛图 + MA + 成交量。  
**方案**：重写为 3 行 Plotly 子图（蜡烛+MA+箱体 / 成交量 / MACD），支持日/周/月切换。

```python
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from indicators.trend_indicators import TrendIndicators

def plot_kline_with_macd(df, title="K线", box=None, height=720):
    # 若没有MACD列，则计算
    if 'MACD' not in df.columns:
        df = TrendIndicators().calculate_macd(df)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.55,0.2,0.25],
                        subplot_titles=(title, "成交量", "MACD"))
    # Row1: 蜡烛 + MA
    fig.add_trace(go.Candlestick(x=df['日期'], open=df['开盘价'],
                                 high=df['最高价'], low=df['最低价'],
                                 close=df['收盘价'], name='K线'), row=1, col=1)
    for ma in ['MA5','MA10','MA20','MA60','MA250']:
        if ma in df.columns:
            fig.add_trace(go.Scatter(x=df['日期'], y=df[ma],
                                     mode='lines', name=ma), row=1, col=1)
    # 震荡区间矩形
    if box and box.get('上沿') and box.get('下沿'):
        fig.add_shape(type="rect", x0=df['日期'].iloc[0], x1=df['日期'].iloc[-1],
                      y0=box['下沿'], y1=box['上沿'],
                      fillcolor="rgba(128,128,128,0.15)", line=dict(width=0),
                      row=1, col=1)
    # Row2: 成交量
    vol_colors = ['#e74c3c' if c >= o else '#2ecc71' for o,c in zip(df['开盘价'], df['收盘价'])]
    fig.add_trace(go.Bar(x=df['日期'], y=df['成交量'], marker_color=vol_colors,
                         name='成交量'), row=2, col=1)
    # Row3: MACD
    if 'DIF' in df.columns:
        fig.add_trace(go.Scatter(x=df['日期'], y=df['DIF'], name='DIF'), row=3, col=1)
    if 'DEA' in df.columns:
        fig.add_trace(go.Scatter(x=df['日期'], y=df['DEA'], name='DEA'), row=3, col=1)
    hist_col = 'MACD柱' if 'MACD柱' in df.columns else 'MACD_Histogram'
    if hist_col in df.columns:
        hist_colors = ['#e74c3c' if v >= 0 else '#2ecc71' for v in df[hist_col]]
        fig.add_trace(go.Bar(x=df['日期'], y=df[hist_col], marker_color=hist_colors,
                             name='MACD柱'), row=3, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False, height=height,
                      template='plotly_white')
    return fig
```

**前端周期切换**：

```python
period = st.radio("周期", ["日线", "周线", "月线"], horizontal=True)
if period == "日线":
    kdf = daily.tail(150)
    box = signal.get('平台范围') or signal.get('固定箱体')
elif period == "周线":
    kdf = resampler.to_weekly(daily).tail(80)   # 若无预生成周线
    box = signal.get('周线箱体')
else:
    kdf = resampler.to_monthly(daily).tail(48)
    box = signal.get('月线箱体')
# 确保均线存在
if 'MA5' not in kdf.columns:
    kdf = MAIndicators().calculate_all(kdf)
fig = plot_kline_with_macd(kdf, title=f"{code} {period}", box=box)
st.plotly_chart(fig, use_container_width=True)
```

### 4. 财务数据展示
**现状**：`data/financial_storage.py` 已支持本地存储，若缺失可调用 akshare 拉取。  
**方案**：
- 从 `FinancialStorage().load_latest(code)` 读取 PE、PB、股息率、ROE 等字段。
- 展示为 4 个 `st.metric`，并附最近三年 ROE 表格。

```python
fs = FinancialStorage()
fi = fs.load_latest(code) or {}
col1, col2, col3, col4 = st.columns(4)
col1.metric("PE", fi.get('PE', 'N/A'))
col2.metric("PB", fi.get('PB', 'N/A'))
col3.metric("股息率", f"{fi.get('股息率', 0):.2f}%")
col4.metric("最新ROE", f"{fi.get('ROE', 'N/A')}%")
```

---

## 二、分析结果多级缓存

**核心思想**：以 `(股票代码, 周期, 最新K线日期)` 为联合主键，行情未更新则直接返回缓存，避免重复计算。

### 1. 缓存表设计
在 `db_manager.py` 初始化时创建：

```sql
CREATE TABLE IF NOT EXISTS mystery_analysis_cache (
    stock_code      TEXT NOT NULL,
    period          TEXT NOT NULL,      -- daily/weekly/monthly
    last_trade_date TEXT NOT NULL,      -- YYYY-MM-DD
    report_json     TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (stock_code, period, last_trade_date)
);
```

### 2. 缓存读写方法
在 `MysteryDB` 类中新增：

```python
import json
def get_analysis_cache(self, stock_code, period, last_trade_date):
    conn = self._connect()
    try:
        row = conn.execute("SELECT report_json FROM mystery_analysis_cache "
                           "WHERE stock_code=? AND period=? AND last_trade_date=?",
                           (stock_code, period, last_trade_date)).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()

def set_analysis_cache(self, stock_code, period, last_trade_date, report):
    conn = self._connect()
    try:
        conn.execute("INSERT OR REPLACE INTO mystery_analysis_cache "
                     "(stock_code, period, last_trade_date, report_json, created_at) "
                     "VALUES (?,?,?,?,datetime('now'))",
                     (stock_code, period, last_trade_date,
                      json.dumps(report, ensure_ascii=False, default=str)))
        conn.commit()
    finally:
        conn.close()
```

### 3. 调用示例
在个股分析入口和全量扫描入口使用：

```python
last_date = db.get_last_trade_date(code, 'daily')
cached = db.get_analysis_cache(code, 'daily', last_date)
if cached:
    signal = cached
else:
    signal = logic.comprehensive_signal_analysis(...)
    db.set_analysis_cache(code, 'daily', last_date, signal)
```

全量扫描可整批缓存到单独表或同一表，用 `period='full_scan'` 标识。必要时用 `st.cache_data` 做短期前端缓存（TTL 1800 秒），减少数据库查询。

---

## 三、板块监控模块

**现状**：`web/pages/2_📊_板块监控.py` 仅有基础板块涨幅排名，用户反馈“内容为空或不足”。  
**方案**：升级为“板块共振强度模型 + 成分股钻取”，复用 `resonance_analyzer.py`（若存在）或自建评分。

### 评分公式
```
板块得分 = MA20偏离度×0.4 + 近10日涨幅×0.3 + 成交额放大倍数×0.3
```

### 前端布局
- 左栏：Plotly 横向条形图展示 Top15 强势板块，同时提供全量排名表格及导出。
- 右栏：点击板块 → 对成分股逐一运行 `comprehensive_signal_analysis`，高亮“真三振 + 综合评分≥85”的龙头，支持一键跳转个股。

### 关键代码骨架
```python
@st.cache_data(ttl=3600)
def calc_sector_strength():
    industry_map = feeder.get_industry_data()['industry_codes']
    rows = []
    for industry, codes in industry_map.items():
        # 取样若干成分股，计算平均MA20偏离、近10日涨幅、量比
        # 加权得到 score
        rows.append({...})
    return sorted(rows, key=lambda r: r['score'], reverse=True)
```

右侧钻取：
```python
for code in selected_codes:
    sig = logic.comprehensive_signal_analysis(daily, weekly)
    results.append({... '真三振': sig.get('真三振'), '综合评分': sig.get('综合评分')})
# 用 st.dataframe 的 style.apply 高亮满足条件行
```

---

## 四、股票池配置 + 模糊匹配

**现状**：已有 `watchlist.json` 持久化自选股。  
**方案**：
- 新增配置区（可放在系统状态页或个股分析页侧边栏）。
- 使用 `streamlit-searchbox` 模糊添加。
- 全局股票池选择器（如“全市场A股”“核心自选池”），决定扫描/分析范围。

### 核心代码
```python
# 添加自选股
add_item = st_searchbox(search_stock, key="pool_add", label="➕ 模糊添加")
if st.button("添加到股票池") and add_item:
    code = add_item.split(" - ")[0].strip()
    wl = load_watchlist()
    if code not in wl:
        wl.append(code)
        save_watchlist(wl)
        st.success(f"已添加 {add_item}")
        st.rerun()

# 当前运行池
pool = st.selectbox("🎯 当前运行股票池", ["全市场A股", "核心自选池"], key="pool_selector")
st.session_state['current_pool'] = pool
```

扫描页调用：
```python
codes = get_current_pool_codes(st.session_state.get('current_pool', '全市场A股'))
```

---

## 五、落地顺序与注意事项

### 建议优先级
1. **K线组件升级 + 个股分析页展示**：见效最快，直接对齐 Excel。
2. **缓存机制**：显著提升响应速度，尤其全量扫描。
3. **板块监控完善**：独立模块，可并行开发。
4. **股票池配置**：依赖模糊搜索组件，可与第1点共用。

### 兼容性提醒
- 列名中英文混用：建议统一使用中文列名（如 `日期`、`开盘价`），或在读取后做一次标准化映射。
- `streamlit-searchbox` 返回值为字符串，解析时需注意格式。
- `akshare` 接口可能变动，财务补丁需捕获异常。
- 全量扫描缓存建议单独建表或加 `scan_date` 字段，避免与个股缓存混淆。

以上方案完全基于仓库现有结构设计，最大化复用已有代码与开源组件（`plotly`、`streamlit-searchbox`、`akshare` 等），实现成本低、可维护性高。若需要某个文件的完整代码或具体接口调整，可进一步提供。


