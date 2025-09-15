# app/api/pet_care/records/services.py
import logging
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import asdict
from firebase_admin import firestore

from app.models.pet_care_log import PetCareLog
from app.utils.datetime_utils import DateTimeUtils

class PetCareRecordService:
    """Service handling pet care records (CRUD + daily summary). Skips Firestore in DOCS_MODE."""

    def __init__(self, db_client=None):
        self.db: Optional[firestore.Client] = db_client
        self.logs_ref = self.db.collection('pet_care_logs') if self.db else None
        if self.db is None:
            logging.info("PetCareRecordService initialized without Firestore client (docs mode or disabled persistence)")
        else:
            logging.info("PetCareRecordService initialized with Firestore client.")

    def create_record(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single pet care record. In DOCS_MODE returns echo payload with generated IDs."""
        try:
            if self.logs_ref is None:
                log_id = str(uuid.uuid4())
                timestamp_ms = record_data['timestamp']
                return {
                    'log_id': log_id,
                    'pet_id': pet_id,
                    'record_type': record_data['record_type'],
                    'timestamp_ms': timestamp_ms,
                    'timestamp': timestamp_ms,
                    'data': record_data['data'],
                    'memo': record_data.get('memo', ''),
                    'searchDate': '1970-01-01'
                }
            # 로그 ID 생성
            log_id = str(uuid.uuid4())
            
            # 타임스탬프에서 검색 날짜 계산
            timestamp_ms = record_data['timestamp']
            timestamp_dt = DateTimeUtils.from_timestamp_ms(timestamp_ms)
            search_date = DateTimeUtils.to_date_str(timestamp_dt)
            
            # 기록 객체 생성
            record = PetCareLog(
                log_id=log_id,
                pet_id=pet_id,
                record_type=record_data['record_type'],
                timestamp=timestamp_dt,
                searchDate=search_date,
                data=record_data['data'],
                memo=record_data.get('memo', ''),
                user_id=record_data.get('user_id', 'system')
            )
            
            # Firestore에 저장
            doc_data = asdict(record)
            doc_data['timestamp'] = DateTimeUtils.for_firestore(record.timestamp)
            doc_data['searchDate'] = record.searchDate
            
            self.logs_ref.document(log_id).set(doc_data)
            
            # 응답 데이터 구성
            result = asdict(record)
            # timestamp / timestamp_ms 는 둘 다 ms 정수값으로 응답 (스키마 예시 준수)
            result['timestamp_ms'] = timestamp_ms
            result['timestamp'] = timestamp_ms  # Marshmallow Int 필드 직렬화 오류 방지 (datetime → int)
            
            logging.info(f"펫케어 기록 생성됨: pet_id={pet_id}, type={record_data['record_type']}")
            return result
            
        except Exception as e:
            logging.error(f"펫케어 기록 생성 실패: {e}", exc_info=True)
            raise

    def update_record(self, pet_id: str, log_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing record. In DOCS_MODE returns placeholder synthetic data."""
        try:
            if self.logs_ref is None:
                synthetic = {
                    'log_id': log_id,
                    'pet_id': pet_id,
                    'record_type': 'synthetic',
                    'timestamp_ms': 0,
                    'timestamp': 0,
                    'data': update_data.get('data', {}),
                    'memo': update_data.get('memo', '')
                }
                return synthetic
            doc_ref = self.logs_ref.document(log_id)
            doc_snap = doc_ref.get()
            
            if not doc_snap.exists:
                raise FileNotFoundError(f"기록을 찾을 수 없습니다: {log_id}")
                
            current_data = doc_snap.to_dict()
            if current_data.get('pet_id') != pet_id:
                raise PermissionError(f"기록에 대한 권한이 없습니다: {log_id}")
            
            # 업데이트 필드 구성
            update_fields = {}
            if 'data' in update_data:
                update_fields['data'] = update_data['data']
            if 'memo' in update_data:
                update_fields['memo'] = update_data['memo']
            
            update_fields['updated_at'] = DateTimeUtils.for_firestore(DateTimeUtils.now_utc())
            
            # 업데이트 실행
            doc_ref.update(update_fields)
            
            # 업데이트된 데이터 조회
            updated_snap = doc_ref.get()
            result = updated_snap.to_dict()
            result['log_id'] = log_id
            
            # 타임스탬프 변환
            if 'timestamp' in result:
                timestamp_val = result['timestamp']
                if hasattr(timestamp_val, 'timestamp'):
                    ts_ms = int(timestamp_val.timestamp() * 1000)
                    result['timestamp_ms'] = ts_ms
                    result['timestamp'] = ts_ms  # 응답 일관성 (Int)
            
            logging.info(f"펫케어 기록 수정됨: pet_id={pet_id}, log_id={log_id}")
            return result
            
        except Exception as e:
            logging.error(f"펫케어 기록 수정 실패: {e}", exc_info=True)
            raise

    def delete_record(self, pet_id: str, log_id: str) -> None:
        """Delete a pet care record. No-op in DOCS_MODE."""
        try:
            if self.logs_ref is None:
                logging.info("PetCareRecordService: DOCS_MODE - delete skipped")
                return
            doc_ref = self.logs_ref.document(log_id)
            doc_snap = doc_ref.get()
            
            if not doc_snap.exists:
                raise FileNotFoundError(f"기록을 찾을 수 없습니다: {log_id}")
                
            current_data = doc_snap.to_dict()
            if current_data.get('pet_id') != pet_id:
                raise PermissionError(f"기록에 대한 권한이 없습니다: {log_id}")
            
            # 삭제 실행
            doc_ref.delete()
            
            logging.info(f"펫케어 기록 삭제됨: pet_id={pet_id}, log_id={log_id}")
            
        except Exception as e:
            logging.error(f"펫케어 기록 삭제 실패: {e}", exc_info=True)
            raise

    def get_daily_records(self, pet_id: str, date: str) -> Dict[str, Any]:
        """Fetch all records for a date. In DOCS_MODE returns empty list & null summary fields."""
        try:
            if self.logs_ref is None:
                summary = {k: None for k in ['meal_count', 'activity_minutes', 'weight', 'bcs', 'stool', 'vomit']}
                return {'date': date, 'records': [], 'summary': summary}
            # 날짜별 기록 조회
            query = (self.logs_ref
                    .where('pet_id', '==', pet_id)
                    .where('searchDate', '==', date)
                    .order_by('timestamp'))
            
            docs = list(query.stream())
            
            records = []
            summary = {}
            
            for doc in docs:
                doc_data = doc.to_dict()
                doc_data['log_id'] = doc.id
                
                # 타임스탬프 변환
                if 'timestamp' in doc_data:
                    timestamp_val = doc_data['timestamp']
                    if hasattr(timestamp_val, 'timestamp'):
                        ts_ms = int(timestamp_val.timestamp() * 1000)
                        doc_data['timestamp_ms'] = ts_ms
                        doc_data['timestamp'] = ts_ms  # 직렬화 호환
                
                records.append(doc_data)
                
                # 요약 데이터 구성
                record_type = doc_data.get('record_type')
                data_value = doc_data.get('data')
                
                if record_type == 'meal_count':
                    summary['meal_count'] = data_value
                elif record_type == 'activity':
                    summary['activity_minutes'] = data_value
                elif record_type == 'weight':
                    summary['weight'] = data_value
                elif record_type == 'bcs':
                    summary['bcs'] = data_value
                elif record_type == 'stool':
                    summary['stool'] = data_value
                elif record_type == 'vomit':
                    summary['vomit'] = data_value
            
            # 기본값 설정
            for field in ['meal_count', 'activity_minutes', 'weight', 'bcs', 'stool', 'vomit']:
                if field not in summary:
                    summary[field] = None
            
            result = {
                'date': date,
                'records': records,
                'summary': summary
            }
            
            logging.info(f"일별 펫케어 기록 조회됨: pet_id={pet_id}, date={date}, count={len(records)}")
            return result
            
        except Exception as e:
            logging.error(f"일별 펫케어 기록 조회 실패: {e}", exc_info=True)
            raise
