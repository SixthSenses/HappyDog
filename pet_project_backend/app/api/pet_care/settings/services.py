# app/api/pet_care/settings/services.py
import logging
import uuid
from typing import Any, Dict, Optional

from firebase_admin import firestore
from firebase_admin.firestore import Transaction

from app.api.breeds.services import BreedService
from app.utils.datetime_utils import DateTimeUtils  # 핵심 유틸리티 임포트

class PetCareSettingService:
    """Service managing pet care goal settings. In DOCS_MODE Firestore is skipped."""
    def __init__(self, breed_service: BreedService, db_client=None):
        self.breed_service = breed_service
        self.db: Optional[firestore.Client] = db_client
        self.settings_ref = self.db.collection('pet_settings') if self.db else None
        self.settings_history_ref = self.db.collection('pet_settings_history') if self.db else None
        if self.db is None:
            logging.info("PetCareSettingService initialized without Firestore client (docs mode or disabled persistence)")
        else:
            logging.info("PetCareSettingService initialized with Firestore client.")

    def create_initial_settings_transactional(self, transaction: Transaction, pet_id: str, gender: str, breed: str, current_weight: float):
        """
        [트랜잭션용] 최초 반려동물 등록 시 초기 설정값을 생성합니다.
        PetService의 트랜잭션 내에서 호출되어 데이터 정합성을 보장합니다.
        """
        try:
            if self.settings_ref is None:
                logging.info("PetCareSettingService: DOCS_MODE - skip transactional create")
                return
            # 1. 품종별 이상 체중 조회
            ideal_weight = self.breed_service.get_breed_ideal_weight(breed, gender)
            goal_weight = ideal_weight if ideal_weight is not None else current_weight

            settings_data = {
                "pet_id": pet_id,
                "goalWeight": goal_weight,
                # 활동 목표(파생): 1회 30분 × 4회 = 120분
                "goalActivityMinutes": 120,  # 저장은 하되 update 시 직접 갱신 금지 (Method A)
                "goalActivitySessions": 4,
                "activitySessionMinutes": 30,
                "activityIncrementMinutes": 10,
                "goalMealCount": 3,
                "mealIncrementCount": 1,
                "created_at": DateTimeUtils.now(), # 표준 유틸리티 사용
                "updated_at": DateTimeUtils.now()  # 표준 유틸리티 사용
            }
            
            # 3. Firestore 저장을 위해 표준 유틸리티로 데이터 변환
            firestore_data = DateTimeUtils.for_firestore(settings_data)
            
            # 4. 트랜잭션을 통해 문서 생성
            settings_doc_ref = self.settings_ref.document(pet_id)
            transaction.set(settings_doc_ref, firestore_data)
            if self.settings_history_ref is not None:
                effective_date = DateTimeUtils.to_kst_date_str(settings_data["created_at"])
                self._save_settings_history(
                    pet_id,
                    settings_data,
                    effective_date=effective_date,
                    transaction=transaction,
                )
            logging.info(f"Transaction: Pet care settings document created for {pet_id}")

        except Exception as e:
            logging.error(f"Failed to create initial settings within transaction for pet {pet_id}: {e}", exc_info=True)
            # 트랜잭션이 실패하면 자동으로 롤백됩니다.
            raise

    def get_settings(self, pet_id: str) -> Dict[str, Any]:
        """Retrieve pet care settings. Returns placeholder in DOCS_MODE."""
        if self.settings_ref is None:
            return {
                "pet_id": pet_id,
                "goalWeight": None,
                # 기본값: 1회 30분 × 4회
                "goalActivityMinutes": 120,
                "goalActivitySessions": 4,
                "activitySessionMinutes": 30,
                "activityIncrementMinutes": 10,
                "goalMealCount": 3,
                "mealIncrementCount": 1,
            }
        doc = self.settings_ref.document(pet_id).get()
        if not doc.exists:
            raise FileNotFoundError("해당 반려동물의 펫케어 설정을 찾을 수 없습니다.")
        data = doc.to_dict()
        # 과거 문서에 새 키가 없을 수 있으므로 합리적 기본값으로 보강
        data.setdefault("goalActivitySessions", 0)
        data.setdefault("activitySessionMinutes", 0)
        # 파생 목표 분 재계산 (Method A): 세션과 1회 분이 유효하면 goalActivityMinutes 재정의 (메모리 상)
        sessions = data.get("goalActivitySessions") or 0
        per_session = data.get("activitySessionMinutes") or 0
        if sessions > 0 and per_session > 0:
            data["goalActivityMinutes"] = sessions * per_session
        return data

    def update_settings(self, pet_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Partially update pet care settings. No-op in DOCS_MODE."""
        if self.settings_ref is None:
            logging.info("PetCareSettingService: DOCS_MODE - update skipped")
            return self.get_settings(pet_id)
        doc_ref = self.settings_ref.document(pet_id)
        incoming_update = dict(update_data)
        transaction = self.db.transaction()

        @firestore.transactional
        def _update(transaction: Transaction):
            snapshot = doc_ref.get(transaction=transaction)
            if not snapshot.exists:
                raise FileNotFoundError("해당 반려동물의 펫케어 설정을 찾을 수 없습니다.")

            # Firestore Timestamp → datetime 변환 후 병합
            current_settings = DateTimeUtils.from_firestore(snapshot.to_dict())

            local_update = dict(incoming_update)
            effective_date_override = local_update.pop('effective_date', None)
            payload = {k: v for k, v in local_update.items() if k != 'goalActivityMinutes'}
            payload['updated_at'] = DateTimeUtils.now()

            firestore_payload = DateTimeUtils.for_firestore(payload)
            transaction.update(doc_ref, firestore_payload)

            merged_settings = {**current_settings, **payload}
            sessions = merged_settings.get("goalActivitySessions") or 0
            per_session = merged_settings.get("activitySessionMinutes") or 0
            if sessions > 0 and per_session > 0:
                merged_settings["goalActivityMinutes"] = sessions * per_session

            if self.settings_history_ref is not None:
                effective_date = effective_date_override or DateTimeUtils.today_kst_as_date_str()
                self._save_settings_history(
                    pet_id,
                    merged_settings,
                    effective_date=effective_date,
                    transaction=transaction,
                )

            return merged_settings

        updated_settings = _update(transaction)
        logging.info(f"Pet care settings updated for {pet_id} (history recorded)")
        return updated_settings

    def get_settings_at_date(self, pet_id: str, date: str) -> Dict[str, Any]:
        """Return settings that were effective on the given KST date.
        
        If multiple settings were changed on the same date, returns the most recent one
        based on created_at timestamp. Requires composite index on (effective_date, created_at).
        """
        if self.settings_history_ref is None:
            return self.get_settings(pet_id)

        history_ref = self.settings_history_ref.document(pet_id).collection('changes')
        try:
            # Try composite index query (effective_date DESC, created_at DESC)
            # This ensures we get the most recent change on the same day
            query = (
                history_ref
                .where('effective_date', '<=', date)
                .order_by('effective_date', direction=firestore.Query.DESCENDING)
                .order_by('created_at', direction=firestore.Query.DESCENDING)
                .limit(1)
            )
            docs = list(query.stream())
        except Exception as exc:
            # Fallback: composite index may not exist yet
            logging.warning(
                f"Composite index query failed for pet {pet_id}, falling back to simple query. "
                f"Consider creating index on (effective_date, created_at). Error: {exc}"
            )
            try:
                # Fallback to simple query without created_at ordering
                query = (
                    history_ref
                    .where('effective_date', '<=', date)
                    .order_by('effective_date', direction=firestore.Query.DESCENDING)
                    .limit(1)
                )
                docs = list(query.stream())
            except Exception as fallback_exc:
                logging.error(f"Failed to fetch settings history for pet {pet_id} at {date}: {fallback_exc}", exc_info=True)
                return self.get_settings(pet_id)

        if not docs:
            logging.warning(f"No settings history before {date} for pet {pet_id}, using current settings")
            return self.get_settings(pet_id)

        history_data = DateTimeUtils.from_firestore(docs[0].to_dict())
        self._ensure_derived_fields(history_data)
        return history_data

    def get_settings_for_range(self, pet_id: str, start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """Return a mapping of effective dates to settings snapshots for the range.
        
        If multiple settings were changed on the same date, only the most recent one
        (based on created_at) is included in the result.
        """
        if self.settings_history_ref is None:
            current = self.get_settings(pet_id)
            return {start_date: current}

        history_ref = self.settings_history_ref.document(pet_id).collection('changes')

        try:
            # Try composite index query for optimal performance
            docs = list(
                history_ref
                .where('effective_date', '<=', end_date)
                .order_by('effective_date', direction=firestore.Query.ASCENDING)
                .order_by('created_at', direction=firestore.Query.DESCENDING)
                .stream()
            )
        except Exception as exc:
            # Fallback: composite index may not exist yet
            logging.warning(
                f"Composite index query failed for range query on pet {pet_id}, using fallback. "
                f"Consider creating index on (effective_date, created_at). Error: {exc}"
            )
            try:
                docs = list(
                    history_ref
                    .where('effective_date', '<=', end_date)
                    .order_by('effective_date')
                    .stream()
                )
            except Exception as fallback_exc:
                logging.error(f"Failed to fetch settings history range for pet {pet_id}: {fallback_exc}", exc_info=True)
                current = self.get_settings(pet_id)
                return {start_date: current}

        if not docs:
            logging.warning(f"No settings history found for pet {pet_id} up to {end_date}, using current settings")
            current = self.get_settings(pet_id)
            return {start_date: current}

        result: Dict[str, Dict[str, Any]] = {}
        base_snapshot: Optional[Dict[str, Any]] = None

        for doc in docs:
            history = DateTimeUtils.from_firestore(doc.to_dict())
            effective_date = history.get('effective_date')
            if not effective_date:
                continue
            
            self._ensure_derived_fields(history)
            history_copy = {**history}
            
            if effective_date <= start_date:
                base_snapshot = history_copy
            
            # Handle same-day multiple changes: keep only the most recent one
            if effective_date in result:
                # Compare created_at to determine which is more recent
                existing_created_at = result[effective_date].get('created_at')
                current_created_at = history_copy.get('created_at')
                
                # Replace if current is more recent (or if existing has no timestamp)
                if not existing_created_at or (current_created_at and current_created_at > existing_created_at):
                    result[effective_date] = history_copy
                # else: keep existing (it's already more recent)
            else:
                # First occurrence of this date
                result[effective_date] = history_copy

        if base_snapshot is None:
            base_snapshot = self.get_settings(pet_id)
            self._ensure_derived_fields(base_snapshot)

        # 시작일 기준 스냅샷은 반드시 포함
        result[start_date] = {**base_snapshot}

        # 시작일 이후 변경은 유지되도록 재정렬
        ordered_result: Dict[str, Dict[str, Any]] = {}
        for key in sorted(result.keys()):
            if key < start_date:
                continue
            ordered_result[key] = result[key]

        return ordered_result

    def _save_settings_history(
        self,
        pet_id: str,
        settings_data: Dict[str, Any],
        *,
        effective_date: Optional[str] = None,
        transaction: Optional[Transaction] = None,
    ) -> None:
        """Persist a snapshot of settings changes for historical goal tracking."""
        if self.settings_history_ref is None:
            logging.debug("Settings history skipped (no Firestore client)")
            return

        if effective_date is None:
            effective_date = DateTimeUtils.today_kst_as_date_str()

        history_payload = {
            **{k: v for k, v in settings_data.items() if k != 'change_id'},
            'change_id': settings_data.get('change_id') or str(uuid.uuid4()),
            'pet_id': pet_id,
            'effective_date': effective_date,
            'created_at': settings_data.get('updated_at') or DateTimeUtils.now(),
        }

        firestore_payload = DateTimeUtils.for_firestore(history_payload)
        history_collection = self.settings_history_ref.document(pet_id).collection('changes')

        if transaction is not None:
            history_doc = history_collection.document()
            transaction.set(history_doc, firestore_payload)
        else:
            history_collection.add(firestore_payload)

        logging.info(
            "Pet care settings history saved",
            extra={'pet_id': pet_id, 'effective_date': effective_date},
        )

    @staticmethod
    def _ensure_derived_fields(settings: Dict[str, Any]) -> None:
        sessions = settings.get('goalActivitySessions') or 0
        per_session = settings.get('activitySessionMinutes') or 0
        if sessions > 0 and per_session > 0:
            settings['goalActivityMinutes'] = sessions * per_session