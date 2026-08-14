#!/usr/bin/env python3
# path_utils.py - 路径解析工具（环境变量优先，基于docs/step3.md阶段3优化）
"""
路径解析工具
============
理论来源: docs/step3.md（阶段3完整生产化方案 - 路径与环境变量优先）

统一路径解析规则: 环境变量 > 配置值 > 默认值
提升跨环境可移植性（同一套代码适配不同部署环境）。

用法:
  from utils.path_utils import resolve_path
  vipdoc = resolve_path('TDX_VIPDOC_DIR', cfg.get('vipdoc_dir'),
                        'data/tdx_vipdoc')
"""

import os
from typing import Optional


def resolve_path(env_key: str, config_value: Optional[str] = None,
                 default: str = 'data/tdx_vipdoc') -> str:
    """
    解析路径：环境变量优先，其次配置值，最后默认值
    :param env_key: 环境变量名（如 TDX_VIPDOC_DIR）
    :param config_value: 配置文件中的值（可为None）
    :param default: 默认值
    :return: 解析后的路径字符串
    """
    if env_key and env_key in os.environ and os.environ[env_key].strip():
        return os.environ[env_key].strip()
    if config_value:
        return str(config_value)
    return default


def resolve_path_abs(env_key: str, config_value: Optional[str] = None,
                     default: str = 'data/tdx_vipdoc',
                     base_dir: Optional[str] = None) -> str:
    """
    解析路径并转为绝对路径（相对路径基于 base_dir 或当前工作目录）
    :param base_dir: 相对路径的基准目录（默认 cwd）
    """
    path = resolve_path(env_key, config_value, default)
    if os.path.isabs(path):
        return path
    base = base_dir or os.getcwd()
    return os.path.abspath(os.path.join(base, path))


def get_env_or(env_key: str, fallback: str) -> str:
    """获取环境变量，缺失时返回 fallback（便捷包装）"""
    return os.environ.get(env_key, fallback) if env_key else fallback
