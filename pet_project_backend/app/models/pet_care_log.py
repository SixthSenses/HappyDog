# app/models/pet_care_log.py
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

@dataclass
class PetCareLog:
        """Firestore 'pet_care_logs' 문서 구조 (API 스펙 정합).

        필드명은 swagger 및 응답 스키마(PetCareRecord) 와 일치하도록 구성:
            - log_id
            - pet_id
            - record_type
            - timestamp (UTC datetime)
            - searchDate (YYYY-MM-DD)
            - data
            - memo (선택)
            - user_id (내부 추적용, 선택)
        """
        log_id: str
        pet_id: str
        record_type: str
        timestamp: datetime
        searchDate: str
        data: Any
        memo: Optional[str] = ""
        user_id: Optional[str] = None