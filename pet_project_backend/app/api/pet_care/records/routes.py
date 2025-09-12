# app/api/pet_care/records/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from app.utils.error_catalog import build_error
from app.utils.datetime_utils import DateTimeUtils

from app.api.pet_care.records.schemas import (
    CareRecordCreateSchema,
    CareRecordUpdateSchema,
    DailyRecordsQuerySchema,
    RecordResponseSchema,
    DailyRecordsResponseSchema
)
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, PetCareErrors
)

pet_care_records_bp = Blueprint('pet_care_records_bp', __name__)

@pet_care_records_bp.route('/<string:pet_id>/records', methods=['POST'])
@jwt_required()
@api_doc(
    summary="펫케어 기록 생성",
    description="개별 펫케어 기록을 생성합니다. 각 기록 타입(식사횟수, 활동량, BCS, 체중, 대변, 구토)을 개별적으로 기록할 수 있습니다.",
    tags=["pet_care"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.RECORD_CREATION_FAILED,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "create_meal_count_record",
    "summary": "식사 횟수 기록",
    "description": "하루 식사 횟수를 기록합니다",
    "value": {
        "record_type": "meal_count",
        "timestamp": 1704067200000,
        "data": 3,
        "memo": "오늘 3회 식사"
    }
}, {
    "name": "create_activity_record",
    "summary": "활동량 기록",
    "description": "활동량을 분 단위로 기록합니다",
    "value": {
        "record_type": "activity",
        "timestamp": 1704070800000,
        "data": 60,
        "memo": "산책 1시간"
    }
}, {
    "name": "create_weight_record",
    "summary": "체중 기록",
    "description": "반려동물의 체중을 기록합니다",
    "value": {
        "record_type": "weight",
        "timestamp": 1704074400000,
        "data": 26.5,
        "memo": "정기 체중 측정"
    }
})
@response_examples({
    "name": "record_created",
    "summary": "기록 생성 성공",
    "description": "생성된 펫케어 기록 정보",
    "value": {
        "log_id": "rec_123",
        "pet_id": "pet_123",
        "record_type": "meal_count",
        "timestamp": 1704067200000,
        "timestamp_ms": 1704067200000,
        "data": 3,
        "memo": "오늘 3회 식사",
        "searchDate": "2024-01-01"
    }
})
def create_care_record(pet_id: str):
    """개별 펫케어 기록을 생성합니다."""
    service = current_app.services['pet_care_records']
    integration_service = current_app.services.get('pet_care_integration')
    
    try:
        # 요청 데이터 검증
        payload = CareRecordCreateSchema().load(request.get_json() or {})
        
        # user_id를 JWT에서 가져와서 알림용으로 추가
        from flask_jwt_extended import get_jwt_identity
        user_id = get_jwt_identity()
        payload['user_id'] = user_id
        
        # 통합 서비스가 있으면 목표 분석과 알림 기능 사용, 없으면 기본 서비스 사용
        if integration_service:
            result = integration_service.create_record_with_goals(pet_id, payload)
        else:
            result = service.create_record(pet_id, payload)
        
        return jsonify(RecordResponseSchema().dump(result)), 201
        
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except Exception as e:
        logging.error(f"기록 생성 API 오류 (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('RECORD_CREATION_FAILED')
        return jsonify(body), status

@pet_care_records_bp.route('/<string:pet_id>/records/<string:log_id>', methods=['PATCH'])
@jwt_required()
@api_doc(
    summary="펫케어 기록 수정",
    description="기존 펫케어 기록을 수정합니다.",
    tags=["pet_care"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.RESOURCE_NOT_FOUND,
    CommonErrors.UPDATE_FAILED
)
@request_examples({
    "name": "update_record",
    "summary": "기록 수정",
    "description": "기록 데이터나 메모를 수정합니다",
    "value": {
        "data": 4,
        "memo": "수정된 식사 횟수"
    }
})
@response_examples({
    "name": "record_updated",
    "summary": "기록 수정 성공",
    "description": "수정된 펫케어 기록 정보",
    "value": {
        "log_id": "rec_123",
        "pet_id": "pet_123",
        "record_type": "meal_count",
        "timestamp": 1704067200000,
        "timestamp_ms": 1704067200000,
        "data": 4,
        "memo": "수정된 식사 횟수",
        "searchDate": "2024-01-01"
    }
})
def update_care_record(pet_id: str, log_id: str):
    """기존 펫케어 기록을 수정합니다."""
    service = current_app.services['pet_care_records']
    try:
        # 요청 데이터 검증
        payload = CareRecordUpdateSchema().load(request.get_json() or {})
        
        # 기록 수정
        result = service.update_record(pet_id, log_id, payload)
        
        return jsonify(RecordResponseSchema().dump(result)), 200
        
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except FileNotFoundError:
        status, body = build_error('RESOURCE_NOT_FOUND')
        return jsonify(body), status
    except Exception as e:
        logging.error(f"기록 수정 오류 (pet_id: {pet_id}, log_id: {log_id}): {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED')
        return jsonify(body), status

@pet_care_records_bp.route('/<string:pet_id>/records/<string:log_id>', methods=['DELETE'])
@jwt_required()
@api_doc(
    summary="펫케어 기록 삭제",
    description="기존 펫케어 기록을 삭제합니다.",
    tags=["pet_care"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.RESOURCE_NOT_FOUND,
    CommonErrors.DELETE_FAILED
)
@response_examples({
    "name": "record_deleted",
    "summary": "기록 삭제 성공",
    "description": "삭제 완료 응답",
    "value": {
        "message": "기록이 성공적으로 삭제되었습니다.",
        "deleted_id": "rec_123"
    }
})
def delete_care_record(pet_id: str, log_id: str):
    """기존 펫케어 기록을 삭제합니다."""
    service = current_app.services['pet_care_records']
    try:
        # 기록 삭제
        service.delete_record(pet_id, log_id)
        
        return jsonify({
            "message": "기록이 성공적으로 삭제되었습니다.",
            "deleted_id": log_id
        }), 200
        
    except FileNotFoundError:
        status, body = build_error('RESOURCE_NOT_FOUND')
        return jsonify(body), status
    except Exception as e:
        logging.error(f"기록 삭제 오류 (pet_id: {pet_id}, log_id: {log_id}): {e}", exc_info=True)
        status, body = build_error('DELETE_FAILED')
        return jsonify(body), status

@pet_care_records_bp.route('/<string:pet_id>/records/daily', methods=['GET'])
@jwt_required()
@api_doc(
    summary="특정 날짜의 모든 펫케어 기록 조회",
    description="특정 날짜에 기록된 모든 펫케어 데이터를 조회합니다. 과거 기록 조회 시 각각의 기록을 추가할 수 있습니다.",
    tags=["pet_care"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.FETCH_FAILED,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "daily_records",
    "summary": "특정 날짜 기록 조회 성공",
    "description": "특정 날짜의 모든 펫케어 기록",
    "value": {
        "date": "2024-01-01",
        "records": [
            {
                "log_id": "rec_123",
                "pet_id": "pet_123",
                "record_type": "meal_count",
                "timestamp": 1704067200000,
                "timestamp_ms": 1704067200000,
                "data": 3,
                "memo": "오늘 3회 식사",
                "searchDate": "2024-01-01"
            },
            {
                "log_id": "rec_124",
                "pet_id": "pet_123",
                "record_type": "activity",
                "timestamp": 1704070800000,
                "timestamp_ms": 1704070800000,
                "data": 60,
                "memo": "산책 1시간",
                "searchDate": "2024-01-01"
            },
            {
                "log_id": "rec_125",
                "pet_id": "pet_123",
                "record_type": "weight",
                "timestamp": 1704074400000,
                "timestamp_ms": 1704074400000,
                "data": 26.5,
                "memo": "정기 체중 측정",
                "searchDate": "2024-01-01"
            }
        ],
        "summary": {
            "meal_count": 3,
            "activity_minutes": 60,
            "weight": 26.5,
            "bcs": None,
            "stool": None,
            "vomit": None
        }
    }
})
def get_daily_records(pet_id: str):
    """특정 날짜의 모든 펫케어 기록을 조회합니다."""
    service = current_app.services['pet_care_records']
    try:
        # 쿼리 파라미터에서 날짜 추출
        date = request.args.get('date')
        if not date:
            date = DateTimeUtils.today_kst_as_date_str()
        
        # 날짜별 기록 조회
        result = service.get_daily_records(pet_id, date)
        
        return jsonify(DailyRecordsResponseSchema().dump(result)), 200
        
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except Exception as e:
        logging.error(f"일별 기록 조회 오류 (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED')
        return jsonify(body), status
