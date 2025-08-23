# app/api/pet_care/records/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
import datetime

from app.api.pet_care.records.schemas import (
    CareRecordCreateSchema, 
    DailyRecordsResponseSchema,
    RecordsQuerySchema,
    RecordsResponseSchema,
    RecordTypeQuerySchema
)

pet_care_records_bp = Blueprint('pet_care_records_bp', __name__)

@pet_care_records_bp.route('/<string:pet_id>/records', methods=['POST'])
@jwt_required()
def create_care_record(pet_id: str):
    """통합 기록 생성 API 엔드포인트."""
    service = current_app.services['pet_care_records']
    try:
        validated_data = CareRecordCreateSchema().load(request.get_json())
        created_record = service.create_care_record(pet_id, validated_data)
        return jsonify(created_record), 201
        
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"기록 생성 API 오류 (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "RECORD_CREATION_FAILED", "message": "기록 생성 중 오류 발생"}), 500

@pet_care_records_bp.route('/<string:pet_id>/records', methods=['GET'])
@jwt_required()
def get_records(pet_id: str):
    """
    [개선된] 유연한 쿼리 파라미터를 지원하는 케어 기록 조회 API.
    서버 사이드 필터링과 커서 기반 페이지네이션을 사용합니다.
    
    쿼리 파라미터:
    - date: 단일 날짜 조회 (YYYY-MM-DD)
    - start_date, end_date: 날짜 범위 조회 (YYYY-MM-DD)
    - record_types: 필터링할 기록 타입 (weight,water,activity,meal)
    - grouped: 타입별 그룹화 여부 (true/false)
    - limit: 조회 개수 제한 (1-100, 기본값: 50)
    - cursor: 커서 기반 페이지네이션 (다음 페이지 조회용)
    - sort: 정렬 방식 (timestamp_asc, timestamp_desc, 기본값: timestamp_desc)
    
    예시:
    - GET /records?date=2024-12-24&grouped=true
    - GET /records?start_date=2024-12-20&end_date=2024-12-24&record_types=weight,meal&limit=20
    - GET /records?date=2024-12-24&record_types=water&limit=10&sort=timestamp_asc
    - GET /records?date=2024-12-24&limit=10&cursor=last_document_id (다음 페이지)
    """
    service = current_app.services['pet_care_records']
    
    try:
        # 쿼리 파라미터 검증 (스키마에서 전처리 포함)
        query_schema = RecordsQuerySchema()
        validated_params = query_schema.load(request.args)
        
        # 유연한 조회 실행
        result = service.get_records_flexible(pet_id, validated_params)
        
        # 응답 스키마로 직렬화
        response_schema = RecordsResponseSchema()
        return jsonify(response_schema.dump(result)), 200
        
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"Record retrieval API error (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "FETCH_FAILED", "message": "기록 조회 중 오류가 발생했습니다."}), 500

@pet_care_records_bp.route('/<string:pet_id>/records/<string:record_type>', methods=['GET'])
@jwt_required()
def get_records_by_type(pet_id: str, record_type: str):
    """
    [개선된] 특정 타입의 케어 기록만 조회하는 API.
    커서 기반 페이지네이션을 지원합니다.
    
    쿼리 파라미터:
    - date: 단일 날짜 조회 (YYYY-MM-DD)
    - start_date, end_date: 날짜 범위 조회 (YYYY-MM-DD)
    - limit: 조회 개수 제한 (1-100, 기본값: 50)
    - cursor: 커서 기반 페이지네이션 (다음 페이지 조회용)
    
    예시:
    - GET /records/weight?date=2024-12-24
    - GET /records/meal?start_date=2024-12-20&end_date=2024-12-24&limit=20
    - GET /records/activity?limit=10&cursor=last_document_id (다음 페이지)
    """
    service = current_app.services['pet_care_records']
    
    # record_type 검증
    valid_types = ['weight', 'water', 'activity', 'meal']
    if record_type not in valid_types:
        return jsonify({
            "error_code": "INVALID_RECORD_TYPE", 
            "message": f"유효하지 않은 기록 타입입니다. 가능한 타입: {', '.join(valid_types)}"
        }), 400
    
    try:
        # 일관된 스키마 사용으로 파라미터 검증
        query_schema = RecordTypeQuerySchema()
        validated_params = query_schema.load(request.args)
        
        # 조회 실행
        result = service.get_records_by_type(
            pet_id=pet_id,
            record_type=record_type,
            date_str=validated_params.get('date'),
            start_date=validated_params.get('start_date'),
            end_date=validated_params.get('end_date'),
            limit=validated_params.get('limit', 50),
            cursor=validated_params.get('cursor')
        )
        
        return jsonify(result), 200
        
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"Record type retrieval API error (pet_id: {pet_id}, type: {record_type}): {e}", exc_info=True)
        return jsonify({"error_code": "FETCH_FAILED", "message": "기록 조회 중 오류가 발생했습니다."}), 500

# 기존 호환성을 위한 엔드포인트 (deprecated)
@pet_care_records_bp.route('/<string:pet_id>/records/legacy', methods=['GET'])
@jwt_required()
def get_records_legacy(pet_id: str):
    """
    [Deprecated] 기존 호환성을 위한 레거시 엔드포인트.
    새로운 get_records 엔드포인트 사용을 권장합니다.
    """
    service = current_app.services['pet_care_records']
    date_str = request.args.get('date')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    try:
        # 분기 1: 기간 조회 (start_date와 end_date가 모두 제공된 경우)
        if start_date_str and end_date_str:
            # 파라미터 유효성 검사
            datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
            datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
            
            records = service.get_records_for_date_range(pet_id, start_date_str, end_date_str)
            # 기간 조회 결과는 DailyRecordsResponseSchema와 형식이 다르므로 그대로 반환
            return jsonify(records), 200

        # 분기 2: 일일 조회 (date 파라미터만 제공된 경우)
        elif date_str:
            datetime.datetime.strptime(date_str, '%Y-%m-%d')
            daily_records = service.get_daily_records(pet_id, date_str)
            return jsonify(DailyRecordsResponseSchema().dump(daily_records)), 200
        
        # 분기 3: 파라미터가 잘못된 경우
        else:
            return jsonify({
                "error_code": "MISSING_PARAMETERS",
                "message": "조회를 위해 'date' 또는 'start_date'와 'end_date' 쿼리 파라미터가 필요합니다."
            }), 400

    except ValueError:
        return jsonify({"error_code": "INVALID_DATE_FORMAT", "message": "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)."}), 400
    except Exception as e:
        logging.error(f"Record retrieval API error (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "FETCH_FAILED", "message": "기록 조회 중 오류가 발생했습니다."}), 500