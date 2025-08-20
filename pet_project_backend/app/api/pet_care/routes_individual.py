# app/api/pet_care/routes_individual.py
import logging
from datetime import date, datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from .schemas import (
    FoodLogSchema, WaterLogSchema, PoopLogSchema, ActivityLogSchema,
    WeightLogSchema, RecommendationSchema, ErrorResponseSchema
)
from .services_individual import IndividualPetCareService

logger = logging.getLogger(__name__)

individual_pet_care_bp = Blueprint('individual_pet_care_bp', __name__)

# 서비스 인스턴스는 앱 팩토리에서 주입받을 예정
def get_individual_pet_care_service():
    """현재 앱에서 IndividualPetCareService 인스턴스를 가져옵니다."""
    return current_app.services.get('individual_pet_care')

# ================== 음식 기록 CRUD ==================

@individual_pet_care_bp.route('/pets/<pet_id>/care-logs/food', methods=['POST'])
@jwt_required()
def add_food_log(pet_id: str):
    """
    새로운 음식 기록을 추가합니다.
    
    Path Parameters:
        - pet_id (str): 반려동물 ID
        
    Request Body:
        - calories (float): 칼로리
        - timestamp (str): 섭취 시간 (ISO format)
        - food_type (str): 음식 타입 ("식사", "간식", "트릿")
        - food_name (str, optional): 음식명
        - amount_g (float, optional): 섭취량 (그램)
        - notes (str, optional): 특이사항
        - date (str, optional): 기록 날짜 (YYYY-MM-DD, 기본값: 오늘)
    """
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 요청 데이터 유효성 검사
        try:
            request_data = request.get_json()
            food_data = FoodLogSchema(exclude=['log_id']).load(request_data)
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 파라미터 처리
        log_date_str = request_data.get('date', date.today().strftime('%Y-%m-%d'))
        try:
            log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
            }), 400
        
        # 음식 기록 추가
        food_log = service.add_food_log(pet_id, user_id, log_date, food_data)
        
        # 응답 데이터 생성
        response_data = FoodLogSchema().dump(food_log)
        
        logger.info(f"음식 기록 추가 성공: {pet_id} - {food_log.log_id}")
        return jsonify({
            "message": "음식 기록이 성공적으로 추가되었습니다.",
            "food_log": response_data
        }), 201
        
    except PermissionError as e:
        logger.warning(f"음식 기록 추가 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"음식 기록 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "FOOD_LOG_CREATION_FAILED",
            "message": "음식 기록 추가 중 오류가 발생했습니다."
        }), 500

