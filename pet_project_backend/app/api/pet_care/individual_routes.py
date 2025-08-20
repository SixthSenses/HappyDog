# app/api/pet_care/individual_routes.py
import logging
from datetime import date, datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from .schemas import (
    FoodLogSchema, WaterLogSchema, PoopLogSchema, ActivityLogSchema,
    WeightLogSchema, VomitLogSchema
)

logger = logging.getLogger(__name__)

def get_pet_care_service():
    """현재 앱에서 PetCareService 인스턴스를 가져옵니다."""
    return current_app.services.get('pet_care')

def register_individual_routes(bp: Blueprint):
    """개별 로그 CRUD 라우트를 등록합니다."""
    
    # ================== 개별 로그 추가 API ==================
    
    @bp.route('/pets/<pet_id>/care-logs/food', methods=['POST'])
    @jwt_required()
    def add_food_log(pet_id: str):
        """새로운 음식 기록을 추가합니다."""
        return _handle_add_log(pet_id, 'food', FoodLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/water', methods=['POST'])
    @jwt_required()
    def add_water_log(pet_id: str):
        """새로운 물 섭취 기록을 추가합니다."""
        return _handle_add_log(pet_id, 'water', WaterLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/poop', methods=['POST'])
    @jwt_required()
    def add_poop_log(pet_id: str):
        """새로운 배변 기록을 추가합니다."""
        return _handle_add_log(pet_id, 'poop', PoopLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/activity', methods=['POST'])
    @jwt_required()
    def add_activity_log(pet_id: str):
        """새로운 활동 기록을 추가합니다."""
        return _handle_add_log(pet_id, 'activity', ActivityLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/weight', methods=['POST'])
    @jwt_required()
    def add_weight_log(pet_id: str):
        """새로운 체중 기록을 추가합니다."""
        return _handle_add_log(pet_id, 'weight', WeightLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/vomit', methods=['POST'])
    @jwt_required()
    def add_vomit_log(pet_id: str):
        """새로운 구토 기록을 추가합니다."""
        return _handle_add_log(pet_id, 'vomit', VomitLogSchema)

    # ================== 수정 API ==================
    
    @bp.route('/pets/<pet_id>/care-logs/food/<food_log_id>', methods=['PATCH'])
    @jwt_required()
    def update_food_log(pet_id: str, food_log_id: str):
        return _handle_update_log(pet_id, food_log_id, 'food', FoodLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/water/<water_log_id>', methods=['PATCH'])
    @jwt_required()
    def update_water_log(pet_id: str, water_log_id: str):
        return _handle_update_log(pet_id, water_log_id, 'water', WaterLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/poop/<poop_log_id>', methods=['PATCH'])
    @jwt_required()
    def update_poop_log(pet_id: str, poop_log_id: str):
        return _handle_update_log(pet_id, poop_log_id, 'poop', PoopLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/activity/<activity_log_id>', methods=['PATCH'])
    @jwt_required()
    def update_activity_log(pet_id: str, activity_log_id: str):
        return _handle_update_log(pet_id, activity_log_id, 'activity', ActivityLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/weight/<weight_log_id>', methods=['PATCH'])
    @jwt_required()
    def update_weight_log(pet_id: str, weight_log_id: str):
        return _handle_update_log(pet_id, weight_log_id, 'weight', WeightLogSchema)

    @bp.route('/pets/<pet_id>/care-logs/vomit/<vomit_log_id>', methods=['PATCH'])
    @jwt_required()
    def update_vomit_log(pet_id: str, vomit_log_id: str):
        return _handle_update_log(pet_id, vomit_log_id, 'vomit', VomitLogSchema)

    # ================== 삭제 API ==================
    
    @bp.route('/pets/<pet_id>/care-logs/food/<food_log_id>', methods=['DELETE'])
    @jwt_required()
    def delete_food_log(pet_id: str, food_log_id: str):
        return _handle_delete_log(pet_id, food_log_id, 'food')

    @bp.route('/pets/<pet_id>/care-logs/water/<water_log_id>', methods=['DELETE'])
    @jwt_required()
    def delete_water_log(pet_id: str, water_log_id: str):
        return _handle_delete_log(pet_id, water_log_id, 'water')

    @bp.route('/pets/<pet_id>/care-logs/poop/<poop_log_id>', methods=['DELETE'])
    @jwt_required()
    def delete_poop_log(pet_id: str, poop_log_id: str):
        return _handle_delete_log(pet_id, poop_log_id, 'poop')

    @bp.route('/pets/<pet_id>/care-logs/activity/<activity_log_id>', methods=['DELETE'])
    @jwt_required()
    def delete_activity_log(pet_id: str, activity_log_id: str):
        return _handle_delete_log(pet_id, activity_log_id, 'activity')

    @bp.route('/pets/<pet_id>/care-logs/weight/<weight_log_id>', methods=['DELETE'])
    @jwt_required()
    def delete_weight_log(pet_id: str, weight_log_id: str):
        return _handle_delete_log(pet_id, weight_log_id, 'weight')

    @bp.route('/pets/<pet_id>/care-logs/vomit/<vomit_log_id>', methods=['DELETE'])
    @jwt_required()
    def delete_vomit_log(pet_id: str, vomit_log_id: str):
        return _handle_delete_log(pet_id, vomit_log_id, 'vomit')

    # ================== 빠른 증감 기능 ==================

    @bp.route('/pets/<pet_id>/care-logs/quick-add', methods=['POST'])
    @jwt_required()
    def quick_add_total(pet_id: str):
        """빠른 증감 기능: 총량 필드를 직접 증감합니다."""
        try:
            user_id = get_jwt_identity()
            service = get_pet_care_service()
            
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

def _handle_add_log(pet_id: str, log_type: str, schema_class):
    """로그 추가를 처리하는 헬퍼 함수"""
    try:
        user_id = get_jwt_identity()
        service = get_pet_care_service()
        
        if not service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 요청 데이터 유효성 검사
        try:
            request_data = request.get_json()
            log_data = schema_class(exclude=['log_id']).load(request_data)
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
        
        # 로그 추가
        method_name = f"add_{log_type}_log"
        add_method = getattr(service, method_name)
        log = add_method(pet_id, user_id, log_date, log_data)
        
        # 응답 데이터 생성
        response_data = schema_class().dump(log)
        
        logger.info(f"{log_type} 기록 추가 성공: {pet_id} - {log.log_id}")
        return jsonify({
            "message": f"{log_type} 기록이 성공적으로 추가되었습니다.",
            f"{log_type}_log": response_data
        }), 201
        
    except PermissionError as e:
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"{log_type} 기록 추가 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": f"{log_type.upper()}_LOG_CREATION_FAILED",
            "message": f"{log_type} 기록 추가 중 오류가 발생했습니다."
        }), 500

def _handle_update_log(pet_id: str, log_id: str, log_type: str, schema_class):
    """로그 수정을 처리하는 헬퍼 함수"""
    try:
        user_id = get_jwt_identity()
        service = get_pet_care_service()
        
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
        
        # 로그 수정
        method_name = f"update_{log_type}_log"
        update_method = getattr(service, method_name)
        updated_log = update_method(pet_id, user_id, log_date, log_id, update_data)
        
        if not updated_log:
            return jsonify({
                "error_code": "LOG_NOT_FOUND",
                "message": f"수정할 {log_type} 기록을 찾을 수 없습니다."
            }), 404
        
        # 응답 데이터 생성
        response_data = schema_class().dump(updated_log)
        
        logger.info(f"{log_type} 기록 수정 성공: {pet_id} - {log_id}")
        return jsonify({
            "message": f"{log_type} 기록이 성공적으로 수정되었습니다.",
            f"{log_type}_log": response_data
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
        logger.error(f"{log_type} 기록 수정 실패 ({pet_id}, {log_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": f"{log_type.upper()}_LOG_UPDATE_FAILED",
            "message": f"{log_type} 기록 수정 중 오류가 발생했습니다."
        }), 500

def _handle_delete_log(pet_id: str, log_id: str, log_type: str):
    """로그 삭제를 처리하는 헬퍼 함수"""
    try:
        user_id = get_jwt_identity()
        service = get_pet_care_service()
        
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
        
        # 로그 삭제
        method_name = f"delete_{log_type}_log"
        delete_method = getattr(service, method_name)
        success = delete_method(pet_id, user_id, log_date, log_id)
        
        if success:
            logger.info(f"{log_type} 기록 삭제 성공: {pet_id} - {log_id}")
            return jsonify({
                "message": f"{log_type} 기록이 성공적으로 삭제되었습니다."
            }), 200
        else:
            return jsonify({
                "error_code": "LOG_NOT_FOUND",
                "message": f"삭제할 {log_type} 기록을 찾을 수 없습니다."
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
        logger.error(f"{log_type} 기록 삭제 실패 ({pet_id}, {log_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": f"{log_type.upper()}_LOG_DELETE_FAILED",
            "message": f"{log_type} 기록 삭제 중 오류가 발생했습니다."
        }), 500
