"""Central Error Catalog & Builder
----------------------------------
표준화된 에러 응답 생성을 위한 스펙 구현 (Sprint C 일부).

응답 필드:
 - error_code
 - category
 - retriable
 - message (옵션: default_message 있거나 오버라이드 제공 시)
 - details (선택)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Any, Tuple


@dataclass(frozen=True)
class ErrorSpec:
    code: str
    category: str
    http_status: int
    retriable: bool = False
    default_message: Optional[str] = None


ERRORS: Dict[str, ErrorSpec] = {
    # Validation & Permission
    'VALIDATION_ERROR': ErrorSpec('VALIDATION_ERROR', 'VALIDATION', 400, False, '입력 값이 유효하지 않습니다.'),
    'FORBIDDEN': ErrorSpec('FORBIDDEN', 'PERMISSION', 403, False, '권한이 없습니다.'),
    'NOT_FOUND': ErrorSpec('NOT_FOUND', 'NOT_FOUND', 404, False, '리소스를 찾을 수 없습니다.'),

    # Rate limit / Conflict
    'RATE_LIMIT_EXCEEDED': ErrorSpec('RATE_LIMIT_EXCEEDED', 'RATE_LIMIT', 429, True, '요청이 너무 많습니다.'),
    'IDEMPOTENCY_CONFLICT': ErrorSpec('IDEMPOTENCY_CONFLICT', 'CONFLICT', 409, False, 'Idempotency 충돌'),

    # Generic internal buckets
    'FETCH_FAILED': ErrorSpec('FETCH_FAILED', 'INTERNAL', 500, True, '조회 중 오류 발생'),
    'RECORD_CREATION_FAILED': ErrorSpec('RECORD_CREATION_FAILED', 'INTERNAL', 500, True, '생성 중 오류 발생'),
    'UPDATE_FAILED': ErrorSpec('UPDATE_FAILED', 'INTERNAL', 500, True, '수정 중 오류 발생'),
    'DELETE_FAILED': ErrorSpec('DELETE_FAILED', 'INTERNAL', 500, True, '삭제 중 오류 발생'),
}


def build_error(code: str, message: Optional[str] = None, details: Any = None) -> Tuple[int, Dict[str, Any]]:
    spec = ERRORS.get(code)
    if not spec:
        return 500, {
            'error_code': code,
            'category': 'INTERNAL',
            'retriable': True,
            'message': message or '알 수 없는 오류'
        }
    body: Dict[str, Any] = {
        'error_code': spec.code,
        'category': spec.category,
        'retriable': spec.retriable,
    }
    msg = message or spec.default_message
    if msg:
        body['message'] = msg
    if details is not None:
        body['details'] = details
    return spec.http_status, body


__all__ = ['build_error', 'ERRORS', 'ErrorSpec']