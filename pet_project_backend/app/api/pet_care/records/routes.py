# app/api/pet_care/records/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
import datetime

from app.api.pet_care.records.schemas import CareRecordCreateSchema, DailyRecordsResponseSchema

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
    일일 또는 기간별 케어 기록을 조회합니다.
    - ?date=YYYY-MM-DD : 특정일 조회
    - ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD : 기간 조회
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