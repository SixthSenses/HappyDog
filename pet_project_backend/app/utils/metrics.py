"""In-memory Metrics Stub (Sprint Tasks)
=======================================
단순 카운터 기반 메트릭 스텁. 프로덕션에서는 Prometheus/Cloud exporter로 대체.

사용법:
    from app.utils import metrics
    metrics.increment('etag_hit', endpoint='daily')

키 포맷:
    name|k1=v1,k2=v2 (태그 알파벳 순 정렬)

주의:
 - 멀티프로세스 / 멀티워커 환경에서는 정확성 보장하지 않음.
 - 테스트/개발 용도.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Any
import threading

_lock = threading.Lock()
_counters: Dict[str, int] = defaultdict(int)


def _format_key(name: str, tags: Dict[str, Any]) -> str:
    if not tags:
        return name
    parts = [f"{k}={tags[k]}" for k in sorted(tags.keys())]
    return f"{name}|{','.join(parts)}"


def increment(name: str, amount: int = 1, **tags):  # type: ignore
    with _lock:
        _counters[_format_key(name, tags)] += amount


def get_counters() -> Dict[str, int]:
    with _lock:
        return dict(_counters)


def reset():
    with _lock:
        _counters.clear()


__all__ = ["increment", "get_counters", "reset"]
