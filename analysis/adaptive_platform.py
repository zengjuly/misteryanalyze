#!/usr/bin/env python3
# adaptive_platform.py - 自适应VAP-ATR平台中枢识别（基于gemmi分析优化报告 docs/design.md + docs/gemmi_an.md）
"""
自适应 VAP-ATR 平台中枢识别算法
================================
理论来源: docs/design.md（gemmi 分析优化报告）+ docs/gemmi_an.md（自适应周期）

核心思想:
  传统平台识别依赖固定周期高低点（唐奇安通道）或固定百分比，存在两大缺陷:
  1. 忽略量能维度 —— 无法分辨资金真正堆积的"核心价值区"与瞬间刺穿的"情绪极值点"
  2. 忽略波动率动态变化 —— 高波动期固定箱体频繁假突破，低波动期箱体过宽信号滞后

本模块通过"成交量决定中枢核心(POC)，波动率(ATR)决定边界容差"解决上述问题:

  ① VAP 筹码分布: 成交量加权的价格分布 → POC(筹码控制点)取代固定箱体中轴
  ② 自适应 ATR 通道: 上轨 = POC + k×ATR, 下轨 = POC - k×ATR（随波动率动态缩放）
  ③ A股适配修正:
     - MTR(Modified True Range): 涨停时用过去14日均值填充, 防止ATR冻结归零
     - K线重心 P_core: 用 Low+G×(High-Low) 替代收盘价, 防止长上影线误导筹码分布
     - 实体突破: Close>上轨 且 阳线 且 重心>0.5 且 非涨停次日, 排除假突破
  ④ 自适应检测周期（gemmi_an.md）:
     - N_base = 70% / 日均换手率（筹码换手周期）, clip 到 [10, 60]
     - 小盘妖股（换手15-20%）→ 5-10日窗口; 大盘蓝筹（换手0.5-1.5%）→ 60日窗口
     - 双周期嵌套: 慢窗口(POC筹码分布, 自适应N) + 快窗口(ATR波动率, clip(N/4, 10, 14))
     - k 自适应: 高换手活跃股放宽(2.2), 低换手蓝筹收紧(1.5)
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


def calculate_adaptive_lookback(
    data: pd.DataFrame,
    min_lookup: int = 10,
    max_lookup: int = 60,
    turnover_col: str = None,
) -> Dict[str, Any]:
    """
    根据A股个股换手率，动态计算自适应震荡检测周期（docs/gemmi_an.md 核心算法）

    核心准则: 时间周期只是表象，资金换手周期才是本质。
    让筹码完成一次充分的换手（Turnover Cycle）作为检测窗口锚定点。

    :param data: 含换手率的日线DataFrame
    :param min_lookup: 最小检测周期限制（防止妖股周期太短导致统计失真）
    :param max_lookup: 最大检测周期限制（防止大盘股周期太长导致信号完全滞后）
    :param turnover_col: 换手率列名（默认自动识别'换手率'/'turnover_rate'/'turn'）
    :return: {adaptive_n, avg_turnover, theoretical_n, min_lookup, max_lookup}
    """
    result = {
        'adaptive_n': None,   # 最终自适应检测周期（交易日数）
        'avg_turnover': None, # 近20日日均换手率(%)
        'theoretical_n': None,  # 70%筹码换手理论天数
        'min_lookup': min_lookup,
        'max_lookup': max_lookup,
    }

    if data is None or len(data) < 20:
        result['adaptive_n'] = 30  # 数据不足默认30
        result['detail'] = '数据不足20日，使用默认周期30'
        return result

    # 识别换手率列
    if turnover_col is None:
        for candidate in ['换手率', 'turnover_rate', 'turn']:
            if candidate in data.columns:
                turnover_col = candidate
                break
    if turnover_col is None or turnover_col not in data.columns:
        result['adaptive_n'] = 30
        result['detail'] = f'缺少换手率列({turnover_col})，使用默认周期30'
        return result

    # 1. 计算过去20天的日均换手率（避免单日异动干扰）
    turnover = pd.to_numeric(data[turnover_col], errors='coerce')
    avg_turnover = turnover.tail(20).mean()

    if pd.isna(avg_turnover) or avg_turnover <= 0:
        result['adaptive_n'] = 30
        result['detail'] = '换手率数据异常，使用默认周期30'
        return result

    # 2. 根据70%筹码换手率公式计算理论天数（A股常有锁仓筹码，取70%为标准）
    theoretical_n = 70.0 / avg_turnover

    # 3. clip限制在合理区间 + 转整数
    adaptive_n = int(round(np.clip(theoretical_n, min_lookup, max_lookup)))

    result['adaptive_n'] = adaptive_n
    result['avg_turnover'] = round(float(avg_turnover), 2)
    result['theoretical_n'] = round(float(theoretical_n), 1)
    result['detail'] = (
        f"换手率自适应周期: 近20日日均换手{avg_turnover:.2f}%, "
        f"理论N={theoretical_n:.1f}日, 自适应N={adaptive_n}日"
    )
    return result


def calculate_adaptive_vap_atr(
    data: pd.DataFrame,
    n: int = 60,
    atr_m: int = 14,
    k: float = 1.8,
    market_type: str = "MainBoard",
) -> pd.DataFrame:
    """
    自适应 VAP-ATR 平台中枢计算（专为A股优化，适配T+1与涨跌停机制）

    :param data: 含 收盘价/最高价/最低价/开盘价/成交量 的日线DataFrame
    :param n: POC筹码分布窗口（默认60日）
    :param atr_m: ATR计算窗口（默认14）
    :param k: 波动率乘数（A股主板默认1.8，创业板/科创板可调）
    :param market_type: 'MainBoard'(主板10%) 或 'ChiNext_STAR'(创业板/科创板20%)
    :return: 增加 poc/platform_upper/platform_lower/is_breakout 等列的DataFrame
    """
    df = data.copy()

    # 列名兼容（支持英文列名）
    col_close = '收盘价' if '收盘价' in df.columns else 'close'
    col_high = '最高价' if '最高价' in df.columns else 'high'
    col_low = '最低价' if '最低价' in df.columns else 'low'
    col_open = '开盘价' if '开盘价' in df.columns else 'open'
    col_vol = '成交量' if '成交量' in df.columns else 'volume'

    # 1. 确定涨停板阈值
    limit_ratio = 0.20 if market_type == "ChiNext_STAR" else 0.10

    # 2. 计算修正后的 MTR (Modified True Range, 防止封板导致波动率归零)
    prev_close = df[col_close].shift(1)
    raw_tr = np.maximum(
        df[col_high] - df[col_low],
        np.maximum(
            (df[col_high] - prev_close).abs(),
            (df[col_low] - prev_close).abs(),
        ),
    )

    # 判定是否封涨停（收盘价 >= 昨收 × (1+涨跌幅限制)，四舍五入到分）
    is_limit_up = df[col_close] >= np.round(
        prev_close * (1 + limit_ratio), 2
    )

    # 封涨停时 TR 用过去14日均值替代（防止自适应箱体上下轨瞬间塌陷）
    ma_tr = raw_tr.rolling(window=atr_m, min_periods=1).mean()
    df['mtr'] = np.where(is_limit_up.fillna(False), ma_tr, raw_tr)
    df['matr'] = df['mtr'].rolling(window=atr_m).mean()

    # 3. 计算A股筹码重心价格（避免长上影线误导中枢）
    #    防止分母为0（一字板情况）
    price_range = df[col_high] - df[col_low]
    price_range = np.where(price_range == 0, 0.001, price_range)

    gravity = (df[col_close] - df[col_low]) / price_range
    df['gravity'] = gravity
    df['p_core'] = df[col_low] + gravity * (df[col_high] - df[col_low])

    # 4. 滚动计算基于重心的 VAP 筹码控制点 (POC)
    #    使用简化直方图分箱模拟KDE积分（50个价格档位，向量化高效实现）
    def get_cn_poc(window_df: pd.DataFrame) -> float:
        if len(window_df) < n:
            return np.nan
        bins = np.linspace(window_df['p_core'].min(), window_df['p_core'].max(), 50)
        hist, bin_edges = np.histogram(
            window_df['p_core'], bins=bins, weights=window_df[col_vol]
        )
        max_idx = np.argmax(hist)
        return float((bin_edges[max_idx] + bin_edges[max_idx + 1]) / 2)

    # 滚动应用（效率优化：仅对窗口起始位置计算）
    poc_series = []
    for i in range(len(df)):
        if i < n - 1:
            poc_series.append(np.nan)
        else:
            window = df.iloc[i - n + 1: i + 1]
            poc_series.append(get_cn_poc(window))
    df['poc'] = poc_series

    # 5. 构建自适应通道上下轨
    df['platform_upper'] = df['poc'] + k * df['matr']
    df['platform_lower'] = df['poc'] - k * df['matr']

    # 6. 生成A股专属突破信号（实体突破，排除长上影虚假突破）
    #    条件: 收盘价>上轨 且 阳线 且 重心>0.5 且 非前一交易日涨停
    is_breakout = (
        (df[col_close] > df['platform_upper'])
        & (df[col_close] > df[col_open])   # 必须是阳线
        & (gravity > 0.5)                  # 重心偏上，证明不是长上影假突破
        & (~is_limit_up.shift(1).fillna(False))  # 排除前一日一字板复牌后的首日情绪溢价
    )
    df['is_breakout'] = is_breakout.fillna(False)

    return df


def analyze_adaptive_platform(
    data: pd.DataFrame,
    stock_code: str = "",
    n: int = None,
    atr_m: int = None,
    k: float = None,
) -> Dict[str, Any]:
    """
    自适应平台分析入口（供主流程调用）

    :param data: 含 收盘价/最高价/最低价/开盘价/成交量/换手率 的日线DataFrame
    :param stock_code: 股票代码（用于判断主板/创业板/科创板，决定涨停阈值）
    :param n: POC窗口（None=自动按换手率自适应，见 calculate_adaptive_lookback）
    :param atr_m: ATR窗口（None=自适应: clip(round(n/4), 10, 14)，双周期嵌套快窗口）
    :param k: 波动率乘数（None=按换手率自适应: 高换手活跃股2.2/默认1.8/低换手蓝筹1.5）
    :return: 分析结果字典
    """
    result = {
        '平台方式': '自适应VAP-ATR',
        'POC': None,
        '自适应上轨': None,
        '自适应下轨': None,
        'ATR': None,
        '突破信号': False,
        '平台范围': None,
        '自适应周期': None,   # gemmi_an.md: 换手率自适应检测周期
        '详情': [],
    }

    if data is None or len(data) < 30:
        result['详情'].append("数据不足30日，无法计算自适应平台")
        return result

    # 判断市场类型（创业板300/301、科创板688 为20%涨跌幅）
    code_str = str(stock_code)
    # 去除 sh/sz 前缀，取6位数字代码判断
    digits = ''.join(ch for ch in code_str if ch.isdigit())[:6]
    if digits.startswith(('300', '301', '688')):
        market_type = "ChiNext_STAR"
    else:
        market_type = "MainBoard"

    # ===== 换手率自适应检测周期（gemmi_an.md） =====
    adaptive_info = calculate_adaptive_lookback(data)
    adaptive_n = adaptive_info.get('adaptive_n')
    if n is None:
        n = adaptive_n if adaptive_n else 30
    if atr_m is None:
        # 快窗口: clip(round(n/4), 10, 14)，双周期嵌套中的波动率快窗口
        atr_m = int(np.clip(round(n / 4), 10, 14))
    if k is None:
        # k 自适应: 高换手活跃股放宽(2.2), 低换手蓝筹收紧(1.5)
        avg_turnover = adaptive_info.get('avg_turnover')
        if avg_turnover is not None:
            if avg_turnover >= 10:
                k = 2.2
            elif avg_turnover >= 3:
                k = 1.8
            else:
                k = 1.5
        else:
            k = 1.8

    try:
        df = calculate_adaptive_vap_atr(data, n=n, atr_m=atr_m, k=k, market_type=market_type)

        # 取最新值
        latest = df.iloc[-1]
        poc = latest.get('poc')
        upper = latest.get('platform_upper')
        lower = latest.get('platform_lower')
        atr_val = latest.get('matr')
        is_brk = bool(latest.get('is_breakout', False))

        # 记录自适应周期信息
        result['自适应周期'] = {
            'adaptive_n': n,
            'atr_m': atr_m,
            'k': k,
            'avg_turnover': adaptive_info.get('avg_turnover'),
            'theoretical_n': adaptive_info.get('theoretical_n'),
        }

        if pd.notna(poc) and pd.notna(upper) and pd.notna(lower):
            result['POC'] = round(float(poc), 2)
            result['自适应上轨'] = round(float(upper), 2)
            result['自适应下轨'] = round(float(lower), 2)
            result['ATR'] = round(float(atr_val), 4) if pd.notna(atr_val) else None
            result['突破信号'] = is_brk
            result['平台范围'] = {
                '上沿': round(float(upper), 2),
                '下沿': round(float(lower), 2),
                'POC': round(float(poc), 2),
                '周期': n,
                '方式': '自适应VAP-ATR',
            }
            # 自适应周期说明（换手率驱动）
            if adaptive_info.get('detail'):
                result['详情'].append(adaptive_info['detail'])
            result['详情'].append(
                f"自适应平台: POC={poc:.2f}, 上轨={upper:.2f}, 下轨={lower:.2f}"
                f" (慢窗口{n}日, 快ATR{atr_m}日, k={k})"
            )
            if is_brk:
                result['详情'].append(
                    f"✅ 实体突破上轨: 收盘价>上轨 且 阳线 且 重心>0.5"
                )
            else:
                result['详情'].append("未突破自适应上轨（需收盘价>上轨且阳线且重心>0.5）")
        else:
            result['详情'].append(f"POC数据不足（需{n}日以上数据）")

    except Exception as e:
        result['详情'].append(f"自适应平台计算异常: {e}")

    return result


# 兼容旧名
def cns_adaptive_vap_atr(
    df: pd.DataFrame, n: int = 60, atr_m: int = 14, k: float = 1.8, market_type: str = "MainBoard"
) -> pd.DataFrame:
    """兼容 docs/design.md 中的函数名"""
    return calculate_adaptive_vap_atr(df, n=n, atr_m=atr_m, k=k, market_type=market_type)
