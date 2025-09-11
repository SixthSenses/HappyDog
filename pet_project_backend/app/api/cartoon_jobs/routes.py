# app/api/cartoon_jobs/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.cartoon_jobs.schemas import CartoonJobCreateSchema, CartoonJobResponseSchema
from app.middleware.idempotency_middleware import idempotent_endpoint
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, CartoonJobErrors, RequestExamples, ResponseExamples
)

cartoon_jobs_bp = Blueprint('cartoon_jobs_bp', __name__)

@cartoon_jobs_bp.route('/', methods=['POST'])
@jwt_required()
@idempotent_endpoint(apply_when_methods=('POST',))
@api_doc(
    summary="만화 변환 작업 생성",
    description="이미지를 만화 스타일로 변환하는 비동기 작업을 생성합니다. 요청 즉시 'pending' 상태의 작업 정보를 반환하고, 실제 처리는 백그라운드에서 진행됩니다.",
    tags=["cartoon_jobs"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CartoonJobErrors.JOB_CREATION_FAILED
)
@request_examples({
    "name": "create_cartoon_job",
    "summary": "만화 작업 생성 요청",
    "description": "만화 변환을 위한 이미지 파일과 사용자 텍스트",
    "value": {
        "file_paths": ["uploads/cartoon/image1.jpg"],
        "user_text": "귀여운 강아지 만화로 변환해주세요"
    }
})
@response_examples({
    "name": "cartoon_job_created",
    "summary": "만화 작업 생성 성공",
    "description": "생성된 만화 변환 작업 정보",
    "value": {
        "job_id": "job_123",
        "status": "pending",
        "created_at": "2023-12-10T12:00:00Z",
        "user_id": "user_456"
    }
})
def create_cartoon_job():
    """
    만화 변환 비동기 작업을 생성합니다.
    - 요청 즉시 'pending' 상태의 작업 정보를 202 Accepted 코드와 함께 반환합니다.
    - 실제 작업은 백그라운드 프로세서에서 처리됩니다.
    """
    cartoon_job_service = current_app.services['cartoon_jobs']
    job_events = current_app.services['job_events']
    
    user_id = get_jwt_identity()
    try:
        data = CartoonJobCreateSchema().load(request.get_json())
        
        # 1. 작업 생성 (순수한 CRUD, 이벤트 데이터 반환)
        image_url = data['file_paths'][0]  # 첫 번째(유일한) 이미지 URL
        job_data = cartoon_job_service.create_job(
            user_id=user_id, 
            image_url=image_url, 
            user_text=data.get('user_text', '')
        )
        
        # 2. 이벤트 처리 (백그라운드 처리 시작)
        job_events.handle_job_created(job_data)
        
        # 3. 작업 정보 반환
        return jsonify(CartoonJobResponseSchema().dump(job_data['job'])), 202
        
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"만화 작업 생성 실패 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "JOB_CREATION_FAILED", 
            "message": "만화 작업 생성 중 오류가 발생했습니다."
        }), 500


@cartoon_jobs_bp.route('/<string:job_id>', methods=['GET'])
@jwt_required()
@api_doc(
    summary="만화 작업 상태 조회",
    description="특정 만화 생성 작업의 현재 상태를 조회합니다. 작업의 진행 상황과 결과를 확인할 수 있습니다.",
    tags=["cartoon_jobs"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CartoonJobErrors.JOB_NOT_FOUND,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "job_status_response",
    "summary": "작업 상태 응답",
    "description": "만화 변환 작업의 현재 상태 정보",
    "value": {
        "job_id": "job_123",
        "status": "completed",
        "created_at": "2023-12-10T12:00:00Z",
        "completed_at": "2023-12-10T12:05:00Z",
        "result_url": "https://storage.googleapis.com/result.jpg",
        "user_id": "user_456"
    }
})
def get_cartoon_job_status(job_id: str):
    """
    특정 만화 생성 작업의 현재 상태를 조회합니다.
    """
    cartoon_job_service = current_app.services['cartoon_jobs']
    
    user_id = get_jwt_identity()
    try:
        job = cartoon_job_service.get_job_status(job_id, user_id)
        if not job:
            return jsonify({
                "error_code": "JOB_NOT_FOUND_OR_FORBIDDEN", 
                "message": "작업을 찾을 수 없거나 조회 권한이 없습니다."
            }), 404
            
        return jsonify(CartoonJobResponseSchema().dump(job)), 200
        
    except Exception as e:
        logging.error(f"만화 작업 조회 중 오류 발생 (job_id: {job_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "INTERNAL_SERVER_ERROR", 
            "message": "작업 조회 중 오류가 발생했습니다."
        }), 500


@cartoon_jobs_bp.route('/<string:job_id>', methods=['DELETE'])
@jwt_required()
@api_doc(
    summary="만화 작업 취소",
    description="진행 중인 만화 생성 작업을 취소 요청합니다. 백그라운드 프로세서에서 작업 중단을 시도합니다.",
    tags=["cartoon_jobs"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.PERMISSION_DENIED,
    CartoonJobErrors.INVALID_STATE_FOR_CANCEL,
    CartoonJobErrors.JOB_CANCEL_FAILED
)
@response_examples({
    "name": "job_cancelled",
    "summary": "작업 취소 성공",
    "description": "취소된 작업의 상태 정보",
    "value": {
        "job_id": "job_123",
        "status": "cancelled",
        "created_at": "2023-12-10T12:00:00Z",
        "cancelled_at": "2023-12-10T12:02:00Z",
        "user_id": "user_456"
    }
})
def cancel_cartoon_job(job_id: str):
    """
    진행 중인 만화 생성 작업을 취소 요청합니다.
    - 백그라운드 프로세서에서 작업 중단을 시도합니다.
    """
    cartoon_job_service = current_app.services['cartoon_jobs']
    
    user_id = get_jwt_identity()
    try:
        cancel_data = cartoon_job_service.cancel_job(job_id, user_id)
        return jsonify(CartoonJobResponseSchema().dump(cancel_data['job'])), 200
        
    except PermissionError as e:
        return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except ValueError as e:  # 상태가 취소 가능하지 않은 경우
        return jsonify({"error_code": "INVALID_STATE_FOR_CANCEL", "message": str(e)}), 409  # Conflict
    except Exception as e:
        logging.error(f"만화 작업 취소 중 오류 발생 (job_id: {job_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "JOB_CANCEL_FAILED", 
            "message": "작업 취소 중 오류가 발생했습니다."
        }), 500


@cartoon_jobs_bp.route('/health', methods=['GET'])
@api_doc(
    summary="작업 프로세서 건강 상태 조회",
    description="만화 변환 작업 프로세서의 현재 상태와 성능 지표를 조회합니다.",
    tags=["cartoon_jobs"]
)
@error_responses(
    CartoonJobErrors.HEALTH_CHECK_FAILED
)
@response_examples({
    "name": "health_status",
    "summary": "건강 상태 응답",
    "description": "작업 프로세서의 현재 상태 정보",
    "value": {
        "active_jobs": 3,
        "queue_size": 5,
        "max_workers": 4,
        "integration_health": {
            "status": "healthy",
            "last_check": "2023-12-10T12:00:00Z"
        }
    }
})
def job_health():
    """
    작업 프로세서의 건강 상태를 조회합니다.
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
        
        return jsonify(health_data), 200
        
    except Exception as e:
        logging.error(f"작업 건강 상태 조회 실패: {e}", exc_info=True)
        return jsonify({
            "error_code": "HEALTH_CHECK_FAILED",
            "message": "건강 상태 조회 중 오류가 발생했습니다."
        }), 500