@individual_pet_care_bp.route('/pets/<pet_id>/care-logs/food/<food_log_id>', methods=['PATCH'])
@jwt_required()
def update_food_log(pet_id: str, food_log_id: str):
    """
    특정 음식 기록을 수정합니다.
    
    Path Parameters:
        - pet_id (str): 반려동물 ID
        - food_log_id (str): 음식 기록 ID
        
    Query Parameters:
        - date (str, required): 기록 날짜 (YYYY-MM-DD)
        
    Request Body:
        - 수정할 필드들 (calories, food_type, food_name, amount_g, notes 등)
    """
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 날짜 파라미터 검증
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "날짜 파라미터(date)가 필요합니다."
            }), 400
        
        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
            }), 400
        
        # 요청 데이터 검증
        update_data = request.get_json()
        if not update_data:
            return jsonify({
                "error_code": "EMPTY_UPDATE_DATA",
                "message": "수정할 데이터가 필요합니다."
            }), 400
        
        # 음식 기록 수정
        updated_food_log = service.update_food_log(pet_id, user_id, log_date, food_log_id, update_data)
        
        if not updated_food_log:
            return jsonify({
                "error_code": "FOOD_LOG_NOT_FOUND",
                "message": "수정할 음식 기록을 찾을 수 없습니다."
            }), 404
        
        # 응답 데이터 생성
        response_data = FoodLogSchema().dump(updated_food_log)
        
        logger.info(f"음식 기록 수정 성공: {pet_id} - {food_log_id}")
        return jsonify({
            "message": "음식 기록이 성공적으로 수정되었습니다.",
            "food_log": response_data
        }), 200
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except ValueError as e:
        return jsonify({
            "error_code": "INVALID_REQUEST",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.error(f"음식 기록 수정 실패 ({pet_id}, {food_log_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "FOOD_LOG_UPDATE_FAILED",
            "message": "음식 기록 수정 중 오류가 발생했습니다."
        }), 500

@individual_pet_care_bp.route('/pets/<pet_id>/care-logs/food/<food_log_id>', methods=['DELETE'])
@jwt_required()
def delete_food_log(pet_id: str, food_log_id: str):
    """
    특정 음식 기록을 삭제합니다.
    
    Path Parameters:
        - pet_id (str): 반려동물 ID
        - food_log_id (str): 음식 기록 ID
        
    Query Parameters:
        - date (str, required): 기록 날짜 (YYYY-MM-DD)
    """
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 날짜 파라미터 검증
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "날짜 파라미터(date)가 필요합니다."
            }), 400
        
        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
            }), 400
        
        # 음식 기록 삭제
        success = service.delete_food_log(pet_id, user_id, log_date, food_log_id)
        
        if success:
            logger.info(f"음식 기록 삭제 성공: {pet_id} - {food_log_id}")
            return jsonify({
                "message": "음식 기록이 성공적으로 삭제되었습니다."
            }), 200
        else:
            return jsonify({
                "error_code": "FOOD_LOG_NOT_FOUND",
                "message": "삭제할 음식 기록을 찾을 수 없습니다."
            }), 404
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except ValueError as e:
        return jsonify({
            "error_code": "INVALID_REQUEST",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.error(f"음식 기록 삭제 실패 ({pet_id}, {food_log_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "FOOD_LOG_DELETE_FAILED",
            "message": "음식 기록 삭제 중 오류가 발생했습니다."
        }), 500

# ================== 배변 기록 CRUD ==================

@individual_pet_care_bp.route('/pets/<pet_id>/care-logs/poop', methods=['POST'])
@jwt_required()
def add_poop_log(pet_id: str):
    """새로운 배변 기록을 추가합니다."""
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 요청 데이터 유효성 검사
        try:
            request_data = request.get_json()
            poop_data = PoopLogSchema(exclude=['log_id']).load(request_data)
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 파라미터 처리
        log_date_str = request_data.get('date', date.today().strftime('%Y-%m-%d'))
        try:
            log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
            }), 400
        
        # 배변 기록 추가
        poop_log = service.add_poop_log(pet_id, user_id, log_date, poop_data)
        
        # 응답 데이터 생성
        response_data = PoopLogSchema().dump(poop_log)
        
        logger.info(f"배변 기록 추가 성공: {pet_id} - {poop_log.log_id}")
        return jsonify({
            "message": "배변 기록이 성공적으로 추가되었습니다.",
            "poop_log": response_data
        }), 201
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"배변 기록 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "POOP_LOG_CREATION_FAILED",
            "message": "배변 기록 추가 중 오류가 발생했습니다."
        }), 500

# ================== 활동 기록 CRUD ==================

