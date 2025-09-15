# app/api/uploads/routes.py

import logging
from flask import request, jsonify, Blueprint, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.utils.error_catalog import build_error

# 'uploads' 기능을 위한 새로운 블루프린트를 생성합니다.
# 이 블루프린트에 속한 모든 API는 '/api/uploads' 라는 접두사 URL을 갖게 됩니다.
uploads_bp = Blueprint('uploads', __name__)

# 새로 분리된 스키마 import
from .schemas import (
    UploadUrlRequestSchema,
    FinalizeCartoonRequestSchema,
    UploadUrlResponseSchema,
    FinalizeCartoonResponseSchema,
    DEPRECATED_UPLOAD_TYPE_ALIASES,
)


@uploads_bp.route('/url', methods=['POST'])
@jwt_required()
def get_upload_url():
    """업로드 URL 생성

    모든 파일 업로드를 위한 범용 Pre-signed URL을 발급합니다.

    RequestSchema: UploadUrlRequestSchema
    ResponseSchema[200]: UploadUrlResponseSchema
    """
    user_id = get_jwt_identity()
    try:
        raw = request.get_json() or {}
        ut = raw.get('upload_type')
        if ut in DEPRECATED_UPLOAD_TYPE_ALIASES:
            canonical = DEPRECATED_UPLOAD_TYPE_ALIASES[ut]
            logging.info(f"Deprecated upload_type alias '{ut}' -> '{canonical}' 변환")
            raw['upload_type'] = canonical
        payload = UploadUrlRequestSchema().load(raw)
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    storage_service = current_app.services['storage']
    try:
        url_info = storage_service.generate_upload_url(
            user_id,
            payload['upload_type'],
            payload['filename'],
            payload['content_type']
        )
        return jsonify(UploadUrlResponseSchema().dump(url_info)), 200
    except ValueError as e:
        logging.warning(f"URL 발급 실패 (INVALID_UPLOAD_TYPE): {e}")
        status, body = build_error('VALIDATION_ERROR', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"Pre-signed URL 생성 중 서버 오류: {e}", exc_info=True)
        status, body = build_error('RECORD_CREATION_FAILED', message="URL 생성 실패")
        return jsonify(body), status


@uploads_bp.route('/finalize-cartoon', methods=['POST'])
@jwt_required()
def finalize_cartoon_upload():
    """만화 이미지 공개 전환

    업로드된 만화 원본 이미지를 공개로 전환하고 URL을 반환합니다.

    RequestSchema: FinalizeCartoonRequestSchema
    ResponseSchema[200]: FinalizeCartoonResponseSchema
    """
    storage_service = current_app.services['storage']
    try:
        data = FinalizeCartoonRequestSchema().load(request.get_json() or {})
        public_url = storage_service.make_public_and_get_url(data['file_path'])
        return jsonify(FinalizeCartoonResponseSchema().dump({'public_url': public_url})), 200
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except FileNotFoundError as e:
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"파일 공개 전환 오류: {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED', message="공개 전환 실패")
        return jsonify(body), status
