# app/models/pet.py
from dataclasses import dataclass ,field
from datetime import date
from typing import Optional, List
from enum import Enum

class PetGender(Enum):
    """반려동물 성별을 나타내는 Enum 클래스"""
    MALE = "MALE"
    FEMALE = "FEMALE"

@dataclass
class Pet:
    """
    Firestore 'pets' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    """
    pet_id: str
    user_id: str
    name: str
    gender: PetGender
    breed: str
    birthdate: date
    fur_color: str
    health_concerns: List[str] = field(default_factory=list)
    nose_print_url: Optional[str] = None
    faiss_id: Optional[int] = None
    