@individual_pet_care_bp.route('/pets/<pet_id>/care-logs/activity', methods=['POST'])
@jwt_required()
def add_activity_log(pet_id: str):
    """새로운 활동 기록을 추가합니다."""
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 요청 데이터 유효성 검사
        try:
            request_data = request.get_json()
            activity_data = ActivityLogSchema(exclude=['log_id']).load(request_data)
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 파라미터 처리
        log_date_str = request_data.get('date', date.today().strftime('%Y-%m-%d'))
        try:
            log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
            }), 400
        
        # 활동 기록 추가
        activity_log = service.add_activity_log(pet_id, user_id, log_date, activity_data)
        
        # 응답 데이터 생성
        response_data = ActivityLogSchema().dump(activity_log)
        
        logger.info(f"활동 기록 추가 성공: {pet_id} - {activity_log.log_id}")
        return jsonify({
            "message": "활동 기록이 성공적으로 추가되었습니다.",
            "activity_log": response_data
        }), 201
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"활동 기록 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "ACTIVITY_LOG_CREATION_FAILED",
            "message": "활동 기록 추가 중 오류가 발생했습니다."
        }), 500

# ================== 물 섭취 기록 CRUD ==================

@individual_pet_care_bp.route('/pets/<pet_id>/care-logs/water', methods=['POST'])
@jwt_required()
def add_water_log(pet_id: str):
    """새로운 물 섭취 기록을 추가합니다."""
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 요청 데이터 유효성 검사
        try:
            request_data = request.get_json()
            water_data = WaterLogSchema(exclude=['log_id']).load(request_data)
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 파라미터 처리
        log_date_str = request_data.get('date', date.today().strftime('%Y-%m-%d'))
        try:
            log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
            }), 400
        
        # 물 섭취 기록 추가
        water_log = service.add_water_log(pet_id, user_id, log_date, water_data)
        
        # 응답 데이터 생성
        response_data = WaterLogSchema().dump(water_log)
        
        logger.info(f"물 섭취 기록 추가 성공: {pet_id} - {water_log.log_id}")
        return jsonify({
            "message": "물 섭취 기록이 성공적으로 추가되었습니다.",
            "water_log": response_data
        }), 201
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"물 섭취 기록 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "WATER_LOG_CREATION_FAILED",
            "message": "물 섭취 기록 추가 중 오류가 발생했습니다."
        }), 500

# ================== 체중 기록 CRUD ==================

@individual_pet_care_bp.route('/pets/<pet_id>/care-logs/weight', methods=['POST'])
@jwt_required()
def add_weight_log(pet_id: str):
    """새로운 체중 기록을 추가합니다."""
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 요청 데이터 유효성 검사
        try:
            request_data = request.get_json()
            weight_data = WeightLogSchema(exclude=['log_id']).load(request_data)
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 파라미터 처리
        log_date_str = request_data.get('date', date.today().strftime('%Y-%m-%d'))
        try:
            log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
            }), 400
        
        # 체중 기록 추가
        weight_log = service.add_weight_log(pet_id, user_id, log_date, weight_data)
        
        # 응답 데이터 생성
        response_data = WeightLogSchema().dump(weight_log)
        
        logger.info(f"체중 기록 추가 성공: {pet_id} - {weight_log.log_id}")
        return jsonify({
            "message": "체중 기록이 성공적으로 추가되었습니다.",
            "weight_log": response_data
        }), 201
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"체중 기록 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "WEIGHT_LOG_CREATION_FAILED",
            "message": "체중 기록 추가 중 오류가 발생했습니다."
        }), 500

# ================== 빠른 증감 기능 ==================

