# app/api/uploads/routes.py

import logging
from flask import request, jsonify, Blueprint, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.utils.error_catalog import build_error
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, UploadErrors, RequestExamples, ResponseExamples
)

# 'uploads' 기능을 위한 새로운 블루프린트를 생성합니다.
# 이 블루프린트에 속한 모든 API는 '/api/uploads' 라는 접두사 URL을 갖게 됩니다.
uploads_bp = Blueprint('uploads', __name__)

# 새로 분리된 스키마 import
from .schemas import (
    UploadUrlRequestSchema,
    FinalizeCartoonRequestSchema,
    ALLOWED_UPLOAD_TYPES,
    DEPRECATED_UPLOAD_TYPE_ALIASES,
)


@uploads_bp.route('/url', methods=['POST'])
@jwt_required()
@api_doc(
    summary="업로드 URL 생성",
    description="모든 파일 업로드를 위한 범용 Pre-signed URL을 발급합니다. 클라이언트는 이 API를 먼저 호출하여 업로드할 권한이 있는 임시 URL을 받아야 합니다.",
    tags=["uploads"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.RECORD_CREATION_FAILED
)
@request_examples({
    "name": "upload_url_request",
    "summary": "업로드 URL 요청",
    "description": "파일 업로드를 위한 Pre-signed URL 요청",
    "value": {
        "upload_type": "profile_image",
        "filename": "profile.jpg",
        "content_type": "image/jpeg"
    }
})
@response_examples({
    "name": "upload_url_response",
    "summary": "업로드 URL 응답",
    "description": "생성된 Pre-signed URL과 업로드 정보",
    "value": {
        "upload_url": "https://storage.googleapis.com/...",
        "file_path": "uploads/profile_images/user_123/profile.jpg",
        "expires_at": "2023-12-10T13:00:00Z"
    }
})
def get_upload_url():
    """
    모든 파일 업로드를 위한 범용 Pre-signed URL을 발급합니다.
    클라이언트는 이 API를 먼저 호출하여 업로드할 권한이 있는 임시 URL을 받아야 합니다.
    """
    # 요청 헤더의 JWT에서 현재 로그인된 사용자의 ID를 가져옵니다.
    user_id = get_jwt_identity()
    
    # 요청 본문이 JSON 형식인지 확인하고 데이터를 파싱합니다.
    try:
        raw = request.get_json() or {}
        # Alias → Canonical 변환 (유예용). 변환 발생 시 로그 남김.
        ut = raw.get('upload_type')
        if ut in DEPRECATED_UPLOAD_TYPE_ALIASES:
            canonical = DEPRECATED_UPLOAD_TYPE_ALIASES[ut]
            logging.info(f"Deprecated upload_type alias '{ut}' -> '{canonical}' 변환")
            raw['upload_type'] = canonical
            # 프론트 교정 유도 위해 응답 metadata 로도 내려줄 수 있으나 scope 밖 → TODO 주석
        payload = UploadUrlRequestSchema().load(raw)
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status

    # Flask 앱에 등록된 StorageService 인스턴스를 가져옵니다.
    storage_service = current_app.services['storage']
    
    try:
        url_info = storage_service.generate_upload_url(
            user_id,
            payload['upload_type'],
            payload['filename'],
            payload['content_type']
        )
        # (선택) deprecated 사용 시 metadata 추가 가능
        return jsonify(url_info), 200
    except ValueError as e:
        # storage 서비스에서 지원하지 않는 타입 등
        logging.warning(f"URL 발급 실패 (INVALID_UPLOAD_TYPE): {e}")
        status, body = build_error('VALIDATION_ERROR', message=str(e))  # 에러 카탈로그에 INVALID_UPLOAD_TYPE 없음 → VALIDATION_ERROR 유지
        return jsonify(body), status
    except Exception as e:
        logging.error(f"Pre-signed URL 생성 중 서버 오류: {e}", exc_info=True)
        status, body = build_error('RECORD_CREATION_FAILED', message="URL 생성 실패")
        return jsonify(body), status


@uploads_bp.route('/finalize-cartoon', methods=['POST'])
@jwt_required()
@api_doc(
    summary="만화 이미지 공개 전환",
    description="업로드된 만화 원본 이미지를 공개로 전환하고 공개 URL을 반환합니다. 만화 변환 작업 완료 후 사용됩니다.",
    tags=["uploads"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.RESOURCE_NOT_FOUND,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "finalize_cartoon_request",
    "summary": "만화 이미지 공개 전환 요청",
    "description": "공개로 전환할 만화 이미지 파일 경로",
    "value": {"file_path": "uploads/cartoon/temp/cartoon_123.jpg"}
})
@response_examples({
    "name": "finalize_cartoon_response",
    "summary": "공개 전환 성공",
    "description": "공개로 전환된 파일의 URL",
    "value": {"public_url": "https://storage.googleapis.com/public/cartoon_123.jpg"}
})
def finalize_cartoon_upload():
    """
    업로드된 만화 원본 이미지를 공개로 전환하고 URL을 반환합니다.
    """
    storage_service = current_app.services['storage']
    
    try:
        data = FinalizeCartoonRequestSchema().load(request.get_json() or {})
        public_url = storage_service.make_public_and_get_url(data['file_path'])
        return jsonify({"public_url": public_url}), 200
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except FileNotFoundError as e:
        status, body = build_error('NOT_FOUND', message=str(e))  # FILE_NOT_FOUND 별도 카탈로그 미존재 → NOT_FOUND
        return jsonify(body), status
    except Exception as e:
        logging.error(f"파일 공개 전환 오류: {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED', message="공개 전환 실패")
        return jsonify(body), status
