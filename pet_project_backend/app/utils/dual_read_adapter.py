"""Dual Read Adapter (Phase0)
=============================
Scalar → Object 마이그레이션을 위한 읽기 어댑터.

현재 대상 필드 예: weight_latest, bcs_latest 등 (이미 일부 객체화됨).

규칙:
 - 값이 스칼라(ex: 12.3)면 {"value": 12.3, "unit": unit(default)} 로 감싼다.
 - 값이 dict 이면 그대로 통과 (value 키 필수 아닐 수도 있으므로 최소 가드만).
 - None 허용.

메트릭:
 - dual_read_adapter_fallback_total (scalar 감싼 횟수)
"""
from __future__ import annotations

from typing import Any, Optional, Dict
from . import metrics


def wrap_scalar(value: Any, unit: str = "kg") -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):  # 이미 객체
        return value
    if isinstance(value, (int, float)):
        metrics.increment("dual_read_adapter_fallback_total", field="weight_latest")
        return {"value": float(value), "unit": unit}
    # 기타 타입은 무시 (불일치)
    return None


__all__ = ["wrap_scalar"]
