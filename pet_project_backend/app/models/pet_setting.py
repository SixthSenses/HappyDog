# app/models/pet_setting.py
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class PetCareSetting:
    """
    Firestore 'pet_settings' 컬렉션 문서 구조.
    pet_id를 문서 ID로 사용하여 pets 문서와 1:1 관계를 맺음.
    """
    pet_id: str
    goalWeight: float
    waterBowlCapacity: int
    waterIncrementAmount: int
    goalActivityMinutes: int
    activityIncrementMinutes: int
    goalMealCount: int
    mealIncrementCount: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)