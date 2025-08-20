# app/api/pet_care/routes/daily_logs.py
"""
일일 펫케어 로그 자원 관리 라우트

자원: /api/pets/{pet_id}/care/daily-logs
- 하루 전체의 종합적인 펫케어 기록을 관리
- 여러 타입의 로그들을 한 번에 조회/생성/수정
"""

import logging
from datetime import date
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.utils.datetime_utils import DateTimeUtils, validate_date
from ..schemas import (
    PetCareLogCreateRequestSchema, PetCareLogResponseSchema, 
    MonthlySummarySchema, ErrorResponseSchema
)

logger = logging.getLogger(__name__)

# 일일 로그 전용 블루프린트
daily_logs_bp = Blueprint('daily_logs', __name__)

def get_daily_log_service():
    """일일 로그 서비스를 가져옵니다."""
    return current_app.services.get('daily_log')

def get_pet_care_service():
    """기존 펫케어 서비스를 가져옵니다 (호환성)."""
    return current_app.services.get('pet_care')

# ================== 일일 종합 로그 API ==================

@daily_logs_bp.route('', methods=['GET'])
@jwt_required()
def get_daily_log(pet_id: str):
    """
    특정 날짜의 일일 펫케어 로그를 조회합니다.
    
    Query Parameters:
        date (required): 조회할 날짜 (YYYY-MM-DD)
        
    Response:
        200: 일일 로그 데이터
        404: 해당 날짜의 로그가 없음
        400: 잘못된 날짜 형식
    """
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
            log_date = DateTimeUtils.validate_date_field(date_str, 'date')
        except ValueError as e:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": str(e)
            }), 400
        
        # 일일 로그 조회
        care_log = pet_care_service.get_daily_log(pet_id, user_id, log_date)
        
        if not care_log:
            return jsonify({
                "error_code": "DAILY_LOG_NOT_FOUND",
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
        logger.warning(f"일일 로그 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN", 
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"일일 로그 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "DAILY_LOG_FETCH_FAILED",
            "message": "일일 로그 조회 중 오류가 발생했습니다."
        }), 500

@daily_logs_bp.route('', methods=['POST'])
@jwt_required()
def create_or_update_daily_log(pet_id: str):
    """
    일일 펫케어 로그를 생성하거나 수정합니다.
    
    Request Body:
        date (required): 기록 날짜
        food_logs (optional): 음식 기록 목록
        water_logs (optional): 물 섭취 기록 목록
        ... (기타 로그 타입들)
        general_notes (optional): 일반 메모
        mood (optional): 기분 상태
        
    Response:
        201: 로그 생성/수정 성공
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
        
        # 요청 데이터 유효성 검사
        try:
            log_data = PetCareLogCreateRequestSchema().load(request.get_json())
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 펫케어 로그 추가/수정
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
        
        logger.info(f"일일 로그 생성/수정 성공: {pet_id} - {log_data['date']}")
        return jsonify(PetCareLogResponseSchema().dump(response_data)), 201
        
    except PermissionError as e:
        logger.warning(f"일일 로그 생성 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"일일 로그 생성 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "DAILY_LOG_CREATION_FAILED",
            "message": "일일 로그 생성 중 오류가 발생했습니다."
        }), 500

@daily_logs_bp.route('/summary', methods=['GET'])
@jwt_required()
def get_monthly_summary(pet_id: str):
    """
    월별 펫케어 로그 요약을 조회합니다.
    
    Query Parameters:
        month (required): 조회할 월 (YYYY-MM)
        
    Response:
        200: 월별 요약 데이터
        400: 잘못된 월 형식
    """
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

# ================== 에러 핸들러 ==================

@daily_logs_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Marshmallow 유효성 검사 오류 처리"""
    return jsonify({
        "error_code": "VALIDATION_ERROR",
        "message": "요청 데이터가 유효하지 않습니다.",
        "details": error.messages
    }), 400

@daily_logs_bp.errorhandler(404)
def handle_not_found(error):
    """404 오류 처리"""
    return jsonify({
        "error_code": "NOT_FOUND",
        "message": "요청한 리소스를 찾을 수 없습니다."
    }), 404
