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
    # =============================
    # Common / Validation / Auth
    # =============================
    'UNAUTHORIZED': ErrorSpec('UNAUTHORIZED', 'AUTH', 401, False, '인증이 필요하거나 토큰이 유효하지 않습니다.'),  # Replaces INVALID_JWT / MISSING_JWT
    'VALIDATION_ERROR': ErrorSpec('VALIDATION_ERROR', 'VALIDATION', 400, False, '입력 값이 유효하지 않습니다.'),
    'FORBIDDEN': ErrorSpec('FORBIDDEN', 'PERMISSION', 403, False, '권한이 없습니다.'),  # Replaces PERMISSION_DENIED
    'NOT_FOUND': ErrorSpec('NOT_FOUND', 'NOT_FOUND', 404, False, '리소스를 찾을 수 없습니다.'),  # Collapses *_NOT_FOUND variants
    'INTERNAL_ERROR': ErrorSpec('INTERNAL_ERROR', 'INTERNAL', 500, True, '서버 내부 오류가 발생했습니다.'),  # Replaces INTERNAL_SERVER_ERROR

    # Range & Query Validation
    'OUT_OF_RANGE': ErrorSpec('OUT_OF_RANGE', 'VALIDATION', 422, False, '값이 허용 범위를 벗어났습니다.'),
    'INVALID_STATE': ErrorSpec('INVALID_STATE', 'VALIDATION', 409, False, '현재 상태에서는 수행할 수 없는 작업입니다.'),
    'RANGE_TOO_LARGE': ErrorSpec('RANGE_TOO_LARGE', 'VALIDATION', 400, False, '조회 범위가 너무 큽니다.'),
    'INVALID_QUERY_COMBINATION': ErrorSpec('INVALID_QUERY_COMBINATION', 'VALIDATION', 400, False, '잘못된 쿼리 파라미터 조합입니다.'),

    # Rate limit / Conflict
    'RATE_LIMIT_EXCEEDED': ErrorSpec('RATE_LIMIT_EXCEEDED', 'RATE_LIMIT', 429, True, '요청이 너무 많습니다.'),  # Replaces RATE_LIMITED
    'IDEMPOTENCY_CONFLICT': ErrorSpec('IDEMPOTENCY_CONFLICT', 'CONFLICT', 409, False, '중복 Idempotency 요청이 감지되었습니다.'),
    'IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY': ErrorSpec('IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY', 'CONFLICT', 409, False, '동일 키로 다른 요청 본문이 전송되었습니다.'),

    # Generic internal operation buckets (Korean unified messages)
    'FETCH_FAILED': ErrorSpec('FETCH_FAILED', 'INTERNAL', 500, True, '조회 처리 중 오류가 발생했습니다.'),
    'RECORD_CREATION_FAILED': ErrorSpec('RECORD_CREATION_FAILED', 'INTERNAL', 500, True, '생성 처리 중 오류가 발생했습니다.'),
    'UPDATE_FAILED': ErrorSpec('UPDATE_FAILED', 'INTERNAL', 500, True, '수정 처리 중 오류가 발생했습니다.'),
    'DELETE_FAILED': ErrorSpec('DELETE_FAILED', 'INTERNAL', 500, True, '삭제 처리 중 오류가 발생했습니다.'),
    'SERVICE_UNAVAILABLE': ErrorSpec('SERVICE_UNAVAILABLE', 'SERVICE', 503, True, '서비스를 현재 사용할 수 없습니다.'),
    'FIRESTORE_UNAVAILABLE': ErrorSpec('FIRESTORE_UNAVAILABLE', 'SERVICE', 503, True, '데이터베이스(Cloud Firestore)에 일시적으로 연결할 수 없습니다.'),

    # Biometric & Pet domain (selected domain-specific retained)
    'BIO_IMAGE_MISSING': ErrorSpec('BIO_IMAGE_MISSING', 'BIOMETRIC', 400, False, '필수 생체 이미지 파일이 누락되었습니다.'),
    'BIO_INVALID_IMAGE': ErrorSpec('BIO_INVALID_IMAGE', 'BIOMETRIC', 400, False, '업로드된 이미지가 유효하지 않거나 읽을 수 없습니다.'),
    'BIO_ALREADY_VERIFIED': ErrorSpec('BIO_ALREADY_VERIFIED', 'BIOMETRIC', 409, False, '이미 해당 반려동물에 대해 생체 정보가 검증되었습니다.'),
    'BIO_DUPLICATE_CANDIDATE': ErrorSpec('BIO_DUPLICATE_CANDIDATE', 'BIOMETRIC', 409, False, '유사한 생체 후보 데이터가 이미 존재합니다.'),
    'BIO_PROCESSING_FAILED': ErrorSpec('BIO_PROCESSING_FAILED', 'BIOMETRIC', 500, False, '생체 이미지 처리에 실패했습니다.'),
    'BIO_ALREADY_PROCESSED': ErrorSpec('BIO_ALREADY_PROCESSED', 'BIOMETRIC', 409, False, '이 생체 이미지는 이미 처리되었습니다.'),
    'PET_LIMIT_REACHED': ErrorSpec('PET_LIMIT_REACHED', 'LIMIT', 409, False, '등록 가능한 반려동물 수 한도를 초과했습니다.'),
    'NOSE_PRINT_DUPLICATE': ErrorSpec('NOSE_PRINT_DUPLICATE', 'BIOMETRIC', 409, False, '이미 등록된 비문과 중복됩니다.'),

    # Cartoon job domain (creation/cancel merged into generic codes; health check -> SERVICE_UNAVAILABLE)
    'INVALID_STATE_FOR_CANCEL': ErrorSpec('INVALID_STATE_FOR_CANCEL', 'VALIDATION', 409, False, '현재 상태에서는 작업을 취소할 수 없습니다.'),
    'JOB_NOT_FOUND_OR_FORBIDDEN': ErrorSpec('JOB_NOT_FOUND_OR_FORBIDDEN', 'NOT_FOUND', 404, False, '작업을 찾을 수 없거나 권한이 없습니다.'),
    
    # Business / quota & duplicate semantics retained
    'DUPLICATE_RECORD': ErrorSpec('DUPLICATE_RECORD', 'CONFLICT', 409, False, '이미 해당 날짜에 동일한 기록이 존재합니다.'),
    'STORAGE_QUOTA_EXCEEDED': ErrorSpec('STORAGE_QUOTA_EXCEEDED', 'LIMIT', 413, False, '저장소 할당량을 초과했습니다.'),
}

