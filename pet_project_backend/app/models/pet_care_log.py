# app/models/pet_care_log.py
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict
from enum import Enum
from uuid import uuid4

class FoodType(Enum):
    """음식 타입을 나타내는 Enum 클래스"""
    MEAL = "식사"
    SNACK = "간식"
    TREAT = "트릿"

class PoopShape(Enum):
    """변 모양을 나타내는 Enum 클래스"""
    NORMAL = "정상 변"
    SOFT = "무른 변"
    DIARRHEA = "설사"
    CONSTIPATION = "변비"
    HARD = "딱딱한 변"

class PoopColor(Enum):
    """변 색깔을 나타내는 Enum 클래스"""
    BROWN = "황토색"
    DARK_BROWN = "갈색"
    BLACK = "흑색"
    RED = "적색"
    GREEN = "녹색"
    YELLOW = "노란색"

class PoopSpecialNote(Enum):
    """변 특이사항을 나타내는 Enum 클래스"""
    MUCUS = "점액변"
    BLOOD = "혈변"
    WORMS = "기생충"
    UNDIGESTED_FOOD = "소화되지 않은 음식"
    FOREIGN_OBJECT = "이물질"

class ActivityType(Enum):
    """활동 타입을 나타내는 Enum 클래스"""
    WALK = "산책"
    PLAY = "놀이"
    EXERCISE = "운동"
    TRAINING = "훈련"
    RUN = "달리기"
    SWIMMING = "수영"

class ActivityIntensity(Enum):
    """활동 강도를 나타내는 Enum 클래스"""
    LIGHT = "가벼운"
    MODERATE = "보통"
    INTENSE = "격렬한"

class VomitType(Enum):
    """구토 타입을 나타내는 Enum 클래스"""
    FOOD = "음식"
    LIQUID = "액체"
    FOAM = "거품"
    BILE = "담즙"
    BLOOD = "혈액"

@dataclass
class FoodLog:
    """음식 섭취 로그"""
    log_id: str = field(default_factory=lambda: str(uuid4()))  # 고유 ID
    calories: float                     # 칼로리
    timestamp: datetime                 # 섭취 시간
    food_type: FoodType                # 음식 타입 (식사/간식/트릿)
    food_name: Optional[str] = None     # 음식명
    amount_g: Optional[float] = None    # 섭취량 (그램)
    notes: Optional[str] = None         # 특이사항

@dataclass
class WaterLog:
    """물 섭취 로그"""
    log_id: str = field(default_factory=lambda: str(uuid4()))  # 고유 ID
    amount_ml: float                    # 섭취량 (밀리리터)
    timestamp: datetime                 # 섭취 시간
    notes: Optional[str] = None         # 특이사항

@dataclass
class PoopLog:
    """배변 로그"""
    log_id: str = field(default_factory=lambda: str(uuid4()))  # 고유 ID
    shape: PoopShape                    # 변 모양
    color: PoopColor                    # 변 색깔
    timestamp: datetime                 # 배변 시간
    special_notes: List[PoopSpecialNote] = field(default_factory=list)  # 특이사항 목록
    size: Optional[str] = None          # 크기 (작음/보통/큼)
    notes: Optional[str] = None         # 추가 메모

@dataclass
class ActivityLog:
    """활동 로그"""
    log_id: str = field(default_factory=lambda: str(uuid4()))  # 고유 ID
    duration_minutes: int               # 활동 시간 (분)
    activity_type: ActivityType         # 활동 타입
    intensity: ActivityIntensity        # 활동 강도
    timestamp: datetime                 # 활동 시간
    distance_km: Optional[float] = None # 거리 (킬로미터)
    calories_burned: Optional[float] = None  # 소모 칼로리
    notes: Optional[str] = None         # 특이사항

@dataclass
class VomitLog:
    """구토 로그"""
    log_id: str = field(default_factory=lambda: str(uuid4()))  # 고유 ID
    vomit_type: VomitType              # 구토 타입
    timestamp: datetime                 # 구토 시간
    amount: Optional[str] = None        # 양 (적음/보통/많음)
    frequency: int = 1                  # 횟수
    notes: Optional[str] = None         # 특이사항

@dataclass
class WeightLog:
    """체중 로그"""
    log_id: str = field(default_factory=lambda: str(uuid4()))  # 고유 ID
    weight_kg: float                    # 체중 (킬로그램)
    timestamp: datetime                 # 측정 시간
    measurement_method: Optional[str] = None  # 측정 방법
    notes: Optional[str] = None         # 특이사항

