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

    # Backward compatibility: legacy code references .message
    # New code should prefer .default_message or build_error.
    @property
    def message(self) -> Optional[str]:  # pragma: no cover - thin accessor
        return self.default_message


ERRORS: Dict[str, ErrorSpec] = {
    # Validation & Permission
    'VALIDATION_ERROR': ErrorSpec('VALIDATION_ERROR', 'VALIDATION', 400, False, '입력 값이 유효하지 않습니다.'),
    'FORBIDDEN': ErrorSpec('FORBIDDEN', 'PERMISSION', 403, False, '권한이 없습니다.'),
    'NOT_FOUND': ErrorSpec('NOT_FOUND', 'NOT_FOUND', 404, False, '리소스를 찾을 수 없습니다.'),
    
    # Range & Query Validation (Sprint C)
    'OUT_OF_RANGE': ErrorSpec('OUT_OF_RANGE', 'VALIDATION', 422, False, '값이 허용 범위를 벗어났습니다.'),
    'RANGE_TOO_LARGE': ErrorSpec('RANGE_TOO_LARGE', 'VALIDATION', 400, False, '조회 범위가 너무 큽니다.'),
    'INVALID_QUERY_COMBINATION': ErrorSpec('INVALID_QUERY_COMBINATION', 'VALIDATION', 400, False, '잘못된 쿼리 파라미터 조합입니다.'),

    # Rate limit / Conflict
    'RATE_LIMIT_EXCEEDED': ErrorSpec('RATE_LIMIT_EXCEEDED', 'RATE_LIMIT', 429, True, '요청이 너무 많습니다.'),
    'IDEMPOTENCY_CONFLICT': ErrorSpec('IDEMPOTENCY_CONFLICT', 'CONFLICT', 409, False, 'Idempotency 충돌'),
    'IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY': ErrorSpec('IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY', 'CONFLICT', 409, False, '동일한 Idempotency Key로 다른 요청을 시도했습니다.'),

    # Generic internal buckets
    'FETCH_FAILED': ErrorSpec('FETCH_FAILED', 'INTERNAL', 500, True, '조회 중 오류 발생'),
    'RECORD_CREATION_FAILED': ErrorSpec('RECORD_CREATION_FAILED', 'INTERNAL', 500, True, '생성 중 오류 발생'),
    'UPDATE_FAILED': ErrorSpec('UPDATE_FAILED', 'INTERNAL', 500, True, '수정 중 오류 발생'),
    'DELETE_FAILED': ErrorSpec('DELETE_FAILED', 'INTERNAL', 500, True, '삭제 중 오류 발생'),
    'SERVICE_UNAVAILABLE': ErrorSpec('SERVICE_UNAVAILABLE', 'SERVICE', 503, True, '서비스를 현재 사용할 수 없습니다.'),

    # Biometric domain (PR2B)
    'BIO_IMAGE_MISSING': ErrorSpec('BIO_IMAGE_MISSING', 'BIOMETRIC', 400, False, 'Required biometric image file is missing.'),
    'BIO_INVALID_IMAGE': ErrorSpec('BIO_INVALID_IMAGE', 'BIOMETRIC', 400, False, 'Uploaded image format is invalid or unreadable.'),
    'BIO_ALREADY_VERIFIED': ErrorSpec('BIO_ALREADY_VERIFIED', 'BIOMETRIC', 409, False, 'Biometric already verified for this pet.'),
    'BIO_DUPLICATE_CANDIDATE': ErrorSpec('BIO_DUPLICATE_CANDIDATE', 'BIOMETRIC', 409, False, 'A similar biometric candidate already exists in staging.'),
    'BIO_PROCESSING_FAILED': ErrorSpec('BIO_PROCESSING_FAILED', 'BIOMETRIC', 500, False, 'Biometric image processing failed.'),
    'BIO_ALREADY_PROCESSED': ErrorSpec('BIO_ALREADY_PROCESSED', 'BIOMETRIC', 409, False, 'This biometric image has already been processed.'),

    # Cartoon job domain (PR3)
    'JOB_CREATION_FAILED': ErrorSpec('JOB_CREATION_FAILED', 'INTERNAL', 500, True, '만화 작업 생성 중 오류가 발생했습니다.'),
    'JOB_CANCEL_FAILED': ErrorSpec('JOB_CANCEL_FAILED', 'INTERNAL', 500, True, '작업 취소 중 오류가 발생했습니다.'),
    'INVALID_STATE_FOR_CANCEL': ErrorSpec('INVALID_STATE_FOR_CANCEL', 'VALIDATION', 409, False, '현재 상태에서는 작업을 취소할 수 없습니다.'),
    'HEALTH_CHECK_FAILED': ErrorSpec('HEALTH_CHECK_FAILED', 'SERVICE', 503, True, '건강 상태 조회 중 오류가 발생했습니다.'),
    'JOB_NOT_FOUND_OR_FORBIDDEN': ErrorSpec('JOB_NOT_FOUND_OR_FORBIDDEN', 'NOT_FOUND', 404, False, '작업을 찾을 수 없거나 권한이 없습니다.'),
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