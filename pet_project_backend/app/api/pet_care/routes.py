# app/api/pet_care/routes.py
import logging
from datetime import date, datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from .schemas import (
    PetCareLogCreateRequestSchema, PetCareLogResponseSchema,
    MonthlySummarySchema, GraphDataSchema, RecommendationSchema,
    FoodLogSchema, WaterLogSchema, PoopLogSchema, ActivityLogSchema,
    WeightLogSchema, VomitLogSchema, ErrorResponseSchema
)
from .services import PetCareService
from .individual_routes import register_individual_routes

logger = logging.getLogger(__name__)

pet_care_bp = Blueprint('pet_care_bp', __name__)

# 개별 로그 CRUD 라우트 등록
register_individual_routes(pet_care_bp)

# 서비스 인스턴스는 앱 팩토리에서 주입받을 예정
def get_pet_care_service():
    """현재 앱에서 PetCareService 인스턴스를 가져옵니다."""
    return current_app.services.get('pet_care')

# ================== 통합 펫케어 로그 API ==================

@pet_care_bp.route('/pets/<pet_id>/care-logs', methods=['POST'])
@jwt_required()
def add_care_log(pet_id: str):
    """일일 펫케어 로그를 추가하거나 수정합니다."""
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 요청 데이터 유효성 검사
        try:
            log_data = PetCareLogCreateRequestSchema().load(request.get_json())
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 펫케어 로그 추가
        care_log = pet_care_service.add_care_log(pet_id, user_id, log_data)
        
        # 응답 데이터 생성
        response_data = {
            'log_id': care_log.log_id,
            'pet_id': care_log.pet_id,
            'user_id': care_log.user_id,
            'date': care_log.date,
            'food_logs_count': len(care_log.food_logs),
            'water_logs_count': len(care_log.water_logs),
            'poop_logs_count': len(care_log.poop_logs),
            'activity_logs_count': len(care_log.activity_logs),
            'vomit_logs_count': len(care_log.vomit_logs),
            'weight_logs_count': len(care_log.weight_logs),
            'medication_logs_count': len(care_log.medication_logs),
            'symptoms_logs_count': len(care_log.symptoms_logs),
            'total_calories': care_log.total_calories,
            'total_water_ml': care_log.total_water_ml,
            'total_activity_minutes': care_log.total_activity_minutes,
            'current_weight_kg': care_log.current_weight_kg,
            'general_notes': care_log.general_notes,
            'mood': care_log.mood,
            'created_at': care_log.created_at,
            'updated_at': care_log.updated_at
        }
        
        logger.info(f"펫케어 로그 추가 성공: {pet_id} - {log_data['date']}")
        return jsonify(PetCareLogResponseSchema().dump(response_data)), 201
        
    except PermissionError as e:
        logger.warning(f"펫케어 로그 추가 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"펫케어 로그 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "CARE_LOG_CREATION_FAILED",
            "message": "펫케어 로그 추가 중 오류가 발생했습니다."
        }), 500

@pet_care_bp.route('/pets/<pet_id>/care-logs', methods=['GET'])
@jwt_required()
def get_daily_log(pet_id: str):
    """특정 날짜의 펫케어 로그를 조회합니다."""
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
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
        
        # 펫케어 로그 조회
        care_log = pet_care_service.get_daily_log(pet_id, user_id, log_date)
        
        if not care_log:
            return jsonify({
                "error_code": "CARE_LOG_NOT_FOUND",
                "message": f"해당 날짜의 펫케어 로그를 찾을 수 없습니다: {date_str}"
            }), 404
        
        # 전체 로그 데이터 반환
        response_data = {
            'log_id': care_log.log_id,
            'pet_id': care_log.pet_id,
            'user_id': care_log.user_id,
            'date': care_log.date,
            'food_logs': [vars(log) for log in care_log.food_logs],
            'water_logs': [vars(log) for log in care_log.water_logs],
            'poop_logs': [vars(log) for log in care_log.poop_logs],
            'activity_logs': [vars(log) for log in care_log.activity_logs],
            'vomit_logs': [vars(log) for log in care_log.vomit_logs],
            'weight_logs': [vars(log) for log in care_log.weight_logs],
            'medication_logs': [vars(log) for log in care_log.medication_logs],
            'symptoms_logs': [vars(log) for log in care_log.symptoms_logs],
            'total_calories': care_log.total_calories,
            'total_water_ml': care_log.total_water_ml,
            'total_activity_minutes': care_log.total_activity_minutes,
            'current_weight_kg': care_log.current_weight_kg,
            'general_notes': care_log.general_notes,
            'mood': care_log.mood,
            'created_at': care_log.created_at,
            'updated_at': care_log.updated_at
        }
        
        logger.info(f"일일 펫케어 로그 조회 성공: {pet_id} - {date_str}")
        return jsonify(response_data), 200
        
    except PermissionError as e:
        logger.warning(f"펫케어 로그 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"일일 펫케어 로그 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "CARE_LOG_FETCH_FAILED",
            "message": "펫케어 로그 조회 중 오류가 발생했습니다."
        }), 500

