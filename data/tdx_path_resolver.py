#!/usr/bin/env python3
# tdx_path_resolver.py - 通达信本地数据路径解析与新鲜度判定（docs/tdx2.md）
"""
数据层"本地优先 + 过期回退"路径解析器
=====================================
规则（docs/tdx2.md §1/§2）:
  - 日K vipdoc: {home_dir}/vipdoc > 显式 vipdoc_dir（若含 lday）> TDX_VIPDOC_DIR > 默认
  - 财务: 仅 vipdoc_dir（及子目录 cw/）—— 绝不从 TDX_HOME 读
  - 板块: 仅 home_dir（T0002/blocknew）
  - 新鲜度: 日K=末根K线日期 / 财务=最新gpcw报告期或mtime
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# 默认值（docs/tdx2.md）
DEFAULT_TDX_HOME = "/mnt/new_tdx"
DEFAULT_VIPDOC_DIR = "/home/ai/ai_runner/stock/data/tdx_vipdoc"
DEFAULT_MAX_AGE = {"kline": 1, "block": 3, "financial": 30}

_CONFIG_CACHE = {}


def _load_config() -> dict:
    """加载 config/config.yaml 的 tdx 段（带缓存，避免重复读文件）"""
    if 'tdx' in _CONFIG_CACHE:
        return _CONFIG_CACHE['tdx']
    cfg = {}
    try:
        import yaml
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'config', 'config.yaml')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            cfg = data.get('tdx', {}) or {}
    except Exception as e:
        logger.warning(f"⚠️ 加载 tdx 配置失败: {e}")
    _CONFIG_CACHE['tdx'] = cfg
    return cfg


def resolve_home() -> str:
    """通达信安装/数据主目录（TDX_HOME）
    优先级: 环境变量 TDX_HOME > config tdx.home_dir > 默认
    """
    cfg = _load_config()
    return (os.environ.get('TDX_HOME')
            or cfg.get('home_dir')
            or DEFAULT_TDX_HOME)


def resolve_vipdoc_for_kline() -> str:
    """日K 数据目录（优先 home/vipdoc，否则显式 vipdoc_dir 若含 lday）
    优先级: {home_dir}/vipdoc > 显式 vipdoc_dir(含lday) > TDX_VIPDOC_DIR > 默认
    """
    cfg = _load_config()
    # 优先级: TDX_VIPDOC_DIR 环境变量 > config tdx.vipdoc_dir > 默认（tdx2 验收: env覆盖生效）
    explicit = (os.environ.get('TDX_VIPDOC_DIR')
                or cfg.get('vipdoc_dir')
                or DEFAULT_VIPDOC_DIR)
    # 1. home/vipdoc（若存在）
    home = resolve_home()
    home_vipdoc = os.path.join(home, 'vipdoc')
    if os.path.isdir(home_vipdoc):
        for mkt in ('sh', 'sz', 'bj'):
            if os.path.isdir(os.path.join(home_vipdoc, mkt, 'lday')):
                return home_vipdoc
    # 2. 显式 vipdoc_dir（本机实际结构: vipdoc 直接含 {sh,sz,bj}/lday）
    if os.path.isdir(explicit):
        for mkt in ('sh', 'sz', 'bj'):
            if os.path.isdir(os.path.join(explicit, mkt, 'lday')):
                return explicit
    # 3. 兜底返回显式值（目录可能尚未下载）
    return explicit


def resolve_vipdoc_for_fin() -> str:
    """财务数据目录（仅 VIPDOC，绝不读 TDX_HOME）
    优先级: config tdx.vipdoc_dir > TDX_VIPDOC_DIR > 默认
    """
    cfg = _load_config()
    # 优先级: TDX_VIPDOC_DIR 环境变量 > config tdx.vipdoc_dir > 默认
    return (os.environ.get('TDX_VIPDOC_DIR')
            or cfg.get('vipdoc_dir')
            or DEFAULT_VIPDOC_DIR)


def day_file_path(code6: str, kline_dir: Optional[str] = None) -> str:
    """日K .day 文件路径（{dir}/{mkt}/{code}.day，兼容 lday/ 子目录）"""
    kline_dir = kline_dir or resolve_vipdoc_for_kline()
    mkt = 'sh' if code6.startswith(('6', '9', '5')) else (
        'sz' if code6.startswith(('0', '2', '3')) else 'bj')
    return os.path.join(kline_dir, mkt, 'lday', f"{mkt}{code6}.day")


def _has_lday_structure(d: str) -> bool:
    """目录是否含 {sh,sz,bj}/lday 结构"""
    return os.path.isdir(d) and any(
        os.path.isdir(os.path.join(d, mkt, 'lday'))
        for mkt in ('sh', 'sz', 'bj'))


def resolve_kline_dirs() -> list:
    """日K目录优先级列表（用户要求: 优先 TDX_HOME，失败则 TDX_VIPDOC_DIR）
    :return: [home/vipdoc(若含lday), 显式vipdoc_dir(若含lday)] 去重；
             均无 lday 结构时兜底返回 [显式vipdoc_dir]
    """
    dirs = []
    home_vipdoc = os.path.join(resolve_home(), 'vipdoc')
    if _has_lday_structure(home_vipdoc):
        dirs.append(home_vipdoc)
    # 显式 vipdoc_dir 用 resolve_vipdoc_for_fin（纯 TDX_VIPDOC_DIR，无 home 逻辑，
    # 避免被 resolve_vipdoc_for_kline 的 home 优先抢占导致第二目录丢失）
    explicit = resolve_vipdoc_for_fin()
    if explicit not in dirs and _has_lday_structure(explicit):
        dirs.append(explicit)
    if not dirs:
        dirs.append(explicit)
    return dirs


def _read_day_last_date(day_file: str) -> Optional[str]:
    """读取 .day 文件末根K线日期（定长32字节/条，读尾部解析）
    :return: 'YYYY-MM-DD' 或 None（文件损坏/过短）
    """
    try:
        size = os.path.getsize(day_file)
        if size < 32:
            return None
        with open(day_file, 'rb') as f:
            f.seek(size - 32)
            raw = f.read(32)
        # 通达信 .day: 前4字节 = 日期（YYYYMMDD 的 int，如 20260814）
        import struct
        date_int = struct.unpack('<I', raw[0:4])[0]
        if date_int < 19900101 or date_int > 21000101:
            return None
        s = str(date_int)
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    except Exception as e:
        logger.debug(f"读取 .day 末日期失败 {day_file}: {e}")
        return None


def is_kline_fresh(day_file: str, max_age_days: int = None) -> bool:
    """日K新鲜度: 文件存在 且 末根K线日期在 max_age_days 内
    :return: True=新鲜; False=缺失/过期
    """
    if max_age_days is None:
        cfg = _load_config()
        max_age_days = cfg.get('freshness', {}).get(
            'kline_max_age_days', DEFAULT_MAX_AGE['kline'])
    if not os.path.exists(day_file):
        return False
    last_date = _read_day_last_date(day_file)
    if not last_date:
        return False
    try:
        last_dt = datetime.strptime(last_date, '%Y-%m-%d')
    except ValueError:
        return False
    # 工作日近似: 用自然日 + 周末缓冲（周五数据周一仍新鲜: 加2天缓冲）
    allowed = max_age_days + 2
    return (datetime.now() - last_dt).days <= allowed


def is_file_fresh(path: str, max_age_days: int = None,
                  kind: str = 'financial') -> bool:
    """文件 mtime 新鲜度（财务包等）"""
    if max_age_days is None:
        cfg = _load_config()
        key = f"{kind}_max_age_days"
        max_age_days = cfg.get('freshness', {}).get(
            key, DEFAULT_MAX_AGE.get(kind, 30))
    if not os.path.exists(path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.now() - mtime).days <= max_age_days


def latest_gpcw_report_period(fin_dir: str) -> Optional[str]:
    """扫描财务目录最新 gpcw 报告期（YYYYMMDD）
    兼容 {fin_dir}/gpcw*.dat 与 {fin_dir}/cw/gpcw*.dat 两种布局
    :return: 'YYYY-MM-DD' 或 None
    """
    import glob
    import re
    latest = None
    for base in (fin_dir, os.path.join(fin_dir, 'cw')):
        for p in glob.glob(os.path.join(base, 'gpcw*.dat')):
            m = re.search(r'gpcw(\d{8})\.dat', os.path.basename(p))
            if m:
                ymd = m.group(1)
                if latest is None or ymd > latest:
                    latest = ymd
    if not latest:
        return None
    return f"{latest[0:4]}-{latest[4:6]}-{latest[6:8]}"


def is_financial_fresh(fin_dir: str, max_age_days: int = None) -> bool:
    """财务新鲜度: 最新 gpcw 报告期 或 包 mtime 在 max_age_days 内"""
    if max_age_days is None:
        cfg = _load_config()
        max_age_days = cfg.get('freshness', {}).get(
            'financial_max_age_days', DEFAULT_MAX_AGE['financial'])
    period = latest_gpcw_report_period(fin_dir)
    if period:
        try:
            pd_dt = datetime.strptime(period, '%Y-%m-%d')
            # 报告期通常滞后（季报+45天），给 45 天缓冲
            if (datetime.now() - pd_dt).days <= max_age_days + 45:
                return True
        except ValueError:
            pass
    # 兜底: 任一 gpcw*.dat mtime 新鲜
    import glob
    for base in (fin_dir, os.path.join(fin_dir, 'cw')):
        for p in glob.glob(os.path.join(base, 'gpcw*.dat'))[:5]:
            if is_file_fresh(p, max_age_days):
                return True
    return False
