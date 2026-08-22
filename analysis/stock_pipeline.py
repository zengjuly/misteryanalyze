#!/usr/bin/env python3
# stock_pipeline.py - 单票深度分析统一入口（Web / daily 共用，docs/082209.md）
"""输出可 JSON 序列化的 dict，键名与 Excel/报告对齐。禁止内部再拉行情（由调用方注入）。"""
from typing import Any, Dict, Optional

import pandas as pd


def _sector_returns(sector_kline: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """板块 5/10/20 日涨跌（优先板块指数K线，docs/082209 §1.2）"""
    out = {
        '板块近5日涨跌': None,
        '板块近10日涨跌': None,
        '板块近20日涨跌': None,
        '板块趋势': None,  # True/False/None，供三振
    }
    if sector_kline is None or sector_kline.empty:
        return out
    df = sector_kline.copy()
    col = '收盘价' if '收盘价' in df.columns else (
        'close' if 'close' in df.columns else None)
    if not col or len(df) < 2:
        return out
    close = df[col].astype(float)
    last = float(close.iloc[-1])
    for days, key in [(5, '板块近5日涨跌'), (10, '板块近10日涨跌'),
                      (20, '板块近20日涨跌')]:
        if len(close) > days:
            past = float(close.iloc[-1 - days])
            if past > 0:
                out[key] = round((last / past - 1) * 100, 2)
    # 近10日 >0 视为走强（与 industry_trend 对齐时可覆盖）
    r10 = out['板块近10日涨跌']
    if r10 is not None:
        out['板块趋势'] = bool(r10 > 0)
    return out


def _multi_period(weekly: Optional[pd.DataFrame],
                  monthly: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """多周期共振（与 main.py _analyze_multi_period 单票分支一致，docs/082209 §1.3）
    周/月 MA5>MA10>MA20 为向上；两者都向上 → 多周期共振=True
    """
    result = {'周线趋势': '未知', '月线趋势': '未知', '多周期共振': False}
    # 周线：MA5/MA10/MA20 多头排列
    if weekly is not None and not weekly.empty and '收盘价' in weekly.columns:
        w = weekly.copy()
        w['MA5'] = w['收盘价'].rolling(5).mean()
        w['MA10'] = w['收盘价'].rolling(10).mean()
        w['MA20'] = w['收盘价'].rolling(20).mean()
        latest_w = w.iloc[-1]
        if (pd.notna(latest_w['MA5']) and pd.notna(latest_w['MA10'])
                and pd.notna(latest_w['MA20'])):
            if (latest_w['MA5'] > latest_w['MA10'] > latest_w['MA20']
                    and latest_w['收盘价'] > latest_w['MA20']):
                result['周线趋势'] = '多头排列'
            elif latest_w['MA5'] < latest_w['MA10'] < latest_w['MA20']:
                result['周线趋势'] = '空头排列'
            else:
                result['周线趋势'] = '震荡整理'
            result['周线最新价'] = round(float(latest_w['收盘价']), 2)
            result['周线MA20'] = round(float(latest_w['MA20']), 2)
    # 月线：MA5/MA10 多头排列
    if monthly is not None and not monthly.empty and '收盘价' in monthly.columns:
        m = monthly.copy()
        m['MA5'] = m['收盘价'].rolling(5).mean()
        m['MA10'] = m['收盘价'].rolling(10).mean()
        latest_m = m.iloc[-1]
        if pd.notna(latest_m['MA5']) and pd.notna(latest_m['MA10']):
            if (latest_m['MA5'] > latest_m['MA10']
                    and latest_m['收盘价'] > latest_m['MA10']):
                result['月线趋势'] = '多头排列'
            elif latest_m['MA5'] < latest_m['MA10']:
                result['月线趋势'] = '空头排列'
            else:
                result['月线趋势'] = '震荡整理'
            result['月线最新价'] = round(float(latest_m['收盘价']), 2)
            result['月线MA10'] = round(float(latest_m['MA10']), 2)
    # 多周期共振：周线多头 + 月线多头
    if (result['周线趋势'] == '多头排列'
            and result['月线趋势'] == '多头排列'):
        result['多周期共振'] = True
    return result


def analyze_one_stock(
    logic,                          # MysteryLogic 实例
    daily: pd.DataFrame,            # 已含指标的日K
    *,
    code: str = "",
    name: str = "",
    weekly: Optional[pd.DataFrame] = None,
    monthly: Optional[pd.DataFrame] = None,
    market_data: Optional[Dict] = None,
    industry_trend: Optional[bool] = None,
    industry_name: str = "未知",
    sector_kline: Optional[pd.DataFrame] = None,  # 板块指数日K（收盘价）
    financial: Optional[Dict] = None,
) -> Dict[str, Any]:
    """单票完整分析；禁止内部再拉行情（由调用方注入）。"""
    # 板块 5/10/20 涨跌 + 趋势
    sec = _sector_returns(sector_kline)
    ind_trend = industry_trend
    if ind_trend is None and sec.get('板块趋势') is not None:
        ind_trend = sec['板块趋势']

    signal = logic.comprehensive_signal_analysis(
        daily, weekly_data=weekly, market_data=market_data,
        industry_data=None, industry_trend=ind_trend)

    resonance = logic.three_resonance_analysis(
        daily, market_data=market_data,
        industry_trend=ind_trend, industry_data=None)

    bull = logic.main_bull_wave_analysis(daily)
    checklist = logic.main_bull_wave_checklist(daily,
                                               industry_trend=ind_trend)
    platform = logic.platform_breakthrough_analysis(
        daily, stock_code=code, weekly_data=weekly, monthly_data=monthly)
    technical = logic.technical_detail_capture(daily)
    multi = _multi_period(weekly, monthly)

    # 判定依据1/2/3：bull['判定依据'] 去掉「判定结果:」行后的前 3 条
    reasons = [x for x in (bull.get('判定依据') or [])
               if not str(x).startswith('判定结果')]
    while len(reasons) < 3:
        reasons.append('—')

    report: Dict[str, Any] = {
        '股票代码': code,
        '股票名称': name,
        '所属板块': industry_name,
        # 信号（Web 展示 + daily 报告共用）
        'signal': signal,
        '综合评分': signal.get('综合评分'),
        '共振级别': signal.get('共振级别'),
        '真三振': signal.get('真三振'),
        '主升浪信号': signal.get('主升浪信号'),
        '操作建议': signal.get('操作建议'),
        # 三振共振
        '三振共振': resonance,
        '板块趋势': ind_trend,
        '板块近5日涨跌': sec['板块近5日涨跌'],
        '板块近10日涨跌': sec['板块近10日涨跌'],
        '板块近20日涨跌': sec['板块近20日涨跌'],
        # 主升浪
        '主升浪状态': bull.get('状态', bull.get('主升浪状态', '未知')),
        '判定依据1': reasons[0],
        '判定依据2': reasons[1],
        '判定依据3': reasons[2],
        '满足数量': checklist.get('满足数量', 0),
        '主升浪判断': checklist.get('综合判断', '未知'),
        '主升浪8项': checklist.get('详情', []),
        # 平台突破
        '平台状态': platform.get('平台状态', '未知'),
        '平台箱体': platform.get('平台范围') or platform.get('平台箱体'),
        '突破信号': platform.get('突破信号', False),
        '买横信号': platform.get('买横信号', False),
        # 筹码
        '筹码集中度': technical.get('筹码集中度'),
        '筹码趋势': technical.get('筹码趋势'),
        # 多周期
        '周线趋势': multi['周线趋势'],
        '月线趋势': multi['月线趋势'],
        '多周期共振': multi['多周期共振'],
        '周线最新价': multi.get('周线最新价'),
        '周线MA20': multi.get('周线MA20'),
        '月线最新价': multi.get('月线最新价'),
        '月线MA10': multi.get('月线MA10'),
        # 财务
        'financial': financial or {},
    }
    # 兼容旧键（一周过渡，docs/082209 §3.2）
    report['板块近5日'] = report['板块近5日涨跌']
    report['板块近10日'] = report['板块近10日涨跌']
    report['板块近20日'] = report['板块近20日涨跌']
    return report
