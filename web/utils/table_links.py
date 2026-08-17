#!/usr/bin/env python3
# table_links.py - 股票代码列 → 个股分析跳转链接
"""把表格中的"股票代码"列渲染为可点击链接（跨页跳转到 个股分析?code=xxx）"""
import pandas as pd
import streamlit as st


def code_column_config(code_col: str = "股票代码"):
    """返回 LinkColumn 配置：代码列显示为链接（兼容 股票代码/代码 别名）"""
    return {code_col: st.column_config.LinkColumn(
        f"{code_col}（点击分析）")}


def link_code_column(df: pd.DataFrame, code_col: str = None) -> pd.DataFrame:
    """把 代码列 值转为跳转 URL（相对路径: 个股分析?code=sh600150）
    :param df: 含代码列的 DataFrame（原样拷贝，不修改原对象）
    :param code_col: 代码列名（默认自动识别 股票代码/代码）
    :return: 转换后的副本（代码列已是 URL 字符串）
    """
    if df is None or df.empty:
        return df
    if code_col is None:
        code_col = '股票代码' if '股票代码' in df.columns else (
            '代码' if '代码' in df.columns else None)
    if not code_col:
        return df
    out = df.copy()
    out[code_col] = out[code_col].map(
        lambda c: f"个股分析?code={c}")
    return out


def render_code_link_table(df: pd.DataFrame, code_col: str = None,
                           **kwargs) -> None:
    """渲染表格：代码列自动变为跳转链接（其余列原样）"""
    cc = code_col or ('股票代码' if (df is not None and
                                     '股票代码' in df.columns) else
                      ('代码' if (df is not None and '代码' in df.columns)
                       else None))
    out = link_code_column(df, cc)
    if cc:
        st.dataframe(out, column_config=code_column_config(cc), **kwargs)
    else:
        st.dataframe(df, **kwargs)
