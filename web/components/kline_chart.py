#!/usr/bin/env python3
# kline_chart.py - K线图组件（docs/ui.md §5.1）
"""交互式K线图：蜡烛图 + MA5/10/20/60/250 + 成交量副图（Plotly）"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

MA_LIST = ['MA5', 'MA10', 'MA20', 'MA60', 'MA250']
MA_COLORS = {'MA5': '#f39c12', 'MA10': '#e74c3c', 'MA20': '#3498db',
             'MA60': '#9b59b6', 'MA250': '#2c3e50'}


def plot_kline(df: pd.DataFrame, title: str = "日K线",
               with_volume: bool = True, height: int = 600) -> go.Figure:
    """绘制带均线的K线图 + 成交量副图
    :param df: 含 日期/开盘价/最高价/最低价/收盘价（可选 MA*/成交量）
    """
    if df is None or df.empty:
        return go.Figure()
    rows = 2 if (with_volume and '成交量' in df.columns) else 1
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05,
        row_heights=[0.8, 0.2] if rows == 2 else [1.0])
    # 蜡烛图
    fig.add_trace(go.Candlestick(
        x=df['日期'], open=df['开盘价'], high=df['最高价'],
        low=df['最低价'], close=df['收盘价'], name='日K',
        increasing_line_color='#e74c3c', decreasing_line_color='#2ecc71',
    ), row=1, col=1)
    # 均线
    for ma in MA_LIST:
        if ma in df.columns:
            fig.add_trace(go.Scatter(
                x=df['日期'], y=df[ma], mode='lines', name=ma,
                line=dict(width=1.2, color=MA_COLORS.get(ma, '#888')),
            ), row=1, col=1)
    # 成交量副图
    if rows == 2:
        colors = ['#e74c3c' if row['收盘价'] >= row['开盘价'] else '#2ecc71'
                  for _, row in df.iterrows()]
        fig.add_trace(go.Bar(
            x=df['日期'], y=df['成交量'], marker_color=colors, name='成交量',
        ), row=2, col=1)
    fig.update_layout(
        title=title, xaxis_rangeslider_visible=False, height=height,
        template='plotly_white', margin=dict(l=40, r=20, t=50, b=30),
        legend=dict(orientation='h', y=1.02),
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=['sat', 'mon'])])  # 跳过周末
    return fig
