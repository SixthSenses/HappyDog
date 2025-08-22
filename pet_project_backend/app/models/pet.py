# app/models/pet.py
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List
from enum import Enum

class PetGender(Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"

@dataclass
class Pet:
    """
    Firestore 'pets' 컬렉션 문서 구조.
    반려동물의 정체성(Identity)과 관련된 정적 데이터를 관리.
    """
    pet_id: str
    user_id: str
    name: str
    gender: PetGender
    breed: str
    birthdate: date
    
    # 최초 등록 시 체중. 동적인 체중 변화는 PetCareLog에서 관리.
    initial_weight: float
    
    # 생체 정보 (Biometrics) - 정체성의 일부
    is_verified: bool = False
    nose_print_url: Optional[str] = None
    faiss_id: Optional[int] = None
    
    # 기타 정적 정보
    fur_color: Optional[str] = None
    health_concerns: List[str] = field(default_factory=list)