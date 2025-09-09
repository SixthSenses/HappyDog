"""Pet Care Record Service V1 (Legacy & Core CRUD)
===================================================
이 모듈은 기존(레거시) v1 동작을 담당하는 서비스 로직을 분리한 것입니다.
주요 책임:
 - 기록 생성/수정/삭제 (멱등성 포함)
 - 유연(flexible) 조회, 타입별 조회
 - 일일(daily) / 범위(range) 그룹화 (v1 형식)
 - V2 전용 응답 구조(평탄화 등)는 포함하지 않음

NOTE:
 - Firestore 접근 패턴 및 검증 로직은 원본 `services.py`에서 그대로 이동.
 - V2 서비스(`services_v2.PetCareRecordServiceV2`)가 동일 Firestore 레퍼런스를 재사용할 수 있도록
   `logs_ref` 공개 속성을 유지.
 - 향후 마이그레이션(스키마 변경 등)은 V2 이후 단계에서만 적용하고, V1은 안정성/하위호환 유지에 집중.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from firebase_admin import firestore
from marshmallow import ValidationError

from app.models.pet_care_log import PetCareLog
from app.utils.datetime_utils import DateTimeUtils


class PetCareRecordServiceV1:
    """레거시(v1) Pet Care Record 서비스.

    V2 기능은 별도 `PetCareRecordServiceV2` 클래스로 분리되어 있으며,
    앱 팩토리에서는 통합 어댑터(`PetCareRecordService`)를 통해 노출됩니다.
    """

    def __init__(self):
        self.db = firestore.client()
        self.logs_ref = self.db.collection('pet_care_logs')
        logging.info("PetCareRecordServiceV1 initialized.")

    # ------------------------------------------------------------------
    # 생성 / 수정 / 삭제
    # ------------------------------------------------------------------
    def create_care_record(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            ts_ms = record_data['timestamp']
            # clock skew 검증 (±300s)
            DateTimeUtils.validate_clock_skew(ts_ms, max_skew_seconds=300)
            record_dt_utc = DateTimeUtils.from_timestamp_ms(ts_ms)
            search_date = record_dt_utc.strftime('%Y-%m-%d')
            request_id = record_data.get('request_id')
            log_id = request_id if request_id else str(uuid.uuid4())
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
            self.logs_ref.document(log_id).set(DateTimeUtils.for_firestore(log_dict), merge=True)
            log_dict['timestamp_ms'] = ts_ms
            return log_dict
        except Exception as e:
            logging.error(f"Failed to create care record for pet {pet_id}: {e}", exc_info=True)
            raise

    def update_care_record(self, pet_id: str, log_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        ref = self.logs_ref.document(log_id)
        snap = ref.get()
        if not snap.exists:
            raise FileNotFoundError("기록 없음")
        data = snap.to_dict()
        if data.get('pet_id') != pet_id:
            raise PermissionError("잘못된 접근")
        previous_search_date = data.get('searchDate')

        ALLOWED_FIELDS = {'data', 'notes', 'timestamp'}
        update_data = {k: v for k, v in (payload or {}).items() if k in ALLOWED_FIELDS}
        if not update_data:
            return data

        record_type = data.get('record_type')
        errors: Dict[str, List[str]] = {}
        if 'data' in update_data:
            val = update_data['data']
            if record_type == 'weight':
                if not isinstance(val, (int, float)) or float(val) <= 0:
                    errors.setdefault('data', []).append('weight는 0보다 큰 실수여야 합니다.')
                else:
                    update_data['data'] = float(val)
            elif record_type in ('water', 'activity', 'meal'):
                if not isinstance(val, int) or val < 0:
                    errors.setdefault('data', []).append(f'{record_type}는 0 이상의 정수여야 합니다.')
            elif record_type == 'bcs':
                if not isinstance(val, int) or val < 1 or val > 5:
                    errors.setdefault('data', []).append('bcs는 1~5 범위의 정수여야 합니다.')
            else:
                errors.setdefault('data', []).append('알 수 없는 record_type에 대한 data입니다.')

        if 'notes' in update_data:
            val = update_data['notes']
            if val is not None and not isinstance(val, str):
                errors.setdefault('notes', []).append('notes는 문자열 또는 null이어야 합니다.')

        if 'timestamp' in update_data:
            val = update_data['timestamp']
            if not isinstance(val, int) or val < 0:
                errors.setdefault('timestamp', []).append('timestamp는 0 이상의 밀리초 정수여야 합니다.')

        if errors:
            raise ValidationError(errors)

        if 'timestamp' in update_data:
            ts_ms = update_data['timestamp']
            try:
                DateTimeUtils.validate_clock_skew(ts_ms, max_skew_seconds=300)
            except Exception as _e:  # 비치명적 로깅
                logging.debug(f"clock skew validation during update non-fatal: {_e}")
            dt = DateTimeUtils.from_timestamp_ms(ts_ms)
            update_data['timestamp'] = dt
            update_data['searchDate'] = dt.strftime('%Y-%m-%d')

        ref.update(update_data)
        updated = ref.get().to_dict()
        ts_obj = updated.get('timestamp')
        if ts_obj:
            updated['timestamp'] = DateTimeUtils.to_timestamp_ms(ts_obj)
        updated['__previous_searchDate'] = previous_search_date
        return updated

    def delete_care_record(self, pet_id: str, log_id: str) -> str:
        ref = self.logs_ref.document(log_id)
        snap = ref.get()
        if not snap.exists:
            raise FileNotFoundError("기록 없음")
        data = snap.to_dict()
        if data.get('pet_id') != pet_id:
            raise PermissionError("잘못된 접근")
        search_date = data.get('searchDate')
        ref.delete()
        return search_date

    # ------------------------------------------------------------------
    # 조회 (Flexible & Legacy Grouping)
    # ------------------------------------------------------------------
    def get_records_flexible(self, pet_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            query = self.logs_ref.where('pet_id', '==', pet_id)
            if query_params.get('date'):
                query = query.where('searchDate', '==', query_params['date'])
            elif query_params.get('start_date') and query_params.get('end_date'):
                query = (query.where('searchDate', '>=', query_params['start_date'])
                               .where('searchDate', '<=', query_params['end_date']))
            record_types = query_params.get('record_types')
            if record_types and len(record_types) <= 10:
                query = query.where('record_type', 'in', record_types)
            sort = query_params.get('sort', 'timestamp_desc')
            if sort == 'timestamp_asc':
                query = query.order_by('timestamp')
            else:
                query = query.order_by('timestamp', direction=firestore.Query.DESCENDING)
            cursor = query_params.get('cursor')
            if cursor:
                try:
                    cursor_doc = self.logs_ref.document(cursor).get()
                    if cursor_doc.exists:
                        query = query.start_after(cursor_doc)
                except Exception:
                    logging.warning(f"Invalid cursor provided: {cursor}, ignoring cursor")
            limit = query_params.get('limit', 50)
            docs = query.limit(limit + 1).stream()
            records = []
            last_doc = None
            for doc in docs:
                if len(records) >= limit:
                    last_doc = doc
                    break
                record = doc.to_dict()
                ts = record.get('timestamp')
                if ts:
                    record['timestamp'] = DateTimeUtils.to_timestamp_ms(ts)
                records.append(record)
            next_cursor = last_doc.id if last_doc else None
            response = {
                'records': records,
                'meta': {
                    'total_count': len(records),
                    'limit': limit,
                    'has_more': len(records) == limit and last_doc is not None,
                    'next_cursor': next_cursor
                }
            }
            if query_params.get('grouped', False):
                grouped = {'weight': [], 'water': [], 'activity': [], 'meal': [], 'bcs': []}
                for r in records:
                    rt = r.get('record_type')
                    if rt in grouped:
                        grouped[rt].append(r)
                response['grouped'] = grouped
            return response
        except Exception as e:
            logging.error(f"Flexible records query failed for pet {pet_id}: {e}", exc_info=True)
            raise

    def get_daily_records(self, pet_id: str, date_str: str) -> Dict[str, List[Dict]]:
        try:
            query = (self.logs_ref.where('pet_id', '==', pet_id)
                                 .where('searchDate', '==', date_str)
                                 .order_by('timestamp'))
            docs = query.stream()
            grouped = {'weight': [], 'water': [], 'activity': [], 'meal': [], 'bcs': []}
            for d in docs:
                rec = d.to_dict()
                rt = rec.get('record_type')
                if rt in grouped:
                    ts = rec.get('timestamp')
                    if ts:
                        rec['timestamp'] = DateTimeUtils.to_timestamp_ms(ts)
                    grouped[rt].append(rec)
            return grouped
        except Exception as e:
            logging.error(f"Failed to get daily records for pet {pet_id} on {date_str}: {e}", exc_info=True)
            raise

    def get_records_for_date_range(self, pet_id: str, start_date: str, end_date: str) -> Dict[str, List[Dict]]:
        try:
            query = (self.logs_ref.where('pet_id', '==', pet_id)
                                 .where('searchDate', '>=', start_date)
                                 .where('searchDate', '<=', end_date)
                                 .order_by('searchDate')
                                 .order_by('timestamp'))
            docs = query.stream()
            by_date = {}
            for d in docs:
                rec = d.to_dict()
                date_key = rec.get('searchDate')
                rt = rec.get('record_type')
                if date_key not in by_date:
                    by_date[date_key] = {'weight': [], 'water': [], 'activity': [], 'meal': [], 'bcs': []}
                if rt in by_date[date_key]:
                    ts = rec.get('timestamp')
                    if ts:
                        rec['timestamp'] = DateTimeUtils.to_timestamp_ms(ts)
                    by_date[date_key][rt].append(rec)
            return by_date
        except Exception as e:
            logging.error(f"Date range query failed for pet {pet_id} ({start_date}-{end_date}): {e}", exc_info=True)
            raise

    def get_records_by_type(self, pet_id: str, record_type: str, date_str: str = None,
                            start_date: str = None, end_date: str = None, limit: int = 50,
                            cursor: str = None) -> Dict[str, Any]:
        try:
            query = (self.logs_ref.where('pet_id', '==', pet_id)
                                 .where('record_type', '==', record_type))
            if date_str:
                query = query.where('searchDate', '==', date_str)
            elif start_date and end_date:
                query = query.where('searchDate', '>=', start_date).where('searchDate', '<=', end_date)
            query = query.order_by('timestamp', direction=firestore.Query.DESCENDING)
            if cursor:
                try:
                    cursor_doc = self.logs_ref.document(cursor).get()
                    if cursor_doc.exists:
                        query = query.start_after(cursor_doc)
                except Exception:
                    logging.warning(f"Invalid cursor provided: {cursor}, ignoring cursor")
            docs = query.limit(limit + 1).stream()
            records = []
            last_doc = None
            for doc in docs:
                if len(records) >= limit:
                    last_doc = doc
                    break
                rec = doc.to_dict()
                ts = rec.get('timestamp')
                if ts:
                    rec['timestamp'] = DateTimeUtils.to_timestamp_ms(ts)
                records.append(rec)
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


__all__ = ["PetCareRecordServiceV1"]
