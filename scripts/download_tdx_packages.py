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
            z.extractall(DEST_DIR)
        logger.info(f"✅ {pkg_name} 解压完成 → {DEST_DIR}")
        return True
    except Exception as e:
        logger.error(f"❌ {pkg_name} 下载/解压失败: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='通达信官方数据包下载')
    parser.add_argument('--pkg', choices=list(PACKAGES.keys()) + ['all'],
                        default='all', help='数据包: hsjday/tdxfin/tdxgp/all')
    args = parser.parse_args()

    os.makedirs(DEST_DIR, exist_ok=True)
    print(f"📂 目标目录: {DEST_DIR}")

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
