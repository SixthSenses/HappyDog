from __future__ import annotations
import logging
import uuid
from typing import Any, Dict, List, Optional, Protocol
from firebase_admin import firestore

from app.models.pet_care_log import PetCareLog
from app.utils.datetime_utils import DateTimeUtils


class PetCareRecordRepository(Protocol):
    def insert(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def update(self, pet_id: str, log_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def delete(self, pet_id: str, log_id: str) -> None:
        ...

    def list_by_date(self, pet_id: str, date: str) -> List[Dict[str, Any]]:
        ...

    def list_by_range(self, pet_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        ...


class FirestorePetCareRecordRepository:
    """Firestore-backed repository for pet care logs."""

    def __init__(self, db_client: Optional[firestore.Client]):
        self.db: Optional[firestore.Client] = db_client
        self.logs_ref = self.db.collection('pet_care_logs') if self.db else None
        if self.db is None:
            logging.info("FirestorePetCareRecordRepository initialized without Firestore (docs mode)")
        else:
            logging.info("FirestorePetCareRecordRepository initialized with Firestore client")

    def insert(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.logs_ref is None:
            # docs mode echo
            log_id = str(uuid.uuid4())
            ts_ms = record_data['timestamp']
            return {
                'log_id': log_id,
                'pet_id': pet_id,
                'record_type': record_data['record_type'],
                'timestamp_ms': ts_ms,
                'timestamp': ts_ms,
                'data': record_data['data'],
                'memo': record_data.get('memo', ''),
                'searchDate': '1970-01-01',
            }

        log_id = str(uuid.uuid4())
        ts_ms = record_data['timestamp']
        ts_dt = DateTimeUtils.from_timestamp_ms(ts_ms)
        search_date = DateTimeUtils.to_date_str(ts_dt)

        record = PetCareLog(
            log_id=log_id,
            pet_id=pet_id,
            record_type=record_data['record_type'],
            timestamp=ts_dt,
            searchDate=search_date,
            data=record_data['data'],
            memo=record_data.get('memo', ''),
            user_id=record_data.get('user_id', 'system'),
        )
        doc = {
            **record.__dict__,
            'timestamp': DateTimeUtils.for_firestore(ts_dt),
            'searchDate': search_date,
        }
        self.logs_ref.document(log_id).set(doc)
        # return client-friendly ints for timestamp
        result = {**record.__dict__, 'timestamp_ms': ts_ms, 'timestamp': ts_ms}
        return result

    def update(self, pet_id: str, log_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.logs_ref is None:
            return {
                'log_id': log_id,
                'pet_id': pet_id,
                'record_type': 'synthetic',
                'timestamp_ms': 0,
                'timestamp': 0,
                'data': update_data.get('data', {}),
                'memo': update_data.get('memo', ''),
            }
        doc_ref = self.logs_ref.document(log_id)
        snap = doc_ref.get()
        if not snap.exists:
            raise FileNotFoundError(f"기록을 찾을 수 없습니다: {log_id}")
        cur = snap.to_dict()
        if cur.get('pet_id') != pet_id:
            raise PermissionError(f"기록에 대한 권한이 없습니다: {log_id}")
        update_fields: Dict[str, Any] = {}
        if 'data' in update_data:
            update_fields['data'] = update_data['data']
        if 'memo' in update_data:
            update_fields['memo'] = update_data['memo']
        update_fields['updated_at'] = DateTimeUtils.for_firestore(DateTimeUtils.now_utc())
        doc_ref.update(update_fields)
        updated = doc_ref.get().to_dict()
        updated['log_id'] = log_id
        # normalize timestamp
        if 'timestamp' in updated:
            tv = updated['timestamp']
            if hasattr(tv, 'timestamp'):
                ts_ms = int(tv.timestamp() * 1000)
                updated['timestamp_ms'] = ts_ms
                updated['timestamp'] = ts_ms
        return updated

    def delete(self, pet_id: str, log_id: str) -> None:
        if self.logs_ref is None:
            logging.info("PetCareRecordRepository: DOCS_MODE - delete skipped")
            return
        doc_ref = self.logs_ref.document(log_id)
        snap = doc_ref.get()
        if not snap.exists:
            raise FileNotFoundError(f"기록을 찾을 수 없습니다: {log_id}")
        cur = snap.to_dict()
        if cur.get('pet_id') != pet_id:
            raise PermissionError(f"기록에 대한 권한이 없습니다: {log_id}")
        doc_ref.delete()

    def list_by_date(self, pet_id: str, date: str) -> List[Dict[str, Any]]:
        if self.logs_ref is None:
            return []
        query = (
            self.logs_ref
            .where('pet_id', '==', pet_id)
            .where('searchDate', '==', date)
            .order_by('timestamp')
        )
        docs = list(query.stream())
        results: List[Dict[str, Any]] = []
        for d in docs:
            obj = d.to_dict()
            obj['log_id'] = d.id
            tv = obj.get('timestamp')
            if hasattr(tv, 'timestamp'):
                ts_ms = int(tv.timestamp() * 1000)
                obj['timestamp_ms'] = ts_ms
                obj['timestamp'] = ts_ms
            results.append(obj)
        return results

    def list_by_range(self, pet_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        if self.logs_ref is None:
            return []
        query = (
            self.logs_ref
            .where('pet_id', '==', pet_id)
            .where('searchDate', '>=', start_date)
            .where('searchDate', '<=', end_date)
            .order_by('searchDate')
            .order_by('timestamp')
        )
        docs = list(query.stream())
        results: List[Dict[str, Any]] = []
        for d in docs:
            obj = d.to_dict()
            obj['log_id'] = d.id
            tv = obj.get('timestamp')
            if hasattr(tv, 'timestamp'):
                ts_ms = int(tv.timestamp() * 1000)
                obj['timestamp_ms'] = ts_ms
                obj['timestamp'] = ts_ms
            results.append(obj)
        return results


class InMemoryPetCareRecordRepository:
    """Simple no-op/in-memory repository for docs mode/tests."""
    def __init__(self):
        self._rows: Dict[str, Dict[str, Any]] = {}

    def insert(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        log_id = str(uuid.uuid4())
        ts_ms = record_data['timestamp']
        row = {
            'log_id': log_id,
            'pet_id': pet_id,
            'record_type': record_data['record_type'],
            'timestamp_ms': ts_ms,
            'timestamp': ts_ms,
            'data': record_data['data'],
            'memo': record_data.get('memo', ''),
            'searchDate': '1970-01-01',
        }
        self._rows[log_id] = row
        return row

    def update(self, pet_id: str, log_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        row = self._rows.get(log_id)
        if not row:
            raise FileNotFoundError(log_id)
        if row['pet_id'] != pet_id:
            raise PermissionError(log_id)
        row.update({k: v for k, v in update_data.items() if k in {'data', 'memo'}})
        return row

    def delete(self, pet_id: str, log_id: str) -> None:
        row = self._rows.get(log_id)
        if not row:
            raise FileNotFoundError(log_id)
        if row['pet_id'] != pet_id:
            raise PermissionError(log_id)
        del self._rows[log_id]

    def list_by_date(self, pet_id: str, date: str) -> List[Dict[str, Any]]:
        return [r for r in self._rows.values() if r['pet_id'] == pet_id and r.get('searchDate') == date]

    def list_by_range(self, pet_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        return [r for r in self._rows.values() if r['pet_id'] == pet_id]
