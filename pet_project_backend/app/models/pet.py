# app/models/pet.py
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

class PetGender(Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"

@dataclass
class Pet:
    """
    Firestore 'pets' 컬렉션 문서 구조.
    반려동물의 정체성(Identity)과 관련된 정적 데이터를 관리.
    데이터베이스와의 상호 변환 로직을 포함하여 모델의 책임을 강화.
    """
    pet_id: str
    user_id: str
    name: str
    gender: PetGender
    breed: str
    birthdate: date
    initial_weight: float
    is_verified: bool = False
    nose_print_url: Optional[str] = None
    faiss_id: Optional[int] = None
    fur_color: Optional[str] = None
    health_concerns: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pet":
        """
        [신규] Firestore에서 받은 딕셔너리로부터 Pet 데이터클래스 인스턴스를 생성합니다.
        문자열로 저장된 Enum 값을 자동으로 변환하고, Timestamp를 date 객체로 변환합니다.
        """
        # 데이터 복사본 생성 (원본 데이터 변경 방지)
        processed_data = data.copy()
        
        # gender 필드의 문자열 값을 PetGender Enum 멤버로 변환
        gender_str = processed_data.get('gender')
        if gender_str and isinstance(gender_str, str):
            try:
                processed_data['gender'] = PetGender(gender_str)
            except ValueError:
                logging.warning(f"Invalid PetGender value '{gender_str}' for pet {processed_data.get('pet_id')}. Defaulting to MALE.")
                processed_data['gender'] = PetGender.MALE
        
        # Firestore Timestamp 객체를 Python date 객체로 변환
        birthdate_obj = processed_data.get('birthdate')
        if birthdate_obj:
            if hasattr(birthdate_obj, 'date'):  # Firestore Timestamp 객체
                processed_data['birthdate'] = birthdate_obj.date()
            elif isinstance(birthdate_obj, datetime):  # Python datetime 객체
                processed_data['birthdate'] = birthdate_obj.date()
            elif isinstance(birthdate_obj, str):  # 문자열 형태의 날짜
                try:
                    processed_data['birthdate'] = datetime.strptime(birthdate_obj, "%Y-%m-%d").date()
                except ValueError:
                    logging.warning(f"Invalid birthdate format '{birthdate_obj}' for pet {processed_data.get('pet_id')}")
                    # 기본값 설정 또는 에러 처리
                    processed_data['birthdate'] = date.today()
        
        # health_concerns가 None인 경우 빈 리스트로 초기화
        if processed_data.get('health_concerns') is None:
            processed_data['health_concerns'] = []
            
        return cls(**processed_data)