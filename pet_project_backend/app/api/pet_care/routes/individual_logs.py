# app/api/pet_care/routes/individual_logs.py
"""
개별 펫케어 로그 자원 관리 라우트

자원: /api/pets/{pet_id}/care/{log-type}
- 각 로그 타입별 개별 CRUD 작업
- 일관된 RESTful 패턴 적용
- 지원하는 로그 타입: food-logs, water-logs, poop-logs, activity-logs, weight-logs, vomit-logs
"""

import logging
from datetime import date
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.utils.datetime_utils import DateTimeUtils, validate_date
from ..schemas import (
    FoodLogSchema, WaterLogSchema, PoopLogSchema, ActivityLogSchema,
    WeightLogSchema, VomitLogSchema,
    ErrorResponseSchema
)

logger = logging.getLogger(__name__)

# 개별 로그 전용 블루프린트
individual_logs_bp = Blueprint('individual_logs', __name__)

def get_individual_log_service():
    """개별 로그 서비스를 가져옵니다."""
    return current_app.services.get('individual_log')

def get_pet_care_service():
    """기존 펫케어 서비스를 가져옵니다 (호환성)."""
    return current_app.services.get('pet_care')

# 로그 타입별 스키마 매핑
LOG_TYPE_SCHEMAS = {
    'food-logs': FoodLogSchema,
    'water-logs': WaterLogSchema,
    'poop-logs': PoopLogSchema,
    'activity-logs': ActivityLogSchema,
    'weight-logs': WeightLogSchema,
    'vomit-logs': VomitLogSchema
}

# 로그 타입별 서비스 메서드 매핑
LOG_TYPE_SERVICE_METHODS = {
    'food-logs': {
        'add': 'add_food_log',
        'update': 'update_food_log', 
        'delete': 'delete_food_log'
    },
    'water-logs': {
        'add': 'add_water_log',
        'update': 'update_water_log',
        'delete': 'delete_water_log'
    },
    'poop-logs': {
        'add': 'add_poop_log',
        'update': 'update_poop_log',
        'delete': 'delete_poop_log'
    },
    'activity-logs': {
        'add': 'add_activity_log',
        'update': 'update_activity_log',
        'delete': 'delete_activity_log'
    },
    'weight-logs': {
        'add': 'add_weight_log',
        'update': 'update_weight_log',
        'delete': 'delete_weight_log'
    },
    'vomit-logs': {
        'add': 'add_vomit_log',
        'update': 'update_vomit_log',
        'delete': 'delete_vomit_log'
    }
}

def validate_log_type(log_type: str) -> bool:
    """유효한 로그 타입인지 확인합니다."""
    return log_type in LOG_TYPE_SCHEMAS

def get_date_from_request() -> date:
    """요청에서 날짜를 추출하고 검증합니다."""
    date_str = request.args.get('date')
    if not date_str:
        raise ValueError("날짜 파라미터(date)가 필요합니다.")
    
    return DateTimeUtils.validate_date_field(date_str, 'date')

# ================== 개별 로그 CRUD API ==================

