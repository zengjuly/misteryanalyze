#!/usr/bin/env python3
# sync_sector_data.py - 行业板块指数流式同步引擎（docs/082202.md 阶段一）
"""拉取同花顺扶摇真实板块指数K线（index-catalog + index-historical）存入
sector_kline/sector_meta 表——替代个股抽样，杜绝样本失真。

用法:
  python data/sync_sector_data.py                 # 全量同步（断点续传）
  python data/sync_sector_data.py --days 1100     # 指定回溯天数
  python data/sync_sector_data.py --limit 10      # 仅前N个板块（测试）
  python data/sync_sector_data.py --force         # 忽略断点全量重拉

输出（Token 极简信封）:
  [Sector Sync Summary] 成功同步 N/M 个官方行业板块真实指数至本地 (sector_kline)
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING,
                    format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger('sync_sector')


def main():
    ap = argparse.ArgumentParser(description='板块指数同步（docs/082202.md）')
    ap.add_argument('--days', type=int, default=1100, help='回溯天数')
    ap.add_argument('--limit', type=int, default=None, help='仅前N板块(测试)')
    ap.add_argument('--force', action='store_true', help='忽略断点全量')
    args = ap.parse_args()

    import yaml
    from data.db_manager import MysteryDB
    from data.ths_client import ThsOfficialClient

    # 配置
    cfg = yaml.safe_load(open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config', 'config.yaml')))
    db = MysteryDB()
    ths = ThsOfficialClient(cfg)

    # 1. 板块目录（index-catalog 真实行业/概念指数）
    logger.info('📋 获取板块目录（index-catalog）...')
    catalogs = ths._run_fuyao(['index-catalog'])
    if not catalogs:
        print('[Sector Sync Summary] ❌ index-catalog 获取失败，终止')
        return 1
    sectors = []
    for cat in catalogs:
        code = cat.get('thscode') or cat.get('index_code')
        name = cat.get('name') or cat.get('index_name')
        if code and name:
            sectors.append((code, name))
    if args.limit:
        sectors = sectors[:args.limit]
    logger.info(f'📋 共 {len(sectors)} 个板块待同步')

    # 2. 断点续传（sector_meta.last_sync_date）
    meta = {r[0]: r[2] for r in db.get_sector_meta()}
    today = datetime.now().strftime('%Y-%m-%d')

    success = 0
    t0 = time.time()
    for code, name in sectors:
        sector_code = f"ths_{code.split('.')[0]}"
        last_date = meta.get(sector_code)
        if last_date and not args.force:
            # 已同步到今天 → 跳过（增量）
            if last_date >= today:
                continue
            start = (datetime.strptime(last_date, '%Y-%m-%d')
                     - timedelta(days=3)).strftime('%Y-%m-%d')
        else:
            start = (datetime.now()
                     - timedelta(days=args.days)).strftime('%Y-%m-%d')
        end = today
        try:
            df = ths.fetch_index_hist(code, start_date=start, end_date=end)
            if df is None or df.empty:
                logger.debug(f'⏭️ {name} 无数据，跳过')
                continue
            # 3. 落库（幂等 INSERT OR REPLACE）
            db.upsert_sector_meta(sector_code, name,
                                  parent_type='行业/概念',
                                  base_code=code.split('.')[0])
            n = db.save_sector_kline(sector_code, name, df,
                                     source_type='ths')
            db.update_sector_sync_date(sector_code, today)
            success += 1
            if success % 20 == 0:
                logger.info(f'⏳ 已同步 {success}/{len(sectors)} ...')
        except Exception as e:
            logger.warning(f'❌ {name}({code}) 同步失败: {str(e)[:80]}')
            continue

    elapsed = time.time() - t0
    # 4. Token 极简摘要信封（docs/082202.md 阶段三）
    print(f'[Sector Sync Summary] 成功同步 {success}/{len(sectors)} 个官方'
          f'行业板块真实指数至本地 (sector_kline)，耗时 {elapsed:.0f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
