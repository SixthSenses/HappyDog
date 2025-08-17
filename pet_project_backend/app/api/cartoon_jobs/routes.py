# app/api/cartoon_jobs/routes.py
import logging
import threading
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.cartoon_jobs.schemas import CartoonJobCreateSchema, CartoonJobResponseSchema

cartoon_jobs_bp = Blueprint('cartoon_jobs_bp', __name__)

def process_cartoon_in_background(app, job_id: str, image_url: str, user_text: str):
    """
    백그라운드에서 만화 생성을 처리하는 함수
    Threading으로 비동기 실행됩니다.
    """
    with app.app_context():
        try:
            # Flask 애플리케이션 컨텍스트에서 서비스 가져오기
            from flask import current_app
            
            # OpenAI 서비스로 만화 생성
            openai_service = current_app.services['openai']
            result = openai_service.generate_cartoon(image_url, user_text)
            
            # CartoonJob 서비스로 결과 처리
            cartoon_job_service = current_app.services['cartoon_jobs']
            
            if result['success']:
                # 성공: 게시물 자동 생성 및 성공 알림
                cartoon_job_service.complete_cartoon_job_with_post(job_id, result['image_url'])
                logging.info(f"만화 생성 성공: {job_id}")
            else:
                # 실패: 실패 알림
                cartoon_job_service.fail_cartoon_job_with_notification(job_id, result.get('error', 'Unknown error'))
                logging.error(f"만화 생성 실패: {job_id} - {result.get('error')}")
                
        except Exception as e:
            logging.error(f"백그라운드 만화 처리 중 오류: {job_id} - {e}", exc_info=True)
            try:
                # 예외 발생 시에도 실패 처리
                cartoon_job_service = current_app.services['cartoon_jobs']
                cartoon_job_service.fail_cartoon_job_with_notification(job_id, f"처리 중 오류: {str(e)}")
            except Exception as cleanup_error:
                logging.error(f"실패 처리 중 추가 오류: {cleanup_error}")

@cartoon_jobs_bp.route('/', methods=['POST'])
@jwt_required()
def create_cartoon_job():
    """
    만화 변환 비동기 작업을 생성합니다.
    - 요청 즉시 'processing' 상태의 작업 정보를 202 Accepted 코드와 함께 반환합니다.
    - 실제 작업은 백그라운드 Thread에서 처리됩니다.
    """
    cartoon_job_service = current_app.services['cartoon_jobs']
    user_id = get_jwt_identity()
    try:
        data = CartoonJobCreateSchema().load(request.get_json())
        
        # 1. Firestore에 작업 등록
        new_job = cartoon_job_service.create_cartoon_job(user_id, data['file_paths'], data.get('user_text', ''))
        
        # 2. 백그라운드 Thread로 만화 생성 처리 시작
        image_url = data['file_paths'][0]  # 첫 번째(유일한) 이미지 URL
        app = current_app._get_current_object() # 실제 Flask app 객체를 가져옵니다.

        thread = threading.Thread(
            target=process_cartoon_in_background, 
            args=[
                app,
                new_job['job_id'],
                image_url,
                data.get('user_text', '')
            ]
        )
        thread.daemon = True  # 메인 프로세스 종료 시 함께 종료
        thread.start()
        
        # 3. 즉시 응답 반환
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