@individual_pet_care_bp.route('/pets/<pet_id>/care-logs/quick-add', methods=['POST'])
@jwt_required()
def quick_add_total(pet_id: str):
    """
    빠른 증감 기능: 총량 필드를 직접 증감합니다.
    
    Request Body:
        - log_type (str): 'calories', 'water', 'activity'
        - amount (float): 증감할 양 (음수도 가능)
        - date (str, optional): 기록 날짜 (YYYY-MM-DD, 기본값: 오늘)
    """
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 요청 데이터 검증
        request_data = request.get_json()
        if not request_data:
            return jsonify({
                "error_code": "MISSING_REQUEST_DATA",
                "message": "요청 데이터가 필요합니다."
            }), 400
        
        log_type = request_data.get('log_type')
        amount = request_data.get('amount')
        
        if not log_type or amount is None:
            return jsonify({
                "error_code": "MISSING_PARAMETERS",
                "message": "log_type과 amount 파라미터가 필요합니다."
            }), 400
        
        valid_log_types = ['calories', 'water', 'activity']
        if log_type not in valid_log_types:
            return jsonify({
                "error_code": "INVALID_LOG_TYPE",
                "message": f"유효하지 않은 로그 타입입니다. 사용 가능한 타입: {', '.join(valid_log_types)}"
            }), 400
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return jsonify({
                "error_code": "INVALID_AMOUNT",
                "message": "amount는 숫자여야 합니다."
            }), 400
        
        # 날짜 파라미터 처리
        log_date_str = request_data.get('date', date.today().strftime('%Y-%m-%d'))
        try:
            log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
            }), 400
        
        # 빠른 증감 실행
        result = service.quick_add_total(pet_id, user_id, log_date, log_type, amount)
        
        logger.info(f"빠른 증감 성공: {pet_id} - {log_type}: {result['change']}")
        return jsonify({
            "message": f"{log_type} 총량이 성공적으로 업데이트되었습니다.",
            "result": result
        }), 200
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"빠른 증감 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "QUICK_ADD_FAILED",
            "message": "빠른 증감 중 오류가 발생했습니다."
        }), 500

# ================== 조회 기능 ==================

@individual_pet_care_bp.route('/pets/<pet_id>/care-logs', methods=['GET'])
@jwt_required()
def get_daily_log(pet_id: str):
    """
    특정 날짜의 모든 기록을 조회합니다.
    
    Query Parameters:
        - date (str, required): 조회할 날짜 (YYYY-MM-DD)
    """
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 날짜 파라미터 검증
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "날짜 파라미터(date)가 필요합니다."
            }), 400
        
        try:
            log_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": "날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식을 사용하세요."
            }), 400
        
        # 일일 기록 조회
        daily_log = service.get_daily_log(pet_id, user_id, log_date)
        
        if not daily_log:
            return jsonify({
                "error_code": "CARE_LOG_NOT_FOUND",
                "message": f"해당 날짜의 펫케어 기록을 찾을 수 없습니다: {date_str}"
            }), 404
        
        logger.info(f"일일 기록 조회 성공: {pet_id} - {date_str}")
        return jsonify(daily_log), 200
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"일일 기록 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "DAILY_LOG_FETCH_FAILED",
            "message": "일일 기록 조회 중 오류가 발생했습니다."
        }), 500

@individual_pet_care_bp.route('/pets/<pet_id>/recommendations', methods=['GET'])
@jwt_required()
def get_recommendations(pet_id: str):
    """
    반려동물의 권장 칼로리 및 음수량을 조회합니다.
    """
    try:
        user_id = get_jwt_identity()
        service = get_individual_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 권장량 계산
        recommendations = service.calculate_recommendations(pet_id)
        
        logger.info(f"권장량 조회 성공: {pet_id}")
        return jsonify(RecommendationSchema().dump(recommendations)), 200
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except ValueError as e:
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

# ================== 에러 핸들러 ==================

@individual_pet_care_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Marshmallow 유효성 검사 오류 처리"""
    return jsonify({
        "error_code": "VALIDATION_ERROR",
        "message": "요청 데이터가 유효하지 않습니다.",
        "details": error.messages
    }), 400

@individual_pet_care_bp.errorhandler(404)
def handle_not_found(error):
    """404 오류 처리"""
    return jsonify({
        "error_code": "NOT_FOUND",
        "message": "요청한 리소스를 찾을 수 없습니다."
    }), 404

@individual_pet_care_bp.errorhandler(500)
def handle_internal_error(error):
    """500 오류 처리"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "error_code": "INTERNAL_SERVER_ERROR",
        "message": "서버 내부 오류가 발생했습니다."
    }), 500
