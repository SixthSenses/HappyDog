# app/api/cartoon_jobs/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

#from app.api.cartoon_jobs.services import cartoon_job_service
from app.api.cartoon_jobs.schemas import CartoonJobCreateSchema, CartoonJobResponseSchema

cartoon_jobs_bp = Blueprint('cartoon_jobs_bp', __name__)

@cartoon_jobs_bp.route('/', methods=['POST'])
@jwt_required()
def create_cartoon_job():
    """
    만화 변환 비동기 작업을 생성합니다.
    - 요청 즉시 'processing' 상태의 작업 정보를 202 Accepted 코드와 함께 반환합니다.
    - 실제 작업은 백그라운드 Cloud Function에서 처리됩니다.
    """
    cartoon_job_service = current_app.services['cartoon_jobs']
    user_id = get_jwt_identity()
    try:
        data = CartoonJobCreateSchema().load(request.get_json())
        new_job = cartoon_job_service.create_cartoon_job(user_id, data['image_url'])
        return jsonify(CartoonJobResponseSchema().dump(new_job)), 202
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"만화 작업 생성 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "JOB_CREATION_FAILED", "message": "작업 생성 중 오류가 발생했습니다."}), 500


@cartoon_jobs_bp.route('/<string:job_id>', methods=['GET'])
@jwt_required()
def get_cartoon_job_status(job_id: str):
    cartoon_job_service = current_app.services['cartoon_jobs']
    """
    특정 만화 생성 작업의 현재 상태를 조회합니다.
    """
    user_id = get_jwt_identity()
    try:
        job = cartoon_job_service.get_job_by_id_and_owner(job_id, user_id)
        if not job:
            return jsonify({"error_code": "JOB_NOT_FOUND_OR_FORBIDDEN", "message": "작업을 찾을 수 없거나 조회 권한이 없습니다."}), 404
        return jsonify(CartoonJobResponseSchema().dump(job)), 200
    except Exception as e:
        logging.error(f"만화 작업 조회 중 오류 발생 (job_id: {job_id}): {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "작업 조회 중 오류가 발생했습니다."}), 500


@cartoon_jobs_bp.route('/<string:job_id>', methods=['DELETE'])
@jwt_required()
def cancel_cartoon_job(job_id: str):
    cartoon_job_service = current_app.services['cartoon_jobs']
    """
    진행 중인 만화 생성 작업을 취소 요청합니다.
    - 실제 작업 중단은 백그라운드 Cloud Function에서 상태를 확인하여 처리합니다.
    """
    user_id = get_jwt_identity()
    try:
        updated_job = cartoon_job_service.cancel_cartoon_job(user_id, job_id)
        return jsonify(CartoonJobResponseSchema().dump(updated_job)), 200
    except PermissionError as e:
        return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except ValueError as e: # 상태가 'processing'이 아닌 경우
        return jsonify({"error_code": "INVALID_STATE_FOR_CANCEL", "message": str(e)}), 409 # Conflict
    except FileNotFoundError as e:
        return jsonify({"error_code": "JOB_NOT_FOUND", "message": str(e)}), 404
    except Exception as e:
        logging.error(f"만화 작업 취소 중 오류 발생 (job_id: {job_id}): {e}", exc_info=True)
        return jsonify({"error_code": "JOB_CANCEL_FAILED", "message": "작업 취소 중 오류가 발생했습니다."}), 500