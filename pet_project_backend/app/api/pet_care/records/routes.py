# app/api/pet_care/records/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app, Response
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from app.utils.error_catalog import build_error
from app.utils.datetime_utils import DateTimeUtils

from app.api.pet_care.records.schemas import (
    CareRecordCreateSchema,
    CareRecordUpdateSchema,
    DailyRecordsQuerySchema,
    RecordResponseSchema,
    DailyRecordsResponseSchema,
    DailySummaryWithGoalsResponseSchema,
    RangeQuerySchema,
    RangeSummaryWithTrendsResponseSchema,
    DeleteRecordResponseSchema
)
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, PetCareErrors
)
from app.middleware.idempotency_middleware import idempotent_endpoint

pet_care_records_bp = Blueprint('pet_care_records_bp', __name__)

@pet_care_records_bp.route('/<string:pet_id>/records', methods=['POST'])
@jwt_required()
@idempotent_endpoint(apply_when_methods=('POST',))
def create_care_record(pet_id: str):
    """펫케어 기록 생성

    개별 펫케어 기록을 생성합니다. 각 기록 타입(식사횟수, 활동량, BCS, 체중, 대변, 구토)을 개별적으로 기록할 수 있습니다.

    RequestSchema: CareRecordCreateSchema
    ResponseSchema[201]: RecordResponseSchema
    """
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
def update_care_record(pet_id: str, log_id: str):
    """펫케어 기록 수정

    기존 펫케어 기록을 수정합니다.

    RequestSchema: CareRecordUpdateSchema
    ResponseSchema[200]: RecordResponseSchema
    """
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
        status, body = build_error('NOT_FOUND')
        return jsonify(body), status
    except Exception as e:
        logging.error(f"기록 수정 오류 (pet_id: {pet_id}, log_id: {log_id}): {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED')
        return jsonify(body), status

@pet_care_records_bp.route('/<string:pet_id>/records/<string:log_id>', methods=['DELETE'])
@jwt_required()
def delete_care_record(pet_id: str, log_id: str):
    """펫케어 기록 삭제

    기존 펫케어 기록을 삭제합니다.

    ResponseSchema[204]: NoContentSchema
    """
    service = current_app.services['pet_care_records']
    try:
        # 기록 삭제
        service.delete_record(pet_id, log_id)
        # 204 No Content 계약으로 일치
        return Response(status=204)
        
    except FileNotFoundError:
        status, body = build_error('NOT_FOUND')
        return jsonify(body), status
    except Exception as e:
        logging.error(f"기록 삭제 오류 (pet_id: {pet_id}, log_id: {log_id}): {e}", exc_info=True)
        status, body = build_error('DELETE_FAILED')
        return jsonify(body), status

@pet_care_records_bp.route('/<string:pet_id>/records/daily', methods=['GET'])
@jwt_required()
def get_daily_records(pet_id: str):
    """특정 날짜 펫케어 기록 조회

    특정 날짜에 기록된 모든 펫케어 데이터를 조회합니다.

    ResponseSchema[200]: DailyRecordsResponseSchema
    """
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


@pet_care_records_bp.route('/<string:pet_id>/records/daily/summary', methods=['GET'])
@jwt_required()
def get_daily_summary_with_goals(pet_id: str):
    """특정 날짜 요약 + 목표 진행률 조회

    UI의 오늘/특정일 달성률, 개수, 간단 요약을 반환합니다.

    ResponseSchema[200]: DailySummaryWithGoalsResponseSchema
    """
    integration_service = current_app.services.get('pet_care_integration')
    base_service = current_app.services['pet_care_records']
    try:
        date = request.args.get('date') or DateTimeUtils.today_kst_as_date_str()
        if integration_service:
            summary = integration_service.get_daily_summary_with_goals(pet_id, date)
            return jsonify(DailySummaryWithGoalsResponseSchema().dump(summary)), 200
        # 통합 서비스가 없는 환경에서는 기본 조회 결과만 반환(호환)
        result = base_service.get_daily_records(pet_id, date)
        fallback = {
            'date': date,
            'records': result.get('records', []),
            'record_counts': {},
            'meta': result.get('summary', {})
        }
        return jsonify(DailySummaryWithGoalsResponseSchema().dump(fallback)), 200
    except Exception as e:
        logging.error(f"일별 요약/목표 조회 오류 (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED')
        return jsonify(body), status


@pet_care_records_bp.route('/<string:pet_id>/records/summary/range', methods=['GET'])
@jwt_required()
def get_range_summary_with_trends(pet_id: str):
    """기간 요약 + 트렌드 + 목표 추적 조회

    월간 분석 카드/문구를 구성하는 데이터에 대응합니다.

    ResponseSchema[200]: RangeSummaryWithTrendsResponseSchema
    """
    integration_service = current_app.services.get('pet_care_integration')
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        if not start_date or not end_date:
            raise ValidationError({'date_range': ['start_date와 end_date가 필요합니다.']})
        if integration_service:
            summary = integration_service.get_range_summary_with_trends(pet_id, start_date, end_date)
            return jsonify(RangeSummaryWithTrendsResponseSchema().dump(summary)), 200
        # 통합 서비스 없을 때는 최소 호환 스켈레톤 반환
        skeleton = {
            'start_date': start_date,
            'end_date': end_date,
            'records_by_date': {},
            'meta': {},
            'trends': {},
        }
        return jsonify(RangeSummaryWithTrendsResponseSchema().dump(skeleton)), 200
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except Exception as e:
        logging.error(f"기간 요약/트렌드 조회 오류 (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED')
        return jsonify(body), status
