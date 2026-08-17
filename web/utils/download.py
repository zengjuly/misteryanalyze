#!/usr/bin/env python3
# download.py - Web 页面 Excel 下载工具（多 sheet 导出）
"""统一的 Excel 导出：把分析结果 DataFrame 转成多 sheet xlsx 字节流，
供 st.download_button 下载（避免各页面重复写 BytesIO/openpyxl 逻辑）"""
import io

import pandas as pd
import streamlit as st


def df_to_excel_bytes(df: pd.DataFrame, sheets: dict = None,
                      sheet_name: str = '数据') -> bytes:
    """DataFrame → xlsx 字节流（支持多 sheet）
    :param df: 主 DataFrame（sheet_name 指定名称）
    :param sheets: 可选附加 sheet {名称: DataFrame}（覆盖主表同名）
    :param sheet_name: 主表 sheet 名
    :return: xlsx bytes（可直接 .download_button(data=...)）
    """
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        # 主表
        if df is not None and not df.empty:
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        # 附加 sheet
        for name, sdf in (sheets or {}).items():
            if sdf is not None and not sdf.empty:
                sdf.to_excel(writer, sheet_name=name[:31], index=False)
    buf.seek(0)
    return buf.getvalue()


def excel_download_button(df: pd.DataFrame, file_name: str,
                          button_label: str = "📥 导出 Excel",
                          sheets: dict = None,
                          sheet_name: str = '数据',
                          key: str = None,
                          help: str = None) -> bool:
    """渲染一个 Excel 下载按钮
    :param df: 主 DataFrame
    :param file_name: 下载文件名（.xlsx 结尾）
    :param sheets: 附加 sheet {名称: DataFrame}
    :return: 是否点击（bool）
    """
    if df is None or df.empty:
        return False
    data = df_to_excel_bytes(df, sheets=sheets, sheet_name=sheet_name)
    return st.download_button(
        button_label, data, file_name, "application/vnd.openxmlformats-"
        "officedocument.spreadsheetml.sheet",
        key=key, help=help, width="stretch")
