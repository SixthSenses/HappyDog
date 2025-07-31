from firebase_admin import firestore
from typing import Optional, Dict, Any
from dataclasses import asdict
from datetime import date, datetime
from app.models.pet import Pet

class PetService:
    """반려동물 관련 비즈니스 로직을 담당하는 서비스 클래스"""
    def __init__(self):
        """
        객체 생성 시점에는 DB에 연결하지 않고, 내부 변수를 None으로 초기화합니다.
        """
        self.db = None
        self.pets_ref = None

    def init_app(self):
        """
        app의 초기화 과정에서 호출되어 실제 DB 연결을 완료합니다.
        """
        self.db = firestore.client()
        self.pets_ref = self.db.collection('pets')

    def get_pet_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """user_id로 반려동물 문서를 찾아 딕셔너리로 반환합니다."""
        query = self.pets_ref.where('user_id', '==', user_id).limit(1).stream()
        pet_doc = next(query, None)
        if pet_doc:
            pet_data = pet_doc.to_dict()
            pet_data['pet_id'] = pet_doc.id # 문서 ID를 포함하여 반환
            return pet_data
        return None

    def create_pet(self, new_pet: Pet) -> Dict[str, Any]:
        """새로운 반려동물 정보를 Firestore에 저장합니다."""
        pet_data_dict = asdict(new_pet)
        pet_data_dict['gender'] = new_pet.gender.value
        
        # --- 수정된 부분: datetime.date 객체를 datetime.datetime으로 변환 ---
        if 'birthdate' in pet_data_dict and isinstance(pet_data_dict['birthdate'], date):
            bdate = pet_data_dict['birthdate']
            pet_data_dict['birthdate'] = datetime(bdate.year, bdate.month, bdate.day)
        # ----------------------------------------------------------------

        self.pets_ref.document(new_pet.pet_id).set(pet_data_dict)
        return pet_data_dict

    def update_pet(self, pet_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """기존 반려동물 정보를 업데이트합니다."""
        
        # --- 수정된 부분: datetime.date 객체를 datetime.datetime으로 변환 ---
        if 'birthdate' in update_data and isinstance(update_data['birthdate'], date):
            bdate = update_data['birthdate']
            update_data['birthdate'] = datetime(bdate.year, bdate.month, bdate.day)
        # ----------------------------------------------------------------

        pet_ref = self.pets_ref.document(pet_id)
        pet_ref.update(update_data)
        updated_doc = pet_ref.get()
        if updated_doc.exists:
            return updated_doc.to_dict()
        return None