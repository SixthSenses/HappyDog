"""Pet Care Record Service V2 (New Spec Endpoints)
=================================================
신규 스펙(Sprint A 이후) 기반의 V2 전용 조회/요약 인터페이스.

포함 기능:
 - /daily (평탄화 구조 + meta.limit/has_more/next_cursor 규칙)
 - /range (meta.limit 포함, 날짜별 그룹화)
 - /summary (임시: 기간 요약, 향후 단일 date 요약으로 재정렬 예정)

설계 원칙:
 - Firestore 접근은 V1 서비스가 가진 logs_ref 재사용 (트랜잭션/보안 규칙 일관성)
 - V1 CRUD 로직을 수정하지 않고 읽기 패턴만 확장
 - 향후 스키마 마이그레이션(weight 등 data 객체화) 시 듀얼 리드 로직을 이 레이어에 추가
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.utils.datetime_utils import DateTimeUtils
from firebase_admin import firestore


class PetCareRecordServiceV2:
    def __init__(self, v1_service):
        self.v1 = v1_service
        self.logs_ref = v1_service.logs_ref  # 공유
        logging.info("PetCareRecordServiceV2 initialized (reusing V1 Firestore reference).")
    # TODO(feedback 2025-09-09):
    #  - Add pagination regression tests: cross-page ordering, last page next_cursor None, has_more ↔ next_cursor equivalence.
    #  - Implement include_total logic (threshold 5000) once route layer exposes with_total param.
    #  - Prepare dual-read adapter Phase0 for scalar→object migration (weight etc.).
    #  - Emit metrics (etag_hit/miss, dual_read_adapter_fallback, rate_limit shadow, idempotent_conflict).

    # -------------------- V2 Endpoints --------------------
    def get_daily_v2(self, pet_id: str, date: str, record_types: Optional[List[str]] = None,
                     limit: int = 100, cursor: Optional[str] = None) -> Dict[str, Any]:
        try:
            q = (self.logs_ref
                 .where('pet_id','==', pet_id)
                 .where('searchDate','==', date)
                 .order_by('timestamp'))
            if cursor:
                try:
                    last_snap = self.logs_ref.document(cursor).get()
                    if last_snap.exists:
                        q = q.start_after(last_snap)
                except Exception:
                    pass
            docs_iter = q.limit(limit + 1).stream()
            groups = { 'weight': [], 'water': [], 'activity': [], 'meal': [], 'bcs': [] }
            fetched = []
            for d in docs_iter:
                fetched.append(d)
            has_more = len(fetched) > limit
            if has_more:
                fetched.pop()
            next_cursor = fetched[-1].id if has_more and fetched else None
            for d in fetched:
                item = d.to_dict()
                rt = item.get('record_type')
                if record_types and rt not in record_types:
                    continue
                ts = item.get('timestamp')
                if ts:
                    item['timestamp'] = DateTimeUtils.to_timestamp_ms(ts)
                if rt in groups:
                    groups[rt].append(item)
            if record_types:
                filtered = {k: groups[k] for k in groups.keys() if k in record_types}
            else:
                filtered = groups
            # 신규 스펙 정합: pet_id 포함
            flat = {'pet_id': pet_id, 'date': date}
            for k in ['weight','water','activity','meal','bcs']:
                flat[k] = filtered.get(k, [])
            return {
                'data': flat,
                'meta': {
                    'limit': limit,
                    'has_more': has_more,
                    'next_cursor': next_cursor
                }
            }
        except Exception as e:
            logging.error(f"daily v2 query failed pet={pet_id} date={date}: {e}", exc_info=True)
            raise

    def get_range_v2(self, pet_id: str, start_date: str, end_date: str,
                      record_types: Optional[List[str]] = None, limit: int = 300,
                      cursor: Optional[str] = None) -> Dict[str, Any]:
        try:
            q = (self.logs_ref
                 .where('pet_id','==', pet_id)
                 .where('searchDate','>=', start_date)
                 .where('searchDate','<=', end_date)
                 .order_by('searchDate')
                 .order_by('timestamp'))
            if cursor:
                try:
                    last_snap = self.logs_ref.document(cursor).get()
                    if last_snap.exists:
                        q = q.start_after(last_snap)
                except Exception:
                    pass
            docs_iter = q.limit(limit + 1).stream()
            fetched = [d for d in docs_iter]
            has_more = len(fetched) > limit
            if has_more:
                fetched.pop()
            next_cursor = fetched[-1].id if has_more and fetched else None
            by_date: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
            for d in fetched:
                item = d.to_dict()
                rt = item.get('record_type')
                if record_types and rt not in record_types:
                    continue
                date_key = item.get('searchDate')
                if date_key not in by_date:
                    by_date[date_key] = { 'weight': [], 'water': [], 'activity': [], 'meal': [], 'bcs': [] }
                ts = item.get('timestamp')
                if ts:
                    item['timestamp'] = DateTimeUtils.to_timestamp_ms(ts)
                if rt in by_date[date_key]:
                    by_date[date_key][rt].append(item)
            if record_types:
                for k in list(by_date.keys()):
                    by_date[k] = {t: by_date[k][t] for t in by_date[k].keys() if t in record_types}
            return {
                'data': {
                    'pet_id': pet_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'records': by_date
                },
                'meta': {
                    'limit': limit,
                    'has_more': has_more,
                    'next_cursor': next_cursor
                }
            }
        except Exception as e:
            logging.error(f"range v2 query failed pet={pet_id} {start_date}-{end_date}: {e}", exc_info=True)
            raise

    # -------------------- Summary Helpers (Sprint B) --------------------
    def _fetch_goals(self, pet_id: str) -> Dict[str, Any]:
        try:
            ref = self.v1.db.collection('pet_settings').document(pet_id)
            snap = ref.get()
            if not snap.exists:
                return {}
            data = snap.to_dict() or {}
            return {
                'water_ml': data.get('goal_water_ml'),
                'meal_count': data.get('goal_meal_count'),
                'activity_minutes': data.get('goal_activity_minutes'),
                'weight_goal': data.get('goal_weight'),
            }
        except Exception:
            return {}

    def _progress_pct(self, num: float, denom: float) -> float:
        if denom is None or denom == 0:
            return 0.0
        v = (num / denom) * 100.0
        if v > 100.0:
            v = 100.0
        return round(v, 1)

    def get_summary_single_day(self, pet_id: str, date: str) -> Dict[str, Any]:
        """
        Sprint C 개선: weight_latest 형식 정규화
        """
        daily = self.get_daily_v2(pet_id, date, record_types=None, limit=500)
        buckets = daily['data']
        
        # Aggregate values
        water_total = sum([i.get('data',0) for i in buckets.get('water', []) if isinstance(i.get('data'), (int,float))])
        activity_total = sum([i.get('data',0) for i in buckets.get('activity', []) if isinstance(i.get('data'), (int,float))])
        meal_count = len(buckets.get('meal', []))
        
        # Weight latest with timestamp
        weight_latest = None
        if buckets.get('weight'):
            latest_record = sorted(buckets['weight'], key=lambda x: x['timestamp'])[-1]
            latest_ts_ms = latest_record.get('timestamp')
            weight_latest = {
                'value': latest_record.get('data'),
                'timestamp_ms': latest_ts_ms
            }
        
        # BCS latest with timestamp  
        bcs_latest = None
        if buckets.get('bcs'):
            latest_record = sorted(buckets['bcs'], key=lambda x: x['timestamp'])[-1]
            latest_ts_ms = latest_record.get('timestamp')
            bcs_latest = {
                'value': latest_record.get('data'),
                'timestamp_ms': latest_ts_ms
            }
        
        # Goals
        goals = self._fetch_goals(pet_id)
        
        # Progress calculation
        progress = {
            'water_ml': self._progress_pct(water_total, goals.get('water_ml')),
            'meal_count': self._progress_pct(meal_count, goals.get('meal_count')),
            'activity_minutes': self._progress_pct(activity_total, goals.get('activity_minutes')),
        }
        
        # Weight delta percentage (null if no goal or no weight)
        if weight_latest and goals.get('weight_goal'):
            goal_weight = goals.get('weight_goal')
            if goal_weight and goal_weight != 0:
                current_weight = weight_latest['value']
                progress['weight_delta_pct'] = round(((current_weight / goal_weight) - 1) * 100.0, 1)
            else:
                progress['weight_delta_pct'] = None
        else:
            progress['weight_delta_pct'] = None
        
        summary = {
            'pet_id': pet_id,
            'date': date,
            'weight_latest': weight_latest,
            'water_intake_total': water_total,
            'meal_count': meal_count,
            'activity_minutes': activity_total,
            'bcs_latest': bcs_latest,
            'goals': goals,
            'progress_percent': progress
        }
        
        return {'data': summary, 'meta': {}}

    def get_summary_v2(self, pet_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
        # Single date fallback (Sprint B behavior)
        if start_date == end_date:
            return self.get_summary_single_day(pet_id, start_date)
        try:
            raw = self.get_range_v2(pet_id, start_date, end_date)
            records_by_date = raw['data']['records']
            summary: Dict[str, Any] = {
                'pet_id': pet_id,
                'interval': {'start_date': start_date, 'end_date': end_date},
                'metrics': {}
            }
            type_keys = ['weight','water','activity','meal','bcs']
            for t in type_keys:
                collected = []
                for _, bucket in records_by_date.items():
                    collected.extend(bucket.get(t, []))
                if not collected:
                    continue
                if t in ('weight','bcs'):
                    latest = sorted(collected, key=lambda x: x['timestamp'])[-1]
                    summary['metrics'][t] = {'latest': latest['data'], 'count': len(collected)}
                else:
                    total = sum([c.get('data',0) for c in collected if isinstance(c.get('data'), (int,float))])
                    summary['metrics'][t] = {'total': total, 'count': len(collected)}
            return {
                'data': summary,
                'meta': {
                    'has_more': False,
                    'next_cursor': None
                }
            }
        except Exception as e:
            logging.error(f"summary v2 query failed pet={pet_id} {start_date}-{end_date}: {e}", exc_info=True)
            raise


__all__ = ["PetCareRecordServiceV2"]