@pet_care_bp.route('/pets/<pet_id>/care-logs/summary', methods=['GET'])
@jwt_required()
def get_monthly_summary(pet_id: str):
    """월별 펫케어 로그 요약을 조회합니다."""
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 월 파라미터 검증
        month_str = request.args.get('month')
        if not month_str:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "월 파라미터(month)가 필요합니다."
            }), 400
        
        try:
            year, month = map(int, month_str.split('-'))
            if month < 1 or month > 12:
                raise ValueError("월은 1-12 사이여야 합니다.")
        except ValueError:
            return jsonify({
                "error_code": "INVALID_MONTH_FORMAT",
                "message": "월 형식이 올바르지 않습니다. YYYY-MM 형식을 사용하세요."
            }), 400
        
        # 월별 요약 조회
        summary = pet_care_service.get_monthly_summary(pet_id, user_id, year, month)
        
        logger.info(f"월별 요약 조회 성공: {pet_id} - {month_str}")
        return jsonify(MonthlySummarySchema().dump(summary)), 200
        
    except PermissionError as e:
        logger.warning(f"월별 요약 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"월별 요약 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "MONTHLY_SUMMARY_FETCH_FAILED",
            "message": "월별 요약 조회 중 오류가 발생했습니다."
        }), 500

@pet_care_bp.route('/pets/<pet_id>/care-logs/graph', methods=['GET'])
@jwt_required()
def get_graph_data(pet_id: str):
    """그래프 데이터를 조회합니다."""
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 파라미터 검증
        metric = request.args.get('metric')
        period = request.args.get('period')
        
        if not metric:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "지표 파라미터(metric)가 필요합니다."
            }), 400
        
        if not period:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "기간 파라미터(period)가 필요합니다."
            }), 400
        
        valid_metrics = ['weight', 'calories', 'water', 'activity']
        valid_periods = ['weekly', 'monthly', 'yearly']
        
        if metric not in valid_metrics:
            return jsonify({
                "error_code": "INVALID_METRIC",
                "message": f"유효하지 않은 지표입니다. 사용 가능한 지표: {', '.join(valid_metrics)}"
            }), 400
        
        if period not in valid_periods:
            return jsonify({
                "error_code": "INVALID_PERIOD",
                "message": f"유효하지 않은 기간입니다. 사용 가능한 기간: {', '.join(valid_periods)}"
            }), 400
        
        # 그래프 데이터 조회
        graph_data = pet_care_service.get_graph_data(pet_id, user_id, metric, period)
        
        logger.info(f"그래프 데이터 조회 성공: {pet_id} - {metric} {period}")
        return jsonify(GraphDataSchema().dump(graph_data)), 200
        
    except PermissionError as e:
        logger.warning(f"그래프 데이터 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"그래프 데이터 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "GRAPH_DATA_FETCH_FAILED",
            "message": "그래프 데이터 조회 중 오류가 발생했습니다."
        }), 500

@pet_care_bp.route('/pets/<pet_id>/recommendations', methods=['GET'])
@jwt_required()
def get_recommendations(pet_id: str):
    """반려동물의 권장 칼로리 및 음수량을 조회합니다."""
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

# ================== 에러 핸들러 ==================

@pet_care_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Marshmallow 유효성 검사 오류 처리"""
    return jsonify({
        "error_code": "VALIDATION_ERROR",
        "message": "요청 데이터가 유효하지 않습니다.",
        "details": error.messages
    }), 400

@pet_care_bp.errorhandler(404)
def handle_not_found(error):
    """404 오류 처리"""
    return jsonify({
        "error_code": "NOT_FOUND",
        "message": "요청한 리소스를 찾을 수 없습니다."
    }), 404

@pet_care_bp.errorhandler(500)
def handle_internal_error(error):
    """500 오류 처리"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "error_code": "INTERNAL_SERVER_ERROR",
        "message": "서버 내부 오류가 발생했습니다."
    }), 500
