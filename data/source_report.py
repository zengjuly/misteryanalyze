#!/usr/bin/env python3
# source_report.py - 源健康报告生成（基于docs/step3.md阶段3优化-可观测性）
"""
源健康报告生成
==============
理论来源: docs/step3.md（阶段3完整生产化方案 - 可观测性）

功能:
  将 SourceHealth 的实时统计导出为 JSON 报告（含时间戳），
  便于运维监控与故障定位。可集成到每日任务/同步任务结束后自动调用。

用法:
  from source_report import generate_source_report
  path = generate_source_report(market_client.source_health)

  # CLI 方式（需提供健康统计来源）
  python data/source_report.py --help
"""

import json
import logging
import os
import time
from typing import Dict

logger = logging.getLogger(__name__)

# 报告默认输出目录（环境变量 SOURCE_REPORT_DIR 可覆盖）
DEFAULT_REPORT_DIR = os.environ.get(
    'SOURCE_REPORT_DIR', 'logs')


def generate_source_report(source_health, output_dir: str = None,
                           prefix: str = 'source_report') -> str:
    """
    生成源健康报告 JSON
    :param source_health: SourceHealth 实例（需有 get_source_stats()）
    :param output_dir: 输出目录（默认 logs/，环境变量 SOURCE_REPORT_DIR 覆盖）
    :param prefix: 文件名前缀
    :return: 报告文件绝对路径
    """
    if source_health is None:
        logger.warning("⚠️ source_health 为 None，跳过报告生成")
        return ''
    try:
        stats = source_health.get_source_stats()
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total_sources': len(stats),
                'open_sources': sum(1 for s in stats.values()
                                    if s.get('is_open', True)),
                'tripped_sources': sum(1 for s in stats.values()
                                       if not s.get('is_open', True)),
                'avg_health_score': round(sum(
                    s.get('health_score', 0) for s in stats.values())
                    / len(stats), 2) if stats else None,
            },
            'sources': {},
        }
        for src, s in stats.items():
            report['sources'][src] = {
                'success_count': s.get('success_count', 0),
                'failure_count': s.get('failure_count', 0),
                'consecutive_failures': s.get('consecutive_failures', 0),
                'health_score': round(s.get('health_score', 100.0), 2),
                'is_open': s.get('is_open', True),
                'avg_latency_ms': round(s.get('avg_latency_ms', 0.0), 1),
            }
        out_dir = output_dir or DEFAULT_REPORT_DIR
        os.makedirs(out_dir, exist_ok=True)
        filename = os.path.join(
            out_dir,
            f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"📊 源健康报告已生成: {filename}")
        return filename
    except Exception as e:
        logger.error(f"❌ 源健康报告生成失败: {e}")
        return ''


def report_from_stats(stats: Dict, output_dir: str = None,
                      prefix: str = 'source_report') -> str:
    """
    从统计 dict（非 SourceHealth 实例）生成报告（测试/调试用）
    :param stats: {'源名': {'success_count':..., 'health_score':..., ...}}
    """
    class _FakeHealth:
        def get_source_stats(self):
            return stats
    return generate_source_report(_FakeHealth(), output_dir, prefix)


if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description='源健康报告生成（需提供统计JSON或由上层集成调用）')
    parser.add_argument('--stats-json', type=str,
                        help='健康统计JSON文件（可选）')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='输出目录（默认 logs/）')
    args = parser.parse_args()

    if args.stats_json:
        with open(args.stats_json, encoding='utf-8') as f:
            stats = json.load(f)
        path = report_from_stats(stats, args.output_dir)
        print(f'📊 报告: {path}')
    else:
        # 无统计来源时从真实 MarketDataClient 生成
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import yaml
        from market_data_client import MarketDataClient
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'config', 'config.yaml')
        with open(cfg_path, encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        mc = MarketDataClient(cfg)
        path = generate_source_report(mc.source_health, args.output_dir)
        print(f'📊 报告: {path}')
