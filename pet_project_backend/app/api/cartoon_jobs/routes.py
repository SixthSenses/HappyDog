# app/api/cartoon_jobs/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.cartoon_jobs.schemas import (
    CartoonJobCreateSchema,
    CartoonJobResponseSchema,
    CartoonJobHealthResponseSchema,
)
from app.middleware.idempotency_middleware import idempotent_endpoint
from app.utils.error_catalog import build_error

cartoon_jobs_bp = Blueprint('cartoon_jobs_bp', __name__)

@cartoon_jobs_bp.route('/', methods=['POST'])
@jwt_required()
@idempotent_endpoint(apply_when_methods=('POST',))
def create_cartoon_job():
    """만화 변환 작업 생성

    이미지를 만화 스타일로 변환하는 비동기 작업을 생성합니다.

    RequestSchema: CartoonJobCreateSchema
    ResponseSchema[202]: CartoonJobResponseSchema
    """
    cartoon_job_service = current_app.services['cartoon_jobs']
    job_events = current_app.services['job_events']
    storage_service = current_app.services['storage']
    user_id = get_jwt_identity()
    try:
        data = CartoonJobCreateSchema().load(request.get_json())
        file_path = data['file_paths'][0]
        
        # 파일 경로를 Firebase Storage URL로 변환
        # (GCS URL이 아닌 토큰 포함된 Firebase Storage URL 사용)
        try:
            if file_path.startswith('https://'):
                # 이미 URL인 경우 그대로 사용
                image_url = file_path
            else:
                # 상대 경로인 경우 Firebase Storage URL 생성
                image_url = storage_service.get_public_url(file_path)
                logging.info(f"만화 작업용 Firebase Storage URL 생성: {image_url}")
        except Exception as e:
            logging.error(f"이미지 URL 생성 실패: {e}")
            # Fallback: 원본 경로 사용
            image_url = file_path
        
        job_data = cartoon_job_service.create_job(
            user_id=user_id,
            image_url=image_url,
            user_text=data.get('user_text', '')
        )
        job_events.handle_job_created(job_data)
        return jsonify(CartoonJobResponseSchema().dump(job_data['job'])), 202
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except Exception as e:
        logging.error(f"만화 작업 생성 실패 (user_id: {user_id}): {e}", exc_info=True)
        status, body = build_error('RECORD_CREATION_FAILED', message="만화 작업 생성 중 오류가 발생했습니다.")
        return jsonify(body), status


@cartoon_jobs_bp.route('/<string:job_id>', methods=['GET'])
@jwt_required()
def get_cartoon_job_status(job_id: str):
    """만화 작업 상태 조회

    특정 만화 생성 작업의 현재 상태를 조회합니다.

    ResponseSchema[200]: CartoonJobResponseSchema
    """
    cartoon_job_service = current_app.services['cartoon_jobs']
    user_id = get_jwt_identity()
    try:
        job = cartoon_job_service.get_job_status(job_id, user_id)
        if not job:
            status, body = build_error('NOT_FOUND', message="작업을 찾을 수 없거나 조회 권한이 없습니다.")
            return jsonify(body), status
        return jsonify(CartoonJobResponseSchema().dump(job)), 200
    except Exception as e:
        logging.error(f"만화 작업 조회 중 오류 발생 (job_id: {job_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED', message="작업 조회 중 오류가 발생했습니다.")
        return jsonify(body), status


@cartoon_jobs_bp.route('/<string:job_id>', methods=['DELETE'])
@jwt_required()
@idempotent_endpoint(apply_when_methods=('DELETE',))
def cancel_cartoon_job(job_id: str):
    """만화 작업 취소

    진행 중인 만화 생성 작업을 취소 요청합니다.

    ResponseSchema[200]: CartoonJobResponseSchema
    """
    cartoon_job_service = current_app.services['cartoon_jobs']
    user_id = get_jwt_identity()
    try:
        cancel_data = cartoon_job_service.cancel_job(job_id, user_id)
        return jsonify(CartoonJobResponseSchema().dump(cancel_data['job'])), 200
    except PermissionError as e:
        status, body = build_error('FORBIDDEN', message=str(e))
        return jsonify(body), status
    except ValueError as e:
        status, body = build_error('INVALID_STATE_FOR_CANCEL', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"만화 작업 취소 중 오류 발생 (job_id: {job_id}): {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED', message="작업 취소 중 오류가 발생했습니다.")
        return jsonify(body), status


@cartoon_jobs_bp.route('/health', methods=['GET'])
def job_health():
    """작업 프로세서 건강 상태 조회

    만화 변환 작업 프로세서의 현재 상태와 성능 지표를 조회합니다.

    ResponseSchema[200]: CartoonJobHealthResponseSchema
    """
    try:
        job_processor = current_app.services['job_processor']
        job_integration = current_app.services['job_integration']
        health_data = {
            'active_jobs': job_processor.get_active_count(),
            'queue_size': job_processor.get_queue_size(),
            'max_workers': job_processor.max_workers,
            'integration_health': job_integration.get_integration_health()
        }
        return jsonify(CartoonJobHealthResponseSchema().dump(health_data)), 200
    except Exception as e:
        logging.error(f"작업 건강 상태 조회 실패: {e}", exc_info=True)
        status, body = build_error('SERVICE_UNAVAILABLE', message="건강 상태 조회 중 오류가 발생했습니다.")
        return jsonify(body), status