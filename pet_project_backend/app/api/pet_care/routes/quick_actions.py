# app/api/pet_care/routes/quick_actions.py
"""
펫케어 빠른 액션 자원 관리 라우트

자원: /api/pets/{pet_id}/care/quick-actions
- 빠른 칼로리/물/활동량 증감 기능
- 사용자 편의를 위한 간편한 기록 추가
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError, Schema, fields, validate

from app.utils.datetime_utils import DateTimeUtils

logger = logging.getLogger(__name__)

# 빠른 액션 전용 블루프린트
quick_actions_bp = Blueprint('quick_actions', __name__)

def get_pet_care_service():
    """펫케어 서비스를 가져옵니다."""
    return current_app.services.get('pet_care')

# ================== 요청 스키마 정의 ==================

class QuickAddSchema(Schema):
    """빠른 추가 요청 스키마"""
    amount = fields.Float(required=True, validate=validate.Range(min=0.1))
    date = fields.Date(required=False, format="%Y-%m-%d", load_default=None)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))

class QuickCaloriesSchema(QuickAddSchema):
    """빠른 칼로리 추가 스키마"""
    amount = fields.Float(required=True, validate=validate.Range(min=1, max=1000))

class QuickWaterSchema(QuickAddSchema):
    """빠른 물 추가 스키마"""  
    amount = fields.Float(required=True, validate=validate.Range(min=1, max=2000))

class QuickActivitySchema(QuickAddSchema):
    """빠른 활동 추가 스키마"""
    amount = fields.Int(required=True, validate=validate.Range(min=1, max=480))  # 분 단위
    activity_type = fields.Str(required=False, load_default="산책", validate=validate.Length(max=50))
    intensity = fields.Str(required=False, load_default="보통", validate=validate.OneOf(['가벼운', '보통', '격렬한']))

# ================== 빠른 액션 API ==================

@quick_actions_bp.route('/add-calories', methods=['POST'])
@jwt_required()
def quick_add_calories(pet_id: str):
    """
    빠른 칼로리 추가
    
    Request Body:
        amount (required): 추가할 칼로리 (kcal)
        date (optional): 기록 날짜 (기본값: 오늘)
        notes (optional): 메모
        
    Response:
        201: 칼로리 추가 성공
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
        
        # 요청 데이터 검증
        try:
            data = QuickCaloriesSchema().load(request.get_json())
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 설정 (기본값: 오늘)
        log_date = data.get('date') or DateTimeUtils.today()
        amount = data['amount']
        notes = data.get('notes')
        
        # 기존 방식 사용: 빠른 증감 기능
        result = pet_care_service.quick_add_total(pet_id, user_id, log_date, 'calories', amount)
        
        response_data = {
            "action": "add_calories",
            "pet_id": pet_id,
            "date": log_date.strftime('%Y-%m-%d'),
            "amount_added": amount,
            "previous_total": result.get('previous_value', 0),
            "new_total": result.get('new_value', 0),
            "notes": notes,
            "recorded_at": DateTimeUtils.now().isoformat(),
            "message": f"{amount}kcal가 추가되었습니다."
        }
        
        logger.info(f"빠른 칼로리 추가 성공: {pet_id} - {amount}kcal")
        return jsonify(response_data), 201
        
    except PermissionError as e:
        logger.warning(f"빠른 칼로리 추가 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"빠른 칼로리 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "QUICK_CALORIES_FAILED",
            "message": "빠른 칼로리 추가 중 오류가 발생했습니다."
        }), 500

@quick_actions_bp.route('/add-water', methods=['POST'])
@jwt_required()
def quick_add_water(pet_id: str):
    """
    빠른 물 추가
    
    Request Body:
        amount (required): 추가할 물 양 (ml)
        date (optional): 기록 날짜 (기본값: 오늘)
        notes (optional): 메모
        
    Response:
        201: 물 추가 성공
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
        
        # 요청 데이터 검증
        try:
            data = QuickWaterSchema().load(request.get_json())
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 설정 (기본값: 오늘)
        log_date = data.get('date') or DateTimeUtils.today()
        amount = data['amount']
        notes = data.get('notes')
        
        # 기존 방식 사용: 빠른 증감 기능
        result = pet_care_service.quick_add_total(pet_id, user_id, log_date, 'water', amount)
        
        response_data = {
            "action": "add_water",
            "pet_id": pet_id,
            "date": log_date.strftime('%Y-%m-%d'),
            "amount_added": amount,
            "previous_total": result.get('previous_value', 0),
            "new_total": result.get('new_value', 0),
            "notes": notes,
            "recorded_at": DateTimeUtils.now().isoformat(),
            "message": f"{amount}ml의 물이 추가되었습니다."
        }
        
        logger.info(f"빠른 물 추가 성공: {pet_id} - {amount}ml")
        return jsonify(response_data), 201
        
    except PermissionError as e:
        logger.warning(f"빠른 물 추가 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"빠른 물 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "QUICK_WATER_FAILED",
            "message": "빠른 물 추가 중 오류가 발생했습니다."
        }), 500

@quick_actions_bp.route('/add-activity', methods=['POST'])
@jwt_required()
def quick_add_activity(pet_id: str):
    """
    빠른 활동 추가
    
    Request Body:
        amount (required): 추가할 활동 시간 (분)
        date (optional): 기록 날짜 (기본값: 오늘)
        activity_type (optional): 활동 타입 (기본값: "산책")
        intensity (optional): 활동 강도 (기본값: "보통")
        notes (optional): 메모
        
    Response:
        201: 활동 추가 성공
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
        
        # 요청 데이터 검증
        try:
            data = QuickActivitySchema().load(request.get_json())
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 설정 (기본값: 오늘)
        log_date = data.get('date') or DateTimeUtils.today()
        amount = data['amount']
        activity_type = data.get('activity_type', '산책')
        intensity = data.get('intensity', '보통')
        notes = data.get('notes')
        
        # 기존 방식 사용: 빠른 증감 기능
        result = pet_care_service.quick_add_total(pet_id, user_id, log_date, 'activity', amount)
        
        response_data = {
            "action": "add_activity",
            "pet_id": pet_id,
            "date": log_date.strftime('%Y-%m-%d'),
            "amount_added": amount,
            "activity_type": activity_type,
            "intensity": intensity,
            "previous_total": result.get('previous_value', 0),
            "new_total": result.get('new_value', 0),
            "notes": notes,
            "recorded_at": DateTimeUtils.now().isoformat(),
            "message": f"{activity_type} {amount}분이 추가되었습니다."
        }
        
        logger.info(f"빠른 활동 추가 성공: {pet_id} - {activity_type} {amount}분")
        return jsonify(response_data), 201
        
    except PermissionError as e:
        logger.warning(f"빠른 활동 추가 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"빠른 활동 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "QUICK_ACTIVITY_FAILED",
            "message": "빠른 활동 추가 중 오류가 발생했습니다."
        }), 500

