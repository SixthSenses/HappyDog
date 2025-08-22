# app/models/pet_care_log.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

@dataclass
class PetCareLog:
    """
    Firestore 'pet_care_logs' 컬렉션 문서 구조.
    모든 동적/시계열 데이터를 통합하여 관리.
    """
    log_id: str
    pet_id: str
    record_type: str  # 'weight', 'water', 'activity', 'meal'
    timestamp: datetime # 클라이언트 제공 Unix timestamp(ms)를 변환한 UTC datetime
    searchDate: str   # 조회 최적화를 위한 YYYY-MM-DD 형식의 문자열
    data: Any         # 실제 기록 값 (예: 5.2, 1, 30)
    notes: Optional[str] = None