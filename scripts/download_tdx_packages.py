#!/usr/bin/env python3
# download_tdx_packages.py - 通达信官方数据包下载脚本（基于docs/tdx.md方案）
"""
通达信官方数据包下载与解压
==========================
下载 hsjday.zip(历史日线) / tdxfin.zip(财务) / tdxgp.zip(股票列表)
解压至 TDX_VIPDOC_DIR（默认 /home/ai/ai_runner/stock/data/tdx_vipdoc，Git仓库外）

用法:
  python scripts/download_tdx_packages.py            # 下载全部
  python scripts/download_tdx_packages.py --pkg hsjday  # 仅下载日线
  TDX_VIPDOC_DIR=/path python scripts/download_tdx_packages.py  # 自定义目录
"""

import argparse
import io
import logging
import os
import sys
import zipfile

import requests

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger('download_tdx')

# 通达信官方数据包
BASE_URL = "https://data.tdx.com.cn/vipdoc/"
PACKAGES = {
    "hsjday": "hsjday.zip",   # 历史日线
    "tdxfin": "tdxfin.zip",   # 财务数据
    "tdxgp": "tdxgp.zip",     # 股票列表
}

# 默认目标目录（仓库外，可用环境变量覆盖）
DEST_DIR = os.getenv("TDX_VIPDOC_DIR",
                     "/home/ai/ai_runner/stock/data/tdx_vipdoc")


def _safe_extract(z: zipfile.ZipFile, dest: str) -> int:
    """
    安全解压：通达信zip内路径用反斜杠'\\'分隔（Windows风格），
    Linux下 zipfile.extractall 会把整个路径当文件名解压成扁平文件
    （历史bug: 12345个 .day 文件变成 'sh\\lday\\sh600150.day' 文件名）。
    本函数将反斜杠替换为正斜杠，按目录结构解压，并防zip slip。
    :return: 解压文件数
    """
    count = 0
    for member in z.infolist():
        # 反斜杠路径 → 正斜杠目录结构
        name = member.filename.replace('\\', '/')
        # zip slip 防护
        if name.startswith('/') or '..' in name.split('/'):
            logger.warning(f"⚠️ 跳过危险路径: {member.filename}")
            continue
        target = os.path.join(dest, name)
        if member.is_dir():
            os.makedirs(target, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with z.open(member) as src, open(target, 'wb') as dst:
            dst.write(src.read())
        count += 1
    return count


def fix_flat_structure(dest: str) -> int:
    """
    修复历史遗留扁平结构: 'sh\\lday\\sh600150.day' 扁平文件名
    → 'sh/lday/sh600150.day' 目录结构（幂等，可重复执行）
    :return: 修复文件数
    """
    moved = 0
    if not os.path.isdir(dest):
        return 0
    for f in os.listdir(dest):
        if '\\' not in f:
            continue
        src = os.path.join(dest, f)
        if not os.path.isfile(src):
            continue
        rel = f.replace('\\', '/')
        dst = os.path.join(dest, rel)
        if os.path.exists(dst):
            logger.warning(f"⚠️ 目标已存在，跳过: {rel}")
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.rename(src, dst)
        moved += 1
    if moved:
        logger.info(f"🔧 扁平结构修复 {moved} 个文件 → 标准目录结构")
    return moved


def download_and_extract(pkg_name: str) -> bool:
    """下载并解压单个数据包"""
    url = BASE_URL + PACKAGES[pkg_name]
    dest = os.path.join(DEST_DIR, pkg_name)
    try:
        logger.info(f"⬇️  下载 {pkg_name}: {url}")
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        logger.info(f"  下载完成 {len(resp.content)/1024/1024:.1f}MB，解压中...")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            n = _safe_extract(z, DEST_DIR)
        logger.info(f"✅ {pkg_name} 解压完成 {n} 个文件 → {DEST_DIR}")
        return True
    except Exception as e:
        logger.error(f"❌ {pkg_name} 下载/解压失败: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='通达信官方数据包下载')
    parser.add_argument('--pkg', choices=list(PACKAGES.keys()) + ['all'],
                        default='all', help='数据包: hsjday/tdxfin/tdxgp/all')
    parser.add_argument('--fix-flat', action='store_true',
                        help='修复历史遗留扁平结构(反斜杠文件名→目录结构)')
    args = parser.parse_args()

    os.makedirs(DEST_DIR, exist_ok=True)
    print(f"📂 目标目录: {DEST_DIR}")

    if args.fix_flat:
        n = fix_flat_structure(DEST_DIR)
        print(f"🔧 扁平结构修复: {n} 个文件")

    if args.pkg == 'all':
        results = {p: download_and_extract(p) for p in PACKAGES}
        ok = sum(results.values())
        print(f"\n📊 下载结果: {ok}/{len(PACKAGES)} 成功")
        for p, s in results.items():
            print(f"  {'✅' if s else '❌'} {p}")
        sys.exit(0 if ok == len(PACKAGES) else 1)
    else:
        ok = download_and_extract(args.pkg)
        sys.exit(0 if ok else 1)