@quick_actions_bp.route('/subtract-calories', methods=['POST'])
@jwt_required()
def quick_subtract_calories(pet_id: str):
    """
    빠른 칼로리 감소
    
    Request Body:
        amount (required): 감소할 칼로리 (kcal)
        date (optional): 기록 날짜 (기본값: 오늘)
        notes (optional): 메모
        
    Response:
        200: 칼로리 감소 성공
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
        
        # 요청 데이터 검증
        try:
            data = QuickCaloriesSchema().load(request.get_json())
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 설정 (기본값: 오늘)
        log_date = data.get('date') or DateTimeUtils.today()
        amount = -abs(data['amount'])  # 음수로 변환
        notes = data.get('notes')
        
        # 기존 방식 사용: 빠른 증감 기능 (음수 값으로)
        result = pet_care_service.quick_add_total(pet_id, user_id, log_date, 'calories', amount)
        
        response_data = {
            "action": "subtract_calories",
            "pet_id": pet_id,
            "date": log_date.strftime('%Y-%m-%d'),
            "amount_subtracted": abs(amount),
            "previous_total": result.get('previous_value', 0),
            "new_total": result.get('new_value', 0),
            "notes": notes,
            "recorded_at": DateTimeUtils.now().isoformat(),
            "message": f"{abs(amount)}kcal가 감소되었습니다."
        }
        
        logger.info(f"빠른 칼로리 감소 성공: {pet_id} - {abs(amount)}kcal")
        return jsonify(response_data), 200
        
    except PermissionError as e:
        logger.warning(f"빠른 칼로리 감소 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"빠른 칼로리 감소 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "QUICK_CALORIES_SUBTRACT_FAILED",
            "message": "빠른 칼로리 감소 중 오류가 발생했습니다."
        }), 500

@quick_actions_bp.route('/presets', methods=['GET'])
@jwt_required()
def get_quick_action_presets(pet_id: str):
    """
    빠른 액션 프리셋 값들을 조회합니다.
    
    Response:
        200: 프리셋 설정 값들 (care_settings에서 추출)
        404: 설정이 없음
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
        
        # 빠른 액션 프리셋 추출
        presets = {
            "calories": {
                "increment": care_settings.get('food_increment', 50),
                "unit": "kcal",
                "suggested_amounts": [25, 50, 100, 150]
            },
            "water": {
                "increment": care_settings.get('water_increment', 100),
                "unit": "ml",
                "suggested_amounts": [50, 100, 200, 300]
            },
            "activity": {
                "increment": care_settings.get('activity_increment', 30),
                "unit": "minutes",
                "suggested_amounts": [15, 30, 45, 60]
            },
            "recommended_daily": {
                "calories": care_settings.get('recommended_calories', 0),
                "water_ml": care_settings.get('recommended_water_ml', 0)
            }
        }
        
        logger.info(f"빠른 액션 프리셋 조회 성공: {pet_id}")
        return jsonify({
            "pet_id": pet_id,
            "presets": presets,
            "last_updated": care_settings.get('generated_at'),
            "retrieved_at": DateTimeUtils.now().isoformat()
        }), 200
        
    except PermissionError as e:
        logger.warning(f"빠른 액션 프리셋 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"빠른 액션 프리셋 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "PRESETS_FETCH_FAILED",
            "message": "빠른 액션 프리셋 조회 중 오류가 발생했습니다."
        }), 500

# ================== 에러 핸들러 ==================

@quick_actions_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Marshmallow 유효성 검사 오류 처리"""
    return jsonify({
        "error_code": "VALIDATION_ERROR",
        "message": "요청 데이터가 유효하지 않습니다.",
        "details": error.messages
    }), 400

@quick_actions_bp.errorhandler(404)
def handle_not_found(error):
    """404 오류 처리"""
    return jsonify({
        "error_code": "NOT_FOUND",
        "message": "요청한 리소스를 찾을 수 없습니다."
    }), 404
