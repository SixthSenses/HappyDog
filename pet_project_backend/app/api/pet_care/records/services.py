# app/api/pet_care/records/services.py
import logging
from typing import Dict, Any, List
from firebase_admin import firestore
import uuid
from dataclasses import asdict

from app.models.pet_care_log import PetCareLog
from app.utils.datetime_utils import DateTimeUtils

class PetCareRecordService:
    """일일 케어 기록의 생성 및 조회를 전담하는 서비스 클래스."""
    def __init__(self):
        self.db = firestore.client()
        self.logs_ref = self.db.collection('pet_care_logs')
        logging.info("PetCareRecordService initialized.")

    def create_care_record(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """통합된 케어 기록을 Firestore에 저장합니다."""
        try:
            ts_ms = record_data['timestamp']
            # Unix timestamp(ms)를 UTC datetime 객체로 변환
            record_dt_utc = DateTimeUtils.from_timestamp_ms(ts_ms)
            
            # 검색 및 필터링을 위한 searchDate 필드 생성 (YYYY-MM-DD)
            search_date = record_dt_utc.strftime('%Y-%m-%d')
            
            log_id = str(uuid.uuid4())
            new_log = PetCareLog(
                log_id=log_id,
                pet_id=pet_id,
                record_type=record_data['record_type'],
                timestamp=record_dt_utc,
                searchDate=search_date,
                data=record_data['data'],
                notes=record_data.get('notes')
            )
            
            log_dict = asdict(new_log)
            firestore_data = DateTimeUtils.for_firestore(log_dict)
            self.logs_ref.document(log_id).set(firestore_data)
            
            logging.info(f"Care record created for pet {pet_id} (type: {record_data['record_type']})")
            return log_dict

        except Exception as e:
            logging.error(f"Failed to create care record for pet {pet_id}: {e}", exc_info=True)
            raise

    def get_daily_records(self, pet_id: str, date_str: str) -> Dict[str, List[Dict]]:
        """특정 날짜의 모든 케어 기록을 타입별로 그룹화하여 조회합니다."""
        try:
            query = self.logs_ref \
                .where('pet_id', '==', pet_id) \
                .where('searchDate', '==', date_str) \
                .order_by('timestamp')
            
            docs = query.stream()
            
            grouped_records = {'weight': [], 'water': [], 'activity': [], 'meal': []}
            
            for doc in docs:
                record = doc.to_dict()
                record_type = record.get('record_type')
                if record_type in grouped_records:
                    # Firestore Timestamp를 다시 Unix timestamp(ms)로 변환하여 응답
                    timestamp_obj = record.get('timestamp')
                    if timestamp_obj:
                        record['timestamp'] = DateTimeUtils.to_timestamp_ms(timestamp_obj)
                    grouped_records[record_type].append(record)
            
            return grouped_records

        except Exception as e:
            logging.error(f"Failed to get daily records for pet {pet_id} on {date_str}: {e}", exc_info=True)
            raise
    def get_records_for_date_range(self, pet_id: str, start_date: str, end_date: str) -> Dict[str, List[Dict]]:
        """
        [신규] 지정된 기간 동안의 모든 케어 기록을 날짜별, 타입별로 그룹화하여 조회합니다.
        단 한 번의 DB 쿼리로 7일치(또는 N일치) 데이터를 가져옵니다.
        """
        try:
            #  중요: 이 쿼리를 위해서는 Firestore에서 'pet_care_logs' 컬렉션에 대한
            # (pet_id, searchDate, timestamp) 복합 색인을 생성해야 합니다.
            query = self.logs_ref \
                .where('pet_id', '==', pet_id) \
                .where('searchDate', '>=', start_date) \
                .where('searchDate', '<=', end_date) \
                .order_by('searchDate') \
                .order_by('timestamp')
                
            docs = query.stream()
            
            # 날짜별로 그룹화하기 위한 딕셔너리
            # 예: { "2023-10-26": {"water": [...]}, "2023-10-27": {"meal": [...]} }
            records_by_date = {}

            for doc in docs:
                record = doc.to_dict()
                date_key = record.get('searchDate')
                record_type = record.get('record_type')

                if date_key not in records_by_date:
                    records_by_date[date_key] = {'weight': [], 'water': [], 'activity': [], 'meal': []}
                
                if record_type in records_by_date[date_key]:
                    timestamp_obj = record.get('timestamp')
                    if timestamp_obj:
                        record['timestamp'] = DateTimeUtils.to_timestamp_ms(timestamp_obj)
                    records_by_date[date_key][record_type].append(record)
            
            return records_by_date

        except Exception as e:
            logging.error(f"Date range query failed for pet {pet_id} ({start_date}-{end_date}): {e}", exc_info=True)
            raise