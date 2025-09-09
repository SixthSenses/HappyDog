"""Thin aggregator module for Pet Care Record services.

이 파일은 이전 단일 거대 `services.py`를 V1 / V2 로 분리한 뒤,
라우트 코드가 기존 import 경로(`app.api.pet_care.records.services`)를 계속 사용할 수 있도록
얇은 어댑터 클래스를 제공한다.

구성:
 - PetCareRecordServiceV1: CRUD 및 레거시/범용 조회
 - PetCareRecordServiceV2: 신규 평탄화/범위/요약 조회
 - PetCareRecordService: 두 버전을 합친 퍼사드(Facade)

주의:
 - 신규 기능 추가 시 직접 이 파일에 비즈니스 로직을 넣지 말고, 해당 버전 서비스 클래스를 확장.
 - 향후 스키마 마이그레이션(예: data 객체화)은 V2 계층에 우선 적용 후 V1 듀얼리드 고려.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .services_v1 import PetCareRecordServiceV1
from .services_v2 import PetCareRecordServiceV2


class PetCareRecordService:
    """Facade aggregating V1 & V2 services.

    라우트에서 기존 메소드 이름을 그대로 호출할 수 있도록 위임(delegate)만 수행한다.
    """

    def __init__(self):
        self.v1 = PetCareRecordServiceV1()
        self.v2 = PetCareRecordServiceV2(self.v1)

    # ---------------- V1 위임 (CRUD & legacy/flexible) ----------------
    def create_care_record(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.v1.create_care_record(pet_id, record_data)

    def update_care_record(self, pet_id: str, log_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.v1.update_care_record(pet_id, log_id, payload)

    def delete_care_record(self, pet_id: str, log_id: str) -> str:
        return self.v1.delete_care_record(pet_id, log_id)

    def get_records_flexible(self, pet_id: str, query_params: Dict[str, Any]) -> Dict[str, Any]:
        return self.v1.get_records_flexible(pet_id, query_params)

    def get_daily_records(self, pet_id: str, date_str: str) -> Dict[str, List[Dict]]:
        return self.v1.get_daily_records(pet_id, date_str)

    def get_records_for_date_range(self, pet_id: str, start_date: str, end_date: str) -> Dict[str, List[Dict]]:
        return self.v1.get_records_for_date_range(pet_id, start_date, end_date)

    def get_records_by_type(self, pet_id: str, record_type: str, date_str: str = None,
                            start_date: str = None, end_date: str = None, limit: int = 50,
                            cursor: str = None) -> Dict[str, Any]:
        return self.v1.get_records_by_type(pet_id, record_type, date_str, start_date, end_date, limit, cursor)

    # ---------------- V2 위임 (신규 스펙) ----------------
    def get_daily_v2(self, pet_id: str, date: str, record_types: Optional[List[str]] = None,
                     limit: int = 100, cursor: Optional[str] = None) -> Dict[str, Any]:
        return self.v2.get_daily_v2(pet_id, date, record_types, limit, cursor)

    def get_range_v2(self, pet_id: str, start_date: str, end_date: str,
                      record_types: Optional[List[str]] = None, limit: int = 300,
                      cursor: Optional[str] = None) -> Dict[str, Any]:
        return self.v2.get_range_v2(pet_id, start_date, end_date, record_types, limit, cursor)

    def get_summary_v2(self, pet_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
        return self.v2.get_summary_v2(pet_id, start_date, end_date)


__all__ = ["PetCareRecordService"]
