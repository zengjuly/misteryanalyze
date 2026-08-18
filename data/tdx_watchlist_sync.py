#!/usr/bin/env python3
# tdx_watchlist_sync.py - 通达信自选股同步（docs 2026-08-17 自选股从TDX安装目录同步）
"""从通达信安装目录 T0002/blocknew/zxg.blk 解析自选股 → 写入 watchlist 表

- 支持 TDX_HOME 环境变量 / config tdx.home_dir 定位安装目录
- zxg.blk 文本格式: 每行 = 市场数字前缀 + 6位代码
  （0=深、1=沪、2/3位前缀如 16/03 按代码首位推断市场）
- 同步策略: 全量替换（TDX 为准）或增量合并（保留手动添加）
"""
import logging
import os
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# 自选股相对路径（通达信标准: T0002/blocknew/zxg.blk）
ZXG_REL = os.path.join('T0002', 'blocknew', 'zxg.blk')


def resolve_tdx_home() -> Optional[str]:
    """定位通达信安装目录: env TDX_HOME > config tdx.home_dir > None"""
    env = os.environ.get('TDX_HOME')
    if env and os.path.isdir(env):
        return env
    try:
        import yaml
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg_path = os.path.join(base, 'config', 'config.yaml')
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            home = (cfg.get('tdx') or {}).get('home_dir')
            if home and os.path.isdir(home):
                return home
    except Exception as e:
        logger.debug(f"读取 config tdx.home_dir 失败: {e}")
    return None


def find_zxg_file() -> Optional[str]:
    """定位 zxg.blk（优先 TDX_HOME，其次常见备选位置）"""
    home = resolve_tdx_home()
    candidates = []
    if home:
        candidates.append(os.path.join(home, ZXG_REL))
    # 备选: T0002/blocknew 直接路径
    candidates.append('/mnt/new_tdx/T0002/blocknew/zxg.blk')
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def parse_zxg(path: str = None) -> List[str]:
    """解析 zxg.blk → 标准代码列表（sh600150 无点格式）
    :param path: zxg.blk 路径（None 自动定位）
    :return: ['sh600150', 'sz000915', ...]（空列表=文件缺失/解析失败）
    """
    path = path or find_zxg_file()
    if not path:
        logger.info("⚠️ 未找到通达信自选股文件 zxg.blk")
        return []
    try:
        text = open(path, 'rb').read().decode('gbk', errors='replace')
    except Exception as e:
        logger.warning(f"⚠️ 读取 zxg.blk 失败: {e}")
        return []
    codes = []
    for ln in text.split():
        ln = ln.strip()
        if not ln or len(ln) < 6:
            continue
        code6 = ln[-6:]
        if not code6.isdigit():
            continue
        prefix = ln[:-6]
        # 市场判定: 显式前缀 0=深 1=沪；否则按代码首位
        if prefix and prefix[-1] == '0':
            mkt = 'sz'
        elif prefix and prefix[-1] == '1':
            mkt = 'sh'
        else:
            mkt = 'sh' if code6.startswith(('6', '9', '5')) else (
                'sz' if code6.startswith(('0', '2', '3')) else 'bj')
        # 过滤非股票: 88/99/98 开头是概念指数（如 881418），非个股
        if code6.startswith(('88', '99', '98')):
            continue
        # 过滤基金/ETF: 15/16/18 开头=深市基金(如159742)，5 开头=沪市基金
        if code6.startswith(('15', '16', '18', '5')):
            continue
        codes.append(f"{mkt}{code6}")
    return codes


def sync_from_tdx(mode: str = 'merge', name_map: dict = None) -> dict:
    """从通达信同步自选股到 watchlist 表
    :param mode: 'merge'=增量合并（保留手动添加）；'replace'=全量替换（TDX为准）
    :param name_map: {code: name} 名称字典（None 时不填名称，仅代码）
    :return: {'synced': 新增数, 'total': TDX 总数, 'watchlist': 同步后总数,
              'codes': TDX代码列表}
    """
    codes = parse_zxg()
    if not codes:
        return {'synced': 0, 'total': 0, 'watchlist': 0, 'codes': []}
    # 兼容两种导入路径（data/ 目录直跑 与 data.xxx 包导入）
    try:
        from watchlist_manager import WatchlistManager
    except ImportError:
        from data.watchlist_manager import WatchlistManager
    wm = WatchlistManager()
    existing = set(wm.codes())
    added = 0
    for c in codes:
        if c not in existing:
            db_code = c[:2] + '.' + c[2:]
            name = ''
            if name_map:
                name = name_map.get(c, name_map.get(db_code, ''))
            wm.add(db_code, name=name, source='tdx_sync')
            added += 1
    if mode == 'replace':
        # 删除 TDX 之外的自选（保留 source='manual' 手动项? replace=全清再同步）
        keep = set(codes)
        for old in existing:
            if old not in keep:
                wm.remove(old)
    total = wm.count()
    logger.info(f"📂 TDX 自选股同步: 解析{len(codes)}只，新增{added}只，"
                f"同步后共{total}只（{mode}）")
    return {'synced': added, 'total': len(codes),
            'watchlist': total, 'codes': codes}