@dataclass
class MedicationLog:
    """투약 로그"""
    log_id: str = field(default_factory=lambda: str(uuid4()))  # 고유 ID
    medication_name: str                # 약물명
    dosage: str                        # 투여량
    timestamp: datetime                 # 투약 시간
    medication_type: Optional[str] = None  # 약물 종류 (처방약/영양제/등)
    notes: Optional[str] = None         # 특이사항

@dataclass
class SymptomsLog:
    """증상 로그"""
    log_id: str = field(default_factory=lambda: str(uuid4()))  # 고유 ID
    symptoms: List[str]                 # 증상 목록
    timestamp: datetime                 # 관찰 시간
    severity: Optional[str] = None      # 심각도 (경미/보통/심각)
    duration_minutes: Optional[int] = None  # 지속 시간 (분)
    notes: Optional[str] = None         # 특이사항

@dataclass
class PetCareLog:
    """
    Firestore 'pet_care_logs' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    하루 단위로 반려동물의 모든 케어 기록을 저장합니다.
    """
    log_id: str                         # 로그 고유 ID
    pet_id: str                         # 반려동물 ID
    user_id: str                        # 사용자 ID
    date: date                          # 기록 날짜 (YYYY-MM-DD)
    
    # 각종 로그 목록들
    food_logs: List[FoodLog] = field(default_factory=list)         # 음식 섭취 기록
    water_logs: List[WaterLog] = field(default_factory=list)       # 물 섭취 기록
    poop_logs: List[PoopLog] = field(default_factory=list)         # 배변 기록
    activity_logs: List[ActivityLog] = field(default_factory=list) # 활동 기록
    vomit_logs: List[VomitLog] = field(default_factory=list)       # 구토 기록
    weight_logs: List[WeightLog] = field(default_factory=list)     # 체중 기록
    medication_logs: List[MedicationLog] = field(default_factory=list)  # 투약 기록
    symptoms_logs: List[SymptomsLog] = field(default_factory=list) # 증상 기록
    
    # 하루 총합 정보
    total_calories: float = 0.0         # 총 섭취 칼로리
    total_water_ml: float = 0.0         # 총 물 섭취량 (ml)
    total_activity_minutes: int = 0     # 총 활동 시간 (분)
    current_weight_kg: Optional[float] = None  # 당일 체중 (kg)
    
    # 메타데이터
    general_notes: Optional[str] = None # 일반 메모
    mood: Optional[str] = None          # 기분/상태 (좋음/보통/나쁨)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_totals(self):
        """로그들을 기반으로 총합 정보를 계산합니다."""
        # 총 칼로리 계산
        self.total_calories = sum(log.calories for log in self.food_logs)
        
        # 총 물 섭취량 계산
        self.total_water_ml = sum(log.amount_ml for log in self.water_logs)
        
        # 총 활동 시간 계산
        self.total_activity_minutes = sum(log.duration_minutes for log in self.activity_logs)
        
        # 가장 최근 체중 사용
        if self.weight_logs:
            latest_weight_log = max(self.weight_logs, key=lambda x: x.timestamp)
            self.current_weight_kg = latest_weight_log.weight_kg
        
        # 업데이트 시간 갱신
        self.updated_at = datetime.utcnow()

@dataclass
class PetCareLogSummary:
    """
    월별/주별 펫케어 로그 요약 정보를 위한 데이터클래스
    """
    period: str                         # 기간 (YYYY-MM 또는 YYYY-WW)
    pet_id: str                         # 반려동물 ID
    user_id: str                        # 사용자 ID
    
    # 기간 내 통계
    total_days_logged: int = 0          # 기록된 일수
    avg_calories_per_day: float = 0.0   # 일평균 칼로리
    avg_water_ml_per_day: float = 0.0   # 일평균 물 섭취량
    avg_activity_minutes_per_day: int = 0  # 일평균 활동 시간
    
    # 가중치별 통계
    weight_changes: List[Dict] = field(default_factory=list)  # 체중 변화 기록
    poop_frequency_per_day: float = 0.0    # 일평균 배변 횟수
    vomit_frequency_per_day: float = 0.0   # 일평균 구토 횟수
    
    # 특이사항
    concerning_symptoms: List[str] = field(default_factory=list)  # 주의할 증상들
    
    created_at: datetime = field(default_factory=datetime.utcnow)
