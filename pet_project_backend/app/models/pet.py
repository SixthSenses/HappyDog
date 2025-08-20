# app/models/pet.py
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Dict, Any
from enum import Enum

class PetGender(Enum):
    """반려동물 성별을 나타내는 Enum 클래스"""
    MALE = "MALE"
    FEMALE = "FEMALE"

class ActivityLevel(Enum):
    """반려동물 활동 수준을 나타내는 Enum 클래스"""
    INACTIVE = "비활동적"
    LIGHT = "가벼운 활동"
    MODERATE = "중간 수준 활동"
    ACTIVE = "활동적"
    VERY_ACTIVE = "매우 활동적"

class DietType(Enum):
    """반려동물 식단 타입을 나타내는 Enum 클래스"""
    DRY_FOOD = "주로 건사료"
    WET_FOOD = "주로 습식사료"
    MIXED = "혼합"
    RAW = "생식"

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
    
    # 펫케어 기능을 위한 추가 필드들
    activity_level: Optional[ActivityLevel] = None  # 활동 수준
    diet_type: Optional[DietType] = None            # 식단 타입
    is_neutered: Optional[bool] = None              # 중성화 여부
    current_weight: Optional[float] = None          # 현재 몸무게 (kg)
    care_settings: Optional[Dict[str, Any]] = None  # 사용자 설정 (빠른 증감 기본값 등)
    