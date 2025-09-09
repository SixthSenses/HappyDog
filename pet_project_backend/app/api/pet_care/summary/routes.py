# app/api/pet_care/summary/routes.py
"""Pet Care Summary API Endpoints (Sprint C)
=============================================
새로운 Summary 엔드포인트 구현
- 단일 날짜 요약: /api/pet-care/{pet_id}/summary?date=
- 범위 요약: /api/pet-care/{pet_id}/summary/range?start_date=&end_date=
"""
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from app.utils.error_catalog import build_error
from app.utils.etag_utils import generate_etag, check_if_none_match
from app.api.pet_care.summary.schemas import (
    SingleDateSummaryQuerySchema,
    RangeSummaryQuerySchema
)
import datetime

pet_care_summary_bp = Blueprint('pet_care_summary', __name__)

@pet_care_summary_bp.route('/<string:pet_id>/summary', methods=['GET'])
@jwt_required()
def get_single_date_summary(pet_id: str):
    """
    단일 날짜 요약 조회 (Sprint C)
    
    Query Parameters:
    - date: 조회할 날짜 (YYYY-MM-DD, 필수)
    - with_total: 전체 개수 포함 여부 (optional, 조건: limit ≤50 & 예상≤5000)
    
    Response:
    {
        "data": {
            "pet_id": "pet123",
            "date": "2024-12-24",
            "weight_latest": {"value": 5.2, "timestamp": 1703404800000},
            "water_intake_total": 150,
            "meal_count": 2,
            "activity_minutes": 30,
            "bcs_latest": {"value": 3, "timestamp": 1703404800000},
            "goals": {...},
            "progress_percent": {...},
            "updated_at": 1703404850000
        },
        "meta": {
            "computed_at": 1703404850000,
            "cache_hit": false
        }
    }
    """
    service = current_app.services['pet_care_records']
    
    try:
        # 파라미터 검증
        query_schema = SingleDateSummaryQuerySchema()
        validated_params = query_schema.load(request.args)
        date_str = validated_params['date']
        
        # ETag 체크 (304 Not Modified)
        cache_key = f"summary:{pet_id}:{date_str}"
        etag_value = generate_etag(cache_key)
        if check_if_none_match(request, etag_value):
            response = jsonify({})
            response.status_code = 304
            response.headers['ETag'] = f'"{etag_value}"'
            response.headers['Cache-Control'] = 'private, max-age=300'
            return response
        
        # 서비스 호출
        result = service.get_summary_single_day(pet_id, date_str)
        
        # updated_at 계산: max(last_record_timestamp, compute_finish_timestamp)
        compute_finish = datetime.datetime.now(datetime.timezone.utc)
        compute_finish_ms = int(compute_finish.timestamp() * 1000)
        
        last_record_ts = 0
        for record_type in ['weight', 'water', 'activity', 'meal', 'bcs']:
            records = result.get('data', {}).get(record_type, [])
            if records:
                for r in records:
                    if 'timestamp' in r:
                        last_record_ts = max(last_record_ts, r['timestamp'])
        # weight_latest / bcs_latest 표준화 (서비스 레이어 이미 표준화됨, 방어적 처리)
        wl = result.get('data', {}).get('weight_latest')
        if wl and 'timestamp' in wl and 'timestamp_ms' not in wl:
            wl['timestamp_ms'] = wl.pop('timestamp')
        bl = result.get('data', {}).get('bcs_latest')
        if bl and 'timestamp' in bl and 'timestamp_ms' not in bl:
            bl['timestamp_ms'] = bl.pop('timestamp')

        result['data']['updated_at'] = max(last_record_ts, compute_finish_ms)
        result['meta']['computed_at'] = compute_finish_ms
        result['meta']['cache_hit'] = False
        
        # with_total 처리 (단일 날짜는 일반적으로 총 개수가 적음)
        if validated_params.get('with_total'):
            total_count = sum([
                len(result.get('data', {}).get(rt, [])) 
                for rt in ['weight', 'water', 'activity', 'meal', 'bcs']
            ])
            if total_count <= 5000:  # 조건 충족
                result['meta']['total'] = total_count
        
        # ETag 설정
        response = jsonify(result)
        response.headers['ETag'] = f'"{etag_value}"'
        response.headers['Cache-Control'] = 'private, max-age=300'
        
        return response
        
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except Exception as e:
        logging.error(f"Single date summary error (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED')
        return jsonify(body), status


@pet_care_summary_bp.route('/<string:pet_id>/summary/range', methods=['GET'])
@jwt_required()
def get_range_summary(pet_id: str):
    """
    범위 요약 조회 (Sprint C)
    
    Query Parameters:
    - start_date: 시작 날짜 (YYYY-MM-DD, 필수)
    - end_date: 종료 날짜 (YYYY-MM-DD, 필수)
    
    Response:
    {
        "data": {
            "pet_id": "pet123",
            "interval": {
                "start_date": "2024-12-20",
                "end_date": "2024-12-24"
            },
            "metrics": {
                "weight": {"latest": 5.2, "count": 5},
                "water": {"total": 750, "count": 20},
                "activity": {"total": 150, "count": 10},
                "meal": {"total": 10, "count": 10},
                "bcs": {"latest": 3, "count": 2}
            },
            "updated_at": 1703404850000
        },
        "meta": {
            "computed_at": 1703404850000,
            "cache_hit": false
        }
    }
    """
    service = current_app.services['pet_care_records']
    
    try:
        # 파라미터 검증
        query_schema = RangeSummaryQuerySchema()
        validated_params = query_schema.load(request.args)
        start_date = validated_params['start_date']
        end_date = validated_params['end_date']
        
        # 범위 검증 (최대 31일)
        start_dt = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()
        if (end_dt - start_dt).days > 31:
            status, body = build_error('RANGE_TOO_LARGE', message='최대 31일 범위만 조회할 수 있습니다.')
            return jsonify(body), status

        # ETag 체크
        cache_key = f"summary_range:{pet_id}:{start_date}:{end_date}"
        etag_value = generate_etag(cache_key)
        if check_if_none_match(request, etag_value):
            response = jsonify({})
            response.status_code = 304
            response.headers['ETag'] = f'"{etag_value}"'
            response.headers['Cache-Control'] = 'private, max-age=600'
            return response

        # 서비스 호출
        result = service.get_summary_v2(pet_id, start_date, end_date)

        # updated_at 계산
        compute_finish = datetime.datetime.now(datetime.timezone.utc)
        compute_finish_ms = int(compute_finish.timestamp() * 1000)
        result['data']['updated_at'] = compute_finish_ms
        result['meta']['computed_at'] = compute_finish_ms
        result['meta']['cache_hit'] = False

        # ETag 설정
        response = jsonify(result)
        response.headers['ETag'] = f'"{etag_value}"'
        response.headers['Cache-Control'] = 'private, max-age=600'

        return response
        
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except Exception as e:
        logging.error(f"Range summary error (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED')
        return jsonify(body), status