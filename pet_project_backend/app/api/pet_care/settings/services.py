# app/api/pet_care/settings/services.py
import logging
from typing import Dict, Any, Optional
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
        if not doc_ref.get().exists:
            raise FileNotFoundError("해당 반려동물의 펫케어 설정을 찾을 수 없습니다.")
        # goalActivityMinutes 직접 수정 요청은 무시 (Method A)
        if 'goalActivityMinutes' in update_data:
            update_data.pop('goalActivityMinutes')

        # 업데이트 시점 기록
        update_data['updated_at'] = DateTimeUtils.now()
        firestore_data = DateTimeUtils.for_firestore(update_data)
        doc_ref.update(firestore_data)

        # 저장 후 파생 목표 재계산을 위해 최신 문서 불러온 뒤 세션×분 계산
        latest = self.get_settings(pet_id)
        sessions = latest.get("goalActivitySessions") or 0
        per_session = latest.get("activitySessionMinutes") or 0
        if sessions > 0 and per_session > 0:
            derived = sessions * per_session
            # 파생값 저장 여부: Method A에서는 저장 강제 필요 X (메모리 계산만).
            # 그러나 기존 문서와의 호환 위해 필드가 있었다면 덮어쓸 수 있음 (선택). 여기서는 저장 생략.
            latest["goalActivityMinutes"] = derived
        logging.info(f"Pet care settings updated for {pet_id} (Method A derived minutes applied in response)")
        return latest