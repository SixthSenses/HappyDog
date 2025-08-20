# app/api/pet_care/routes/recommendations.py
"""
펫케어 권장량 자원 관리 라우트

자원: /api/pets/{pet_id}/care/recommendations
- 반려동물별 맞춤 권장량 조회
- 권장량 수동 갱신 (필요시)
- 권장량 변경 이력 관리
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.utils.datetime_utils import DateTimeUtils
from ..schemas import RecommendationSchema, ErrorResponseSchema

logger = logging.getLogger(__name__)

# 권장량 전용 블루프린트
recommendations_bp = Blueprint('recommendations', __name__)

def get_recommendation_service():
    """권장량 서비스를 가져옵니다."""
    return current_app.services.get('recommendation')

def get_pet_care_service():
    """기존 펫케어 서비스를 가져옵니다 (호환성)."""
    return current_app.services.get('pet_care')

# ================== 권장량 관리 API ==================

@recommendations_bp.route('', methods=['GET'])
@jwt_required()
def get_recommendations(pet_id: str):
    """
    현재 반려동물의 권장량을 조회합니다.
    
    Response:
        200: 권장량 데이터 (RER, MER, 권장 음수량 등)
        404: 권장량 정보가 없음
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 권장량 계산
        recommendations = pet_care_service.calculate_recommendations(pet_id)
        
        logger.info(f"권장량 조회 성공: {pet_id}")
        return jsonify(RecommendationSchema().dump(recommendations)), 200
        
    except PermissionError as e:
        logger.warning(f"권장량 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except ValueError as e:
        logger.warning(f"권장량 계산 데이터 오류: {pet_id} - {e}")
        return jsonify({
            "error_code": "INVALID_PET_DATA",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.error(f"권장량 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "RECOMMENDATIONS_FETCH_FAILED",
            "message": "권장량 조회 중 오류가 발생했습니다."
        }), 500

@recommendations_bp.route('/refresh', methods=['POST'])
@jwt_required()
def refresh_recommendations(pet_id: str):
    """
    권장량을 수동으로 갱신합니다.
    
    Note: 일반적으로는 반려동물 정보 업데이트 시 자동 갱신되지만,
    필요에 따라 수동으로 갱신할 수 있습니다.
    
    Response:
        200: 갱신된 권장량 데이터
        400: 갱신 실패
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 권한 확인을 위해 펫 정보 조회
        if not pet_care_service._verify_pet_ownership(pet_id, user_id):
            return jsonify({
                "error_code": "FORBIDDEN",
                "message": f"펫 {pet_id}에 대한 접근 권한이 없습니다."
            }), 403
        
        # 새로운 권장량 계산
        recommendations = pet_care_service.calculate_recommendations(pet_id)
        
        # TODO: 향후 펫 정보의 care_settings도 함께 업데이트하는 로직 추가
        # 현재는 계산만 수행하고 반환
        
        logger.info(f"권장량 수동 갱신 성공: {pet_id}")
        return jsonify({
            "message": "권장량이 성공적으로 갱신되었습니다.",
            "recommendations": RecommendationSchema().dump(recommendations),
            "refreshed_at": DateTimeUtils.now().isoformat()
        }), 200
        
    except PermissionError as e:
        logger.warning(f"권장량 갱신 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except ValueError as e:
        logger.warning(f"권장량 갱신 데이터 오류: {pet_id} - {e}")
        return jsonify({
            "error_code": "INVALID_PET_DATA",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.error(f"권장량 갱신 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "RECOMMENDATIONS_REFRESH_FAILED",
            "message": "권장량 갱신 중 오류가 발생했습니다."
        }), 500

@recommendations_bp.route('/history', methods=['GET'])
@jwt_required()
def get_recommendation_history(pet_id: str):
    """
    권장량 변경 이력을 조회합니다.
    
    Query Parameters:
        limit (optional): 조회할 이력 개수 (기본값: 10)
        
    Response:
        200: 권장량 변경 이력 목록
        
    Note: 현재는 기본 구조만 제공, 향후 이력 저장 로직 구현 필요
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 권한 확인
        if not pet_care_service._verify_pet_ownership(pet_id, user_id):
            return jsonify({
                "error_code": "FORBIDDEN",
                "message": f"펫 {pet_id}에 대한 접근 권한이 없습니다."
            }), 403
        
        # 현재는 현재 권장량만 반환 (이력 기능은 향후 구현)
        current_recommendations = pet_care_service.calculate_recommendations(pet_id)
        
        history = [
            {
                "timestamp": current_recommendations.get("calculated_at"),
                "recommendations": current_recommendations,
                "trigger": "current_calculation",
                "notes": "현재 계산된 권장량"
            }
        ]
        
        logger.info(f"권장량 이력 조회 성공: {pet_id}")
        return jsonify({
            "pet_id": pet_id,
            "history": history,
            "total_count": len(history),
            "note": "현재는 최신 권장량만 제공됩니다. 이력 기능은 향후 업데이트 예정입니다."
        }), 200
        
    except PermissionError as e:
        logger.warning(f"권장량 이력 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"권장량 이력 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "RECOMMENDATION_HISTORY_FAILED",
            "message": "권장량 이력 조회 중 오류가 발생했습니다."
        }), 500

@recommendations_bp.route('/settings', methods=['GET'])
@jwt_required()
def get_care_settings(pet_id: str):
    """
    펫케어 설정 정보를 조회합니다.
    
    Response:
        200: care_settings 데이터 (빠른 증감 설정 등)
        404: 설정 정보가 없음
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 권한 확인
        if not pet_care_service._verify_pet_ownership(pet_id, user_id):
            return jsonify({
                "error_code": "FORBIDDEN",
                "message": f"펫 {pet_id}에 대한 접근 권한이 없습니다."
            }), 403
        
        # 펫 정보에서 care_settings 조회
        pet_doc = pet_care_service.pets_collection.document(pet_id).get()
        if not pet_doc.exists:
            return jsonify({
                "error_code": "PET_NOT_FOUND",
                "message": "반려동물을 찾을 수 없습니다."
            }), 404
        
        pet_data = pet_doc.to_dict()
        care_settings = pet_data.get('care_settings', {})
        
        if not care_settings:
            return jsonify({
                "error_code": "CARE_SETTINGS_NOT_FOUND",
                "message": "펫케어 설정 정보가 없습니다."
            }), 404
        
        logger.info(f"펫케어 설정 조회 성공: {pet_id}")
        return jsonify({
            "pet_id": pet_id,
            "care_settings": care_settings,
            "retrieved_at": DateTimeUtils.now().isoformat()
        }), 200
        
    except PermissionError as e:
        logger.warning(f"펫케어 설정 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"펫케어 설정 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "CARE_SETTINGS_FETCH_FAILED",
            "message": "펫케어 설정 조회 중 오류가 발생했습니다."
        }), 500

@recommendations_bp.route('/settings', methods=['PUT'])
@jwt_required()
def update_care_settings(pet_id: str):
    """
    펫케어 설정을 업데이트합니다.
    
    Request Body:
        food_increment (optional): 음식 빠른 증감 단위
        water_increment (optional): 물 빠른 증감 단위
        activity_increment (optional): 활동 빠른 증감 단위
        
    Response:
        200: 업데이트된 설정 정보
        400: 잘못된 요청 데이터
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 권한 확인
        if not pet_care_service._verify_pet_ownership(pet_id, user_id):
            return jsonify({
                "error_code": "FORBIDDEN",
                "message": f"펫 {pet_id}에 대한 접근 권한이 없습니다."
            }), 403
        
        # 요청 데이터 검증
        update_data = request.get_json()
        if not update_data:
            return jsonify({
                "error_code": "MISSING_REQUEST_BODY",
                "message": "요청 본문이 필요합니다."
            }), 400
        
        # 유효한 설정 필드만 허용
        valid_fields = {'food_increment', 'water_increment', 'activity_increment'}
        invalid_fields = set(update_data.keys()) - valid_fields
        
        if invalid_fields:
            return jsonify({
                "error_code": "INVALID_FIELDS",
                "message": f"허용되지 않는 필드입니다: {', '.join(invalid_fields)}"
            }), 400
        
        # 값 검증
        for field, value in update_data.items():
            if not isinstance(value, (int, float)) or value <= 0:
                return jsonify({
                    "error_code": "INVALID_VALUE",
                    "message": f"{field}는 양수여야 합니다."
                }), 400
        
        # 기존 care_settings 조회
        pet_ref = pet_care_service.pets_collection.document(pet_id)
        pet_doc = pet_ref.get()
        
        if not pet_doc.exists:
            return jsonify({
                "error_code": "PET_NOT_FOUND",
                "message": "반려동물을 찾을 수 없습니다."
            }), 404
        
        pet_data = pet_doc.to_dict()
        current_settings = pet_data.get('care_settings', {})
        
        # 설정 업데이트
        updated_settings = {**current_settings, **update_data}
        updated_settings['updated_at'] = DateTimeUtils.now()
        
        # Firestore 업데이트
        pet_ref.update({
            'care_settings': DateTimeUtils.for_firestore(updated_settings)
        })
        
        logger.info(f"펫케어 설정 업데이트 성공: {pet_id}")
        return jsonify({
            "pet_id": pet_id,
            "care_settings": updated_settings,
            "updated_at": DateTimeUtils.now().isoformat(),
            "message": "펫케어 설정이 성공적으로 업데이트되었습니다."
        }), 200
        
    except PermissionError as e:
        logger.warning(f"펫케어 설정 업데이트 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"펫케어 설정 업데이트 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "CARE_SETTINGS_UPDATE_FAILED",
            "message": "펫케어 설정 업데이트 중 오류가 발생했습니다."
        }), 500

# ================== 에러 핸들러 ==================

@recommendations_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Marshmallow 유효성 검사 오류 처리"""
    return jsonify({
        "error_code": "VALIDATION_ERROR",
        "message": "요청 데이터가 유효하지 않습니다.",
        "details": error.messages
    }), 400

@recommendations_bp.errorhandler(404)
def handle_not_found(error):
    """404 오류 처리"""
    return jsonify({
        "error_code": "NOT_FOUND",
        "message": "요청한 리소스를 찾을 수 없습니다."
    }), 404