@individual_logs_bp.route('/<log_type>', methods=['GET'])
@jwt_required()
def get_logs_by_type(pet_id: str, log_type: str):
    """
    특정 타입의 로그 목록을 조회합니다.
    
    Path Parameters:
        log_type: 로그 타입 (food-logs, water-logs, etc.)
        
    Query Parameters:
        date (optional): 특정 날짜의 로그만 조회
        limit (optional): 조회할 로그 개수 제한
        
    Response:
        200: 로그 목록
        400: 잘못된 로그 타입 또는 파라미터
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 로그 타입 검증
        if not validate_log_type(log_type):
            return jsonify({
                "error_code": "INVALID_LOG_TYPE",
                "message": f"지원하지 않는 로그 타입입니다: {log_type}"
            }), 400
        
        # 날짜 파라미터 처리 (선택적)
        log_date = None
        if request.args.get('date'):
            try:
                log_date = get_date_from_request()
            except ValueError as e:
                return jsonify({
                    "error_code": "INVALID_DATE_FORMAT",
                    "message": str(e)
                }), 400
        
        # 특정 날짜의 로그 조회
        if log_date:
            daily_log = pet_care_service.get_daily_log(pet_id, user_id, log_date)
            if not daily_log:
                return jsonify({
                    "logs": [],
                    "total_count": 0,
                    "date": log_date.strftime('%Y-%m-%d')
                }), 200
            
            # 로그 타입에 따라 해당 로그들만 추출
            log_field = log_type.replace('-', '_')  # food-logs -> food_logs
            logs = getattr(daily_log, log_field, [])
            
            # 로그 데이터를 직렬화 가능한 형태로 변환
            serialized_logs = []
            for log in logs:
                if hasattr(log, '__dict__'):
                    # dataclass 객체인 경우
                    serialized_logs.append(vars(log))
                elif isinstance(log, dict):
                    # 이미 딕셔너리인 경우
                    serialized_logs.append(log)
                else:
                    # 기타 경우 - 문자열로 변환 후 처리 시도
                    try:
                        serialized_logs.append(log.__dict__ if hasattr(log, '__dict__') else str(log))
                    except:
                        serialized_logs.append(str(log))
            
            return jsonify({
                "logs": serialized_logs,
                "total_count": len(logs),
                "date": log_date.strftime('%Y-%m-%d')
            }), 200
        
        # 날짜 지정 없이 조회하는 경우는 추후 구현 (페이지네이션 필요)
        return jsonify({
            "error_code": "DATE_REQUIRED",
            "message": "현재는 특정 날짜의 로그만 조회 가능합니다. date 파라미터를 추가해주세요."
        }), 400
        
    except PermissionError as e:
        logger.warning(f"로그 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"로그 조회 실패 ({pet_id}, {log_type}): {e}", exc_info=True)
        return jsonify({
            "error_code": "LOG_FETCH_FAILED",
            "message": "로그 조회 중 오류가 발생했습니다."
        }), 500

@individual_logs_bp.route('/<log_type>', methods=['POST'])
@jwt_required()
def create_log(pet_id: str, log_type: str):
    """
    새로운 로그를 추가합니다.
    
    Path Parameters:
        log_type: 로그 타입 (food-logs, water-logs, etc.)
        
    Request Body:
        로그 타입에 따른 필드들 (timestamp는 필수)
        
    Response:
        201: 로그 생성 성공
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
        
        # 로그 타입 검증
        if not validate_log_type(log_type):
            return jsonify({
                "error_code": "INVALID_LOG_TYPE",
                "message": f"지원하지 않는 로그 타입입니다: {log_type}"
            }), 400
        
        # 요청 데이터 유효성 검사
        schema_class = LOG_TYPE_SCHEMAS[log_type]
        try:
            log_data = schema_class().load(request.get_json())
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 날짜 추출 (timestamp에서)
        timestamp = log_data.get('timestamp')
        log_date = timestamp.date() if timestamp else DateTimeUtils.today()
        
        # 서비스 메서드 호출
        service_method_name = LOG_TYPE_SERVICE_METHODS[log_type]['add']
        service_method = getattr(pet_care_service, service_method_name)
        
        created_log_id = service_method(pet_id, user_id, log_date, log_data)
        
        # 응답 데이터 생성 (log_id만 반환)
        response_data = {"log_id": created_log_id}
        
        logger.info(f"{log_type} 생성 성공: {pet_id} - {created_log_id}")
        return jsonify(response_data), 201
        
    except PermissionError as e:
        logger.warning(f"{log_type} 생성 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"{log_type} 생성 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "LOG_CREATION_FAILED",
            "message": f"{log_type} 생성 중 오류가 발생했습니다."
        }), 500

