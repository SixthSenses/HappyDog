#app/models/pet.py

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from enum import Enum

class PetGender(Enum):
    """반려동물 성별을 나타내는 Enum 클래스"""
    MALE = "MALE"
    FEMALE = "FEMALE"
@dataclass
class Pet:
    """반려동물 데이터 구조를 정의하는 데이터클래스"""
    # pet_id: 반려동물의 고유 ID. Firestore 문서 ID와 동일하게 사용됩니다.
    pet_id: str
    
    # user_id: 이 반려동물의 소유자를 가리키는 User의 ID (FK 역할).
    user_id: str
    
    # name: 반려동물의 이름입니다.
    name: str
    
    # gender: 반려동물의 성별 ('MALE' 또는 'FEMALE').
    gender: PetGender
    
    # breed: 반려동물의 견종입니다.
    breed: str
    
    # birthdate: 반려동물의 생년월일입니다.
    birthdate: date
    
    # is_neutered: 중성화 수술 여부입니다.
    #is_neutered: bool
    
    # is_verified: 비문 인증 완료 여부. 최초 등록 시 항상 False로 설정됩니다.
    is_verified: bool = False
    nose_print_url: Optional[str] = None
    faiss_id: Optional[int] = None
    # vaccination_status: 예방접종 관련 정보 (선택 사항).
    vaccination_status: Optional[str] = None
    
    # weight: 체중. 기획이 미확정되어 모델에만 포함하고 API 요청으로는 받지 않습니다.
    weight: Optional[float] = None