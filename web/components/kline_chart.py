#!/usr/bin/env python3
# kline_chart.py - K线图组件（docs/ui.md §5.1 + docs/ui2.md 升级）
"""交互式K线图 v2：
- 3行子图：蜡烛+MA+震荡区间矩形 / 成交量 / MACD
- 支持日/周/月任意周期 DataFrame（含 MACD 列自动计算）
- 震荡区间矩形绘制（上沿/下沿/最新价参考线）
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

MA_LIST = ['MA5', 'MA10', 'MA20', 'MA60', 'MA250', 'MA377', 'MA610']
MA_COLORS = {'MA5': '#f39c12', 'MA10': '#e74c3c', 'MA20': '#3498db',
             'MA60': '#9b59b6', 'MA250': '#2c3e50',
             'MA377': '#8e44ad', 'MA610': '#16a085'}
EMA_LIST = ['EMA20']
EMA_COLORS = {'EMA20': '#e67e22'}  # 橙色虚线区分
UP, DOWN = '#e74c3c', '#2ecc71'  # A股红涨绿跌


def _ensure_macd(df: pd.DataFrame) -> pd.DataFrame:
    """若缺少 MACD 列则计算（复用 TrendIndicators）"""
    if 'MACD' in df.columns and 'MACD_Signal' in df.columns:
        return df
    try:
        from indicators.trend_indicators import TrendIndicators
        return TrendIndicators().calculate_macd(df)
    except Exception:
        return df


def plot_kline(df: pd.DataFrame, title: str = "K线",
               box: dict = None, with_volume: bool = True,
               height: int = 720, max_bars: int = 1000) -> go.Figure:
    """绘制带均线/MACD/震荡区间的K线图
    :param df: 含 日期/开盘价/最高价/最低价/收盘价（可选 MA*/MACD*）
    :param box: {'上沿': x, '下沿': y, 'POC': z} 震荡区间（K线图矩形）
    :param max_bars: 最多显示最近 N 根（docs/081601.md: 日1000/周200/月50）
    """
    if df is None or df.empty:
        return go.Figure()
    if len(df) > max_bars:
        df = df.tail(max_bars).copy()
    df = _ensure_macd(df)
    rows = 3 if 'MACD' in df.columns else (2 if (with_volume and '成交量' in df.columns) else 1)
    if rows == 3:
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                            vertical_spacing=0.03, row_heights=[0.55, 0.2, 0.25],
                            subplot_titles=(title, "成交量", "MACD"))
    else:
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                            vertical_spacing=0.05,
                            row_heights=[0.8, 0.2] if rows == 2 else [1.0],
                            subplot_titles=(title, "成交量") if rows == 2 else (title,))
    # ---- Row1: 蜡烛 + MA ----
    fig.add_trace(go.Candlestick(
        x=df['日期'], open=df['开盘价'], high=df['最高价'],
        low=df['最低价'], close=df['收盘价'], name='K线',
        increasing_line_color=UP, decreasing_line_color=DOWN,
    ), row=1, col=1)
    for ma in MA_LIST:
        if ma in df.columns:
            fig.add_trace(go.Scatter(
                x=df['日期'], y=df[ma], mode='lines', name=ma,
                line=dict(width=1.1, color=MA_COLORS.get(ma, '#888')),
            ), row=1, col=1)
    # EMA 曲线（docs/081601.md: EMA20 橙色虚线）
    for ema in EMA_LIST:
        if ema in df.columns:
            fig.add_trace(go.Scatter(
                x=df['日期'], y=df[ema], mode='lines', name=ema,
                line=dict(width=1.5, color=EMA_COLORS.get(ema, '#e67e22'),
                          dash='dash'),
            ), row=1, col=1)
    # 震荡区间矩形（docs/ui2.md: 在K线图中绘制）
    if box and box.get('上沿') and box.get('下沿'):
        x0, x1 = df['日期'].iloc[0], df['日期'].iloc[-1]
        fig.add_shape(type='rect', x0=x0, x1=x1,
                      y0=float(box['下沿']), y1=float(box['上沿']),
                      fillcolor='rgba(128,128,128,0.15)', line=dict(width=0),
                      row=1, col=1)
        fig.add_hline(y=float(box['上沿']), line_dash='dot',
                      line_color='rgba(52,152,219,0.7)', row=1, col=1)
        fig.add_hline(y=float(box['下沿']), line_dash='dot',
                      line_color='rgba(52,152,219,0.7)', row=1, col=1)
        if box.get('POC'):
            fig.add_hline(y=float(box['POC']), line_dash='dash',
                          line_color='rgba(243,156,18,0.7)', row=1, col=1)
    # ---- Row2: 成交量 ----
    if rows >= 2 and '成交量' in df.columns:
        colors = [UP if c >= o else DOWN
                  for o, c in zip(df['开盘价'], df['收盘价'])]
        fig.add_trace(go.Bar(x=df['日期'], y=df['成交量'],
                             marker_color=colors, name='成交量'),
                      row=2, col=1)
    # ---- Row3: MACD ----
    if rows == 3:
        fig.add_trace(go.Scatter(x=df['日期'], y=df['MACD'],
                                 mode='lines', name='DIF',
                                 line=dict(width=1, color='#3498db')),
                      row=3, col=1)
        fig.add_trace(go.Scatter(x=df['日期'], y=df['MACD_Signal'],
                                 mode='lines', name='DEA',
                                 line=dict(width=1, color='#f39c12')),
                      row=3, col=1)
        if 'MACD_Histogram' in df.columns:
            hc = [UP if v >= 0 else DOWN for v in df['MACD_Histogram']]
            fig.add_trace(go.Bar(x=df['日期'], y=df['MACD_Histogram'],
                                 marker_color=hc, name='MACD柱'),
                          row=3, col=1)
    fig.update_layout(
        title=title, xaxis_rangeslider_visible=False, height=height,
        template='plotly_white', margin=dict(l=40, r=20, t=60, b=30),
        legend=dict(orientation='h', y=1.02),
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=['sat', 'mon'])])  # 跳过周末
    return fig
