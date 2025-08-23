# app/api/pet_care/settings/services.py
import logging
from typing import Dict, Any
from firebase_admin import firestore
from firebase_admin.firestore import Transaction
from app.api.breeds.services import BreedService
from app.utils.datetime_utils import DateTimeUtils  # 핵심 유틸리티 임포트

class PetCareSettingService:
    """반려동물의 케어 목표 설정 관리를 전담하는 서비스 클래스."""
    def __init__(self, breed_service: BreedService):
        self.db = firestore.client()
        self.settings_ref = self.db.collection('pet_settings')
        self.breed_service = breed_service
        logging.info("PetCareSettingService initialized.")

    def create_initial_settings_transactional(self, transaction: Transaction, pet_id: str, gender: str, breed: str, current_weight: float):
        """
        [트랜잭션용] 최초 반려동물 등록 시 초기 설정값을 생성합니다.
        PetService의 트랜잭션 내에서 호출되어 데이터 정합성을 보장합니다.
        """
        try:
            # 1. 품종별 이상 체중 조회
            ideal_weight = self.breed_service.get_breed_ideal_weight(breed, gender)
            goal_weight = ideal_weight if ideal_weight is not None else current_weight

            # 2. 제안서 요구사항에 따른 값 계산
            water_bowl_capacity = round(current_weight * 60)
            water_increment = max(1, round(water_bowl_capacity * 0.2)) # 최소 1 보장

            settings_data = {
                "pet_id": pet_id,
                "goalWeight": goal_weight,
                "waterBowlCapacity": water_bowl_capacity,
                "waterIncrementAmount": water_increment,
                "goalActivityMinutes": 30,
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
        """펫케어 설정 정보를 조회합니다."""
        doc = self.settings_ref.document(pet_id).get()
        if not doc.exists:
            raise FileNotFoundError("해당 반려동물의 펫케어 설정을 찾을 수 없습니다.")
        return doc.to_dict()

    def update_settings(self, pet_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """펫케어 설정 정보를 부분 업데이트합니다."""
        doc_ref = self.settings_ref.document(pet_id)
        if not doc_ref.get().exists:
            raise FileNotFoundError("해당 반려동물의 펫케어 설정을 찾을 수 없습니다.")
        
        # 업데이트 시간 기록 시 표준 유틸리티 사용
        update_data['updated_at'] = DateTimeUtils.now()
        firestore_data = DateTimeUtils.for_firestore(update_data)
        
        doc_ref.update(firestore_data)
        logging.info(f"Pet care settings updated for {pet_id}")
        return self.get_settings(pet_id)