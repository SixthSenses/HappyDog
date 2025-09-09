"""Canonical JSON 직렬화 & 해시 유틸리티

README (섹션 5. Canonical JSON) 규칙 구현:
1) 키 정렬 (사전순)
2) 공백 제거 (compact) – json.dumps(separators=(',', ':'))
3) float 처리: 정수값이면 소수 제거 (1.0 -> 1) 단, 예외 필드(PRESERVE_DECIMAL_FIELDS)는 최소 한 자리 유지(7.0 그대로)
4) boolean/null: 표준 json 모듈이 소문자 처리
5) 53bit 초과 정수(> 2**53-1 또는 < -(2**53-1))는 문자열로 강제 (정밀도 손실 방지)
6) 출력: Canonical 문자열 + SHA256(hex)
7) 멱등성 키 비교 시 Body(요청 JSON)만 대상 (Query 제외) – 호출 측에서 Body만 전달할 것

예시:
>>> from app.utils.canonical_json import compute_canonical_hash
>>> payload = {"b": 2, "a": 1.0}
>>> canonical, h = compute_canonical_hash(payload)
>>> canonical
'{"a":1,"b":2}'

주의:
- datetime / bytes 등 JSON 비호환 타입 입력 시 TypeError 발생
- PRESERVE_DECIMAL_FIELDS 는 키 이름 기준(깊이 무관). 중첩 dict 내부 동일 키에도 적용.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Set
import json
import math
import hashlib

PRESERVE_DECIMAL_FIELDS: Set[str] = {"weight_goal", "probability"}
SAFE_INT_MAX = 2 ** 53 - 1  # JavaScript Number 안전 정수 최대값

__all__ = [
    "PRESERVE_DECIMAL_FIELDS",
    "canonicalize",
    "canonical_json_dumps",
    "compute_canonical_hash",
]


def _is_safe_int(n: int) -> bool:
    return -SAFE_INT_MAX <= n <= SAFE_INT_MAX


def _transform(value: Any, key: str | None, preserve_decimal_fields: Set[str]) -> Any:
    """재귀적으로 값 변환.

    - dict: 키 정렬은 dumps 단계에서 수행하므로 값만 변환
    - list: 요소 변환
    - float: 규칙 적용
    - int: 53bit 초과 시 문자열 변환
    - 기타: JSON 호환 타입만 허용
    """
    if isinstance(value, dict):
        return {k: _transform(v, k, preserve_decimal_fields) for k, v in value.items()}
    if isinstance(value, list):
        return [_transform(v, None, preserve_decimal_fields) for v in value]
    if isinstance(value, float):
        # 예외 필드: 소수 한 자리 이상 유지 (7.0 => 7.0 그대로)
        if key in preserve_decimal_fields:
            return value  # json.dumps 가 7.0 형태 유지
        # 정수값이면 int 변환
        if math.isfinite(value) and value.is_integer():
            return int(value)
        return value  # 그대로 (json 모듈이 0.5 등 출력)
    if isinstance(value, int):
        if not _is_safe_int(value):
            # 안전 범위 초과 → 문자열화
            return str(value)
        return value
    if value is None or isinstance(value, (str, bool)):
        return value
    # JSON 비호환 타입 방지 (미리 명확하게 오류)
    raise TypeError(f"Unsupported type for canonical JSON: {type(value)} (key={key})")


def canonicalize(obj: Any, preserve_decimal_fields: Set[str] | None = None) -> Any:
    """입력 객체(JSON 직렬화 가능)를 Canonical 규칙에 맞게 변환한 새 구조 반환.

    Note: 키 정렬은 최종 직렬화 단계에서 수행. 여기선 값 변환만.
    """
    if preserve_decimal_fields is None:
        preserve_decimal_fields = PRESERVE_DECIMAL_FIELDS
    return _transform(obj, None, preserve_decimal_fields)


def canonical_json_dumps(obj: Any, preserve_decimal_fields: Set[str] | None = None) -> str:
    """Canonical 규칙에 따라 JSON 문자열 생성."""
    transformed = canonicalize(obj, preserve_decimal_fields)
    # sort_keys=True 로 모든 dict 키 사전순 정렬, compact separators
    return json.dumps(transformed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_canonical_hash(obj: Any, preserve_decimal_fields: Set[str] | None = None) -> Tuple[str, str]:
    """Canonical JSON 문자열과 SHA256(hex) 해시를 반환.

    Returns:
        (canonical_json_str, sha256_hex)
    """
    canonical_str = canonical_json_dumps(obj, preserve_decimal_fields)
    sha = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    return canonical_str, sha


if __name__ == "__main__":  # 간단한 수동 검증
    samples = [
        {"b": 2, "a": 1.0},
        {"weight_goal": 7.0, "probability": 0.50},
        {"nested": {"z": 1, "a": 2.0}},
        {"big": 2 ** 60, "ok": 1234567890123},
    ]
    for s in samples:
        c, h = compute_canonical_hash(s)
        print(c, h)