# ---------------------------------------------------------------------------
# Legacy Mapping Reference (Phase 1 Consolidation)
# ---------------------------------------------------------------------------
# INVALID_JWT, MISSING_JWT -> UNAUTHORIZED
# PERMISSION_DENIED -> FORBIDDEN
# RESOURCE_NOT_FOUND, *_NOT_FOUND (Phase 2 collapse) -> NOT_FOUND
# INTERNAL_SERVER_ERROR -> INTERNAL_ERROR
# RATE_LIMITED -> RATE_LIMIT_EXCEEDED
# POST_CREATION_FAILED, COMMENT_CREATION_FAILED, ... -> RECORD_CREATION_FAILED (Phase 2)
# POST_UPDATE_FAILED, PROFILE_UPDATE_FAILED, ... -> UPDATE_FAILED (Phase 2)
# POST_DELETE_FAILED, COMMENT_DELETE_FAILED, ACCOUNT_DELETE_FAILED -> DELETE_FAILED (Phase 2)
# FILE_NOT_FOUND, RECORD_NOT_FOUND, SETTINGS_NOT_FOUND, PET_NOT_FOUND, ... -> NOT_FOUND (Phase 2)
# JOB_NOT_FOUND -> JOB_NOT_FOUND_OR_FORBIDDEN (already unified)
# INVALID_PARAMETERS, INVALID_UPLOAD_TYPE -> VALIDATION_ERROR (evaluate retention in Phase 2)
# LIKE_TOGGLE_FAILED -> UPDATE_FAILED (collapsed)
# JOB_CREATION_FAILED, JOB_CANCEL_FAILED -> RECORD_CREATION_FAILED / UPDATE_FAILED (collapsed)
# HEALTH_CHECK_FAILED -> SERVICE_UNAVAILABLE (collapsed)



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