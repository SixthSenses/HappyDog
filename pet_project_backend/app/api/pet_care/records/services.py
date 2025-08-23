# app/api/pet_care/records/services.py
import logging
from typing import Dict, Any, List, Optional, Tuple
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

    def get_records_flexible(self, pet_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        [개선된] 유연한 쿼리 파라미터를 지원하는 통합 조회 메서드.
        서버 사이드 필터링과 커서 기반 페이지네이션을 사용합니다.
        
        Args:
            pet_id: 반려동물 ID
            query_params: 쿼리 파라미터 딕셔너리
                - date: 단일 날짜 (YYYY-MM-DD)
                - start_date, end_date: 날짜 범위
                - record_types: 필터링할 기록 타입 리스트
                - grouped: 타입별 그룹화 여부
                - limit: 조회 개수 제한
                - cursor: 커서 기반 페이지네이션용
                - sort: 정렬 방식
        
        Returns:
            조회 결과 딕셔너리
        """
        try:
            # 기본 쿼리 구성
            query = self.logs_ref.where('pet_id', '==', pet_id)
            
            # 날짜 필터링
            if query_params.get('date'):
                query = query.where('searchDate', '==', query_params['date'])
            elif query_params.get('start_date') and query_params.get('end_date'):
                query = query.where('searchDate', '>=', query_params['start_date']) \
                            .where('searchDate', '<=', query_params['end_date'])
            
            # 서버 사이드 타입 필터링 (Firestore 'in' 연산자 사용)
            record_types = query_params.get('record_types')
            if record_types and len(record_types) <= 10:  # Firestore 'in' 연산자는 최대 10개 값 지원
                query = query.where('record_type', 'in', record_types)
            
            # 정렬
            sort = query_params.get('sort', 'timestamp_desc')
            if sort == 'timestamp_asc':
                query = query.order_by('timestamp')
            else:  # timestamp_desc
                query = query.order_by('timestamp', direction=firestore.Query.DESCENDING)
            
            # 커서 기반 페이지네이션
            cursor = query_params.get('cursor')
            if cursor:
                try:
                    # 커서에서 마지막 문서 정보 추출 (실제 구현에서는 더 안전한 방식 사용)
                    cursor_doc = self.logs_ref.document(cursor).get()
                    if cursor_doc.exists:
                        query = query.start_after(cursor_doc)
                except Exception as e:
                    logging.warning(f"Invalid cursor provided: {cursor}, ignoring cursor")
            
            # 페이지네이션
            limit = query_params.get('limit', 50)
            
            # 쿼리 실행
            docs = query.limit(limit + 1).stream()  # has_more 확인을 위해 +1
            records = []
            last_doc = None
            
            for doc in docs:
                if len(records) >= limit:
                    last_doc = doc
                    break
                    
                record = doc.to_dict()
                # Firestore Timestamp를 Unix timestamp(ms)로 변환
                timestamp_obj = record.get('timestamp')
                if timestamp_obj:
                    record['timestamp'] = DateTimeUtils.to_timestamp_ms(timestamp_obj)
                records.append(record)
            
            # 다음 페이지 커서 생성
            next_cursor = last_doc.id if last_doc else None
            
            # 응답 구성
            response = {
                'records': records,
                'meta': {
                    'total_count': len(records),
                    'limit': limit,
                    'has_more': len(records) == limit and last_doc is not None,
                    'next_cursor': next_cursor
                }
            }
            
            # 타입별 그룹화 (요청된 경우)
            if query_params.get('grouped', False):
                grouped = {'weight': [], 'water': [], 'activity': [], 'meal': []}
                for record in records:
                    record_type = record.get('record_type')
                    if record_type in grouped:
                        grouped[record_type].append(record)
                response['grouped'] = grouped
            
            return response

        except Exception as e:
            logging.error(f"Flexible records query failed for pet {pet_id}: {e}", exc_info=True)
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

    def get_records_by_type(self, pet_id: str, record_type: str, date_str: str = None, 
                           start_date: str = None, end_date: str = None, limit: int = 50,
                           cursor: str = None) -> Dict[str, Any]:
        """
        [개선된] 특정 타입의 기록만 조회하는 메서드.
        커서 기반 페이지네이션을 지원합니다.
        """
        try:
            query = self.logs_ref.where('pet_id', '==', pet_id).where('record_type', '==', record_type)
            
            # 날짜 필터링
            if date_str:
                query = query.where('searchDate', '==', date_str)
            elif start_date and end_date:
                query = query.where('searchDate', '>=', start_date).where('searchDate', '<=', end_date)
            
            # 정렬 및 제한
            query = query.order_by('timestamp', direction=firestore.Query.DESCENDING)
            
            # 커서 기반 페이지네이션
            if cursor:
                try:
                    cursor_doc = self.logs_ref.document(cursor).get()
                    if cursor_doc.exists:
                        query = query.start_after(cursor_doc)
                except Exception as e:
                    logging.warning(f"Invalid cursor provided: {cursor}, ignoring cursor")
            
            # 쿼리 실행
            docs = query.limit(limit + 1).stream()  # has_more 확인을 위해 +1
            records = []
            last_doc = None
            
            for doc in docs:
                if len(records) >= limit:
                    last_doc = doc
                    break
                    
                record = doc.to_dict()
                timestamp_obj = record.get('timestamp')
                if timestamp_obj:
                    record['timestamp'] = DateTimeUtils.to_timestamp_ms(timestamp_obj)
                records.append(record)
            
            # 다음 페이지 커서 생성
            next_cursor = last_doc.id if last_doc else None
            
            return {
                'records': records,
                'meta': {
                    'record_type': record_type,
                    'total_count': len(records),
                    'limit': limit,
                    'has_more': len(records) == limit and last_doc is not None,
                    'next_cursor': next_cursor
                }
            }

        except Exception as e:
            logging.error(f"Failed to get {record_type} records for pet {pet_id}: {e}", exc_info=True)
            raise