@individual_logs_bp.route('/<log_type>/<log_id>', methods=['GET'])
@jwt_required()
def get_log_by_id(pet_id: str, log_type: str, log_id: str):
    """
    특정 로그를 ID로 조회합니다.
    
    Path Parameters:
        log_type: 로그 타입
        log_id: 로그 ID
        
    Query Parameters:
        date (required): 해당 로그가 속한 날짜
        
    Response:
        200: 로그 데이터
        404: 로그를 찾을 수 없음
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 로그 타입 검증
        if not validate_log_type(log_type):
            return jsonify({
                "error_code": "INVALID_LOG_TYPE",
                "message": f"지원하지 않는 로그 타입입니다: {log_type}"
            }), 400
        
        # 날짜 파라미터 필수
        try:
            log_date = get_date_from_request()
        except ValueError as e:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": str(e)
            }), 400
        
        # 일일 로그에서 특정 로그 찾기
        daily_log = pet_care_service.get_daily_log(pet_id, user_id, log_date)
        if not daily_log:
            return jsonify({
                "error_code": "DAILY_LOG_NOT_FOUND",
                "message": "해당 날짜의 로그를 찾을 수 없습니다."
            }), 404
        
        # 로그 타입에 따라 해당 로그 찾기
        log_field = log_type.replace('-', '_')
        logs = getattr(daily_log, log_field, [])
        
        target_log = None
        for log in logs:
            if log.log_id == log_id:
                target_log = log
                break
        
        if not target_log:
            return jsonify({
                "error_code": "LOG_NOT_FOUND",
                "message": f"ID {log_id}인 {log_type}을 찾을 수 없습니다."
            }), 404
        
        # 응답 데이터 생성
        schema_class = LOG_TYPE_SCHEMAS[log_type]
        response_data = schema_class().dump(target_log)
        
        logger.info(f"{log_type} 조회 성공: {pet_id} - {log_id}")
        return jsonify(response_data), 200
        
    except PermissionError as e:
        logger.warning(f"{log_type} 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"{log_type} 조회 실패 ({pet_id}, {log_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "LOG_FETCH_FAILED",
            "message": f"{log_type} 조회 중 오류가 발생했습니다."
        }), 500

@individual_logs_bp.route('/<log_type>/<log_id>', methods=['PUT'])
@jwt_required()
def update_log(pet_id: str, log_type: str, log_id: str):
    """
    기존 로그를 수정합니다.
    
    Path Parameters:
        log_type: 로그 타입
        log_id: 로그 ID
        
    Query Parameters:
        date (required): 해당 로그가 속한 날짜
        
    Request Body:
        수정할 필드들
        
    Response:
        200: 로그 수정 성공
        404: 로그를 찾을 수 없음
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 로그 타입 검증
        if not validate_log_type(log_type):
            return jsonify({
                "error_code": "INVALID_LOG_TYPE",
                "message": f"지원하지 않는 로그 타입입니다: {log_type}"
            }), 400
        
        # 날짜 파라미터 필수
        try:
            log_date = get_date_from_request()
        except ValueError as e:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": str(e)
            }), 400
        
        # 요청 데이터 유효성 검사 (부분 업데이트)
        schema_class = LOG_TYPE_SCHEMAS[log_type]
        try:
            update_data = schema_class(partial=True).load(request.get_json())
        except ValidationError as err:
            return jsonify({
                "error_code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": err.messages
            }), 400
        
        # 서비스 메서드 호출
        service_method_name = LOG_TYPE_SERVICE_METHODS[log_type]['update']
        service_method = getattr(pet_care_service, service_method_name)
        
        updated_log = service_method(pet_id, user_id, log_date, log_id, update_data)
        
        if not updated_log:
            return jsonify({
                "error_code": "LOG_NOT_FOUND",
                "message": f"ID {log_id}인 {log_type}을 찾을 수 없습니다."
            }), 404
        
        # 응답 데이터 생성
        response_data = schema_class().dump(updated_log)
        
        logger.info(f"{log_type} 수정 성공: {pet_id} - {log_id}")
        return jsonify(response_data), 200
        
    except PermissionError as e:
        logger.warning(f"{log_type} 수정 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"{log_type} 수정 실패 ({pet_id}, {log_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "LOG_UPDATE_FAILED",
            "message": f"{log_type} 수정 중 오류가 발생했습니다."
        }), 500

@individual_logs_bp.route('/<log_type>/<log_id>', methods=['DELETE'])
@jwt_required()
def delete_log(pet_id: str, log_type: str, log_id: str):
    """
    기존 로그를 삭제합니다.
    
    Path Parameters:
        log_type: 로그 타입
        log_id: 로그 ID
        
    Query Parameters:
        date (required): 해당 로그가 속한 날짜
        
    Response:
        204: 로그 삭제 성공
        404: 로그를 찾을 수 없음
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 로그 타입 검증
        if not validate_log_type(log_type):
            return jsonify({
                "error_code": "INVALID_LOG_TYPE",
                "message": f"지원하지 않는 로그 타입입니다: {log_type}"
            }), 400
        
        # 날짜 파라미터 필수
        try:
            log_date = get_date_from_request()
        except ValueError as e:
            return jsonify({
                "error_code": "INVALID_DATE_FORMAT",
                "message": str(e)
            }), 400
        
        # 서비스 메서드 호출
        service_method_name = LOG_TYPE_SERVICE_METHODS[log_type]['delete']
        service_method = getattr(pet_care_service, service_method_name)
        
        success = service_method(pet_id, user_id, log_date, log_id)
        
        if not success:
            return jsonify({
                "error_code": "LOG_NOT_FOUND",
                "message": f"ID {log_id}인 {log_type}을 찾을 수 없습니다."
            }), 404
        
        logger.info(f"{log_type} 삭제 성공: {pet_id} - {log_id}")
        return '', 204
        
    except PermissionError as e:
        logger.warning(f"{log_type} 삭제 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"{log_type} 삭제 실패 ({pet_id}, {log_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "LOG_DELETE_FAILED",
            "message": f"{log_type} 삭제 중 오류가 발생했습니다."
        }), 500

# ================== 에러 핸들러 ==================

@individual_logs_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Marshmallow 유효성 검사 오류 처리"""
    return jsonify({
        "error_code": "VALIDATION_ERROR",
        "message": "요청 데이터가 유효하지 않습니다.",
        "details": error.messages
    }), 400
