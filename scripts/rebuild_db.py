#!/usr/bin/env python3
# rebuild_db.py - 清除本地所有缓存并重建数据库（一键重建脚本）
"""
用法（docs/README 重建指南）:
  python scripts/rebuild_db.py               # 删除全部缓存 + 重建空库（不重新同步）
  python scripts/rebuild_db.py --sync        # 删除 + 重建 + 全量重新同步行情(5208只)
  python scripts/rebuild_db.py --sync --days 2000   # 指定同步回溯天数
  python scripts/rebuild_db.py --dry-run     # 预览将删除的文件（不实际删除）
  python scripts/rebuild_db.py --yes         # 跳过确认提示（无人值守）

说明:
  - 删除范围: 生产库(MYSTERY_DB_PATH) / 开发缓存 / 扫描结果独立库 /
    前端JSON(scan_results/watchlist) / 同步断点(checkpoint)
  - 重建: SQLite 空 schema（首次访问自动建表）
  - 建议先停止 Web 服务再执行: sudo systemctl stop mystery-web
  - 财务/行业板块在分析时按需自动拉取，无需手动同步
"""
import argparse
import logging
import os
import shutil
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger('rebuild')

# 项目根（scripts/ 的上一级）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def collect_targets() -> list:
    """收集所有待删除的缓存/数据库文件（env 感知）"""
    targets = []
    # 1. 生产库（MYSTERY_DB_PATH 优先，否则默认路径）
    prod_db = os.environ.get('MYSTERY_DB_PATH') or os.path.join(
        ROOT, 'data', 'mystery_cache.db')
    targets.append(prod_db)
    # 2. 开发缓存（默认路径，可能与生产库同路径——去重）
    dev_db = os.path.join(ROOT, 'data', 'mystery_cache.db')
    if dev_db != prod_db:
        targets.append(dev_db)
    # 3. 扫描结果独立库（与主库同目录）
    targets.append(os.path.join(os.path.dirname(prod_db), 'scan_results.db'))
    # 4. 前端 JSON 缓存
    targets.append(os.path.join(ROOT, 'web', 'data', 'scan_results.json'))
    targets.append(os.path.join(ROOT, 'web', 'data', 'watchlist.json'))
    # 5. 同步断点
    targets.append(os.path.join(ROOT, 'data', 'sync_checkpoint.json'))
    # 去重 + 过滤存在的
    seen = set()
    result = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            if os.path.exists(t):
                result.append(t)
    return result


def rebuild_schema():
    """重建空 schema（db_manager 建表）"""
    sys.path.insert(0, os.path.join(ROOT, 'data'))
    sys.path.insert(0, ROOT)
    from data.db_manager import MysteryDB
    db = MysteryDB()
    conn = db._connect()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    logger.info(f"✅ 数据库已重建: {db.db_path}")
    logger.info(f"   表: {tables}")
    return tables


def run_sync(days: int):
    """全量重新同步行情（子进程，本地 .day 优先）"""
    logger.info(f"🚀 开始全量行情同步（--days {days}，本地优先，约 10-15 分钟）...")
    cmd = [sys.executable, os.path.join(ROOT, 'data', 'sync_all_market.py'),
           '--period', 'daily', '--days', str(days), '--no-progress']
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode == 0:
        logger.info("✅ 行情同步完成")
    else:
        logger.error(f"❌ 行情同步失败 (exit={r.returncode})")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='清除本地所有缓存并重建数据库')
    parser.add_argument('--sync', action='store_true',
                        help='重建后全量重新同步行情')
    parser.add_argument('--days', type=int, default=1100,
                        help='同步回溯天数（--sync 时生效）')
    parser.add_argument('--dry-run', action='store_true',
                        help='仅预览将删除的文件，不实际执行')
    parser.add_argument('--yes', action='store_true', help='跳过确认提示')
    args = parser.parse_args()

    targets = collect_targets()
    if not targets:
        logger.info("📋 无缓存文件需要删除（数据库已干净）")
    else:
        logger.info("📋 将删除以下文件:")
        for t in targets:
            size = os.path.getsize(t) / 1024 / 1024
            logger.info(f"   - {t} ({size:.1f} MB)")
        if args.dry_run:
            logger.info("🔍 dry-run 模式：未执行任何删除")
            return
        if not args.yes:
            ans = input("确认删除并重建? [y/N] ").strip().lower()
            if ans != 'y':
                logger.info("已取消")
                return
        for t in targets:
            os.remove(t)
            logger.info(f"🗑️  已删除: {t}")

    # 重建空 schema
    tables = rebuild_schema()

    # 重新同步（可选）
    if args.sync:
        run_sync(args.days)
    else:
        logger.info("💡 未指定 --sync：财务/行业板块在分析时按需自动拉取。")
        logger.info("   如需重建后立即重新同步行情，请运行: "
                    "python scripts/rebuild_db.py --sync")

    logger.info("\n🎉 数据库重建完成！")
    logger.info("   - 如 Web 服务运行中，请重启加载新库: "
                "sudo systemctl restart mystery-web")


if __name__ == '__main__':
    main()
