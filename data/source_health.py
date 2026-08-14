#!/usr/bin/env python3
# source_health.py - 数据源健康评分与动态熔断（基于docs/step2.md阶段2优化）
"""
SourceHealth - 源健康评分与动态熔断
===================================
理论来源: docs/step2.md（阶段2详细设计：源健康评分与动态熔断）

核心设计:
  - 滑动窗口 + 指数加权失败率（窗口内成功/失败计数）
  - 连续失败熔断: consecutive_failures >= fail_threshold 且未过恢复期 → 熔断
  - 自动恢复: 超过 recover_seconds 后自动放回可用列表（下次请求允许试探）
  - 动态排序: get_ordered_sources 剔除熔断源（可选按健康分降序）

用法:
  health = SourceHealth(config)
  health.record('akshare', success=True, latency_ms=120)   # 每次请求后记录
  health.record('akshare', success=False, latency_ms=3000) # 失败记录
  if health.is_available('akshare'): ...                   # 熔断查询
  sources = health.get_ordered_sources(['tdx_local','akshare','baostock'])
"""

import logging
import time
from collections import deque
from typing import Dict, List

logger = logging.getLogger(__name__)


class SourceHealth:
    """数据源健康评分与动态熔断"""

    def __init__(self, config: dict = None):
        cfg = ((config or {}).get("data_source", {})
               .get("health", {})) or {}
        self.window_size = int(cfg.get("window_size", 10))
        self.fail_threshold = int(cfg.get("fail_threshold", 3))
        self.recover_seconds = float(cfg.get("recover_seconds", 300))
        self.enable = bool(cfg.get("enable", True))
        # 是否按健康分动态排序（false=保持preferred顺序仅剔除熔断源）
        self.sort_by_health = bool(cfg.get("sort_by_health", False))
        self.stats: Dict[str, dict] = {}

    def _init_source(self, source: str):
        """初始化单个源的统计结构"""
        if source not in self.stats:
            self.stats[source] = {
                "success_count": 0,
                "failure_count": 0,
                "consecutive_failures": 0,
                "last_failure_time": 0,
                "window": deque(maxlen=self.window_size),
                "health_score": 100.0,
                "is_open": True,
                "last_latency_ms": 0.0,
                "avg_latency_ms": 0.0,
            }

    def record(self, source: str, success: bool, latency_ms: float = 0):
        """
        记录一次请求结果
        :param source: 数据源名称（tdx_local/akshare/baostock/tdx_protocol）
        :param success: 是否成功（空数据视为成功，避免停牌股误熔断）
        :param latency_ms: 请求耗时（毫秒）
        """
        if not self.enable:
            return
        self._init_source(source)
        s = self.stats[source]
        if success:
            s["success_count"] += 1
            s["consecutive_failures"] = 0
            s["window"].append(1)
        else:
            s["failure_count"] += 1
            s["consecutive_failures"] += 1
            s["last_failure_time"] = time.time()
            s["window"].append(0)
        # 延迟统计（指数加权平均）
        s["last_latency_ms"] = latency_ms
        if s["success_count"] + s["failure_count"] == 1:
            s["avg_latency_ms"] = latency_ms
        else:
            s["avg_latency_ms"] = s["avg_latency_ms"] * 0.8 + latency_ms * 0.2
        # 更新健康分: 窗口内成功率*100（滑动窗口优先，不足窗口期用累计）
        window_vals = list(s["window"])
        if window_vals:
            s["health_score"] = (sum(window_vals) / len(window_vals)) * 100
        # 熔断检查（首次达到阈值时触发，熔断中不重复告警）
        if (s["consecutive_failures"] >= self.fail_threshold
                and s["is_open"]):
            s["is_open"] = False
            logger.warning(f"🔴 源 {source} 连续失败 "
                           f"{s['consecutive_failures']} 次，"
                           f"熔断 {self.recover_seconds:.0f} 秒")

    def is_available(self, source: str) -> bool:
        """查询源是否可用（熔断中且未过恢复期 → False）"""
        if not self.enable:
            return True
        self._init_source(source)
        s = self.stats[source]
        if not s["is_open"]:
            elapsed = time.time() - s["last_failure_time"]
            if elapsed >= self.recover_seconds:
                # 熔断恢复：重置熔断状态，允许试探请求
                s["is_open"] = True
                s["consecutive_failures"] = 0
                s["window"].clear()
                logger.info(f"🟢 源 {source} 熔断恢复（{elapsed:.0f}s 后）")
                return True
            return False
        return True

    def get_ordered_sources(self, preferred: List[str]) -> List[str]:
        """
        返回可用源列表：
          - 剔除熔断中的源
          - sort_by_health=true 时按健康分降序（高分优先）
          - 默认保持 preferred 顺序（主源优先策略，源性质不同）
        """
        if not preferred:
            return []
        if not self.enable:
            return list(preferred)
        available = [s for s in preferred if self.is_available(s)]
        if self.sort_by_health and len(available) > 1:
            available = sorted(
                available,
                key=lambda s: (self.stats[s]["health_score"],
                               -self.stats[s]["failure_count"]),
                reverse=True)
        return available

    def get_source_stats(self) -> Dict[str, dict]:
        """获取所有源的健康统计（调试/报告用）"""
        return {k: {kk: vv for kk, vv in v.items() if kk != 'window'}
                for k, v in self.stats.items()}
