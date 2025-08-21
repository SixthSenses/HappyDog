# app/api/pet_care/services_new/base.py
"""
펫케어 서비스 기본 클래스
모든 펫케어 서비스가 상속받는 기본 기능 제공
"""

import logging
from datetime import date, datetime
from typing import Any, Optional, Dict
from dataclasses import asdict
from firebase_admin import firestore

from app.utils.datetime_utils import DateTimeUtils
from app.api.breeds.services import BreedService

logger = logging.getLogger(__name__)


class BasePetCareService:
    """
    펫케어 서비스의 기본 클래스
    공통 기능과 유틸리티 메서드 제공
    """
    
    def __init__(self, breed_service: Optional[BreedService] = None):
        self.db = firestore.client()
        self.pets_collection = self.db.collection('pets')
        self.care_logs_collection = self.db.collection('pet_care_logs')
        self.breed_service = breed_service or BreedService()
    
    def _convert_date_for_firestore(self, obj: Any) -> Any:
        """Firestore 저장을 위해 날짜/시간 객체를 변환합니다."""
        return DateTimeUtils.for_firestore(obj)
    
    def _convert_firestore_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Firestore에서 가져온 데이터를 Python 객체로 변환합니다."""
        return DateTimeUtils.from_firestore(data)
    
    def _verify_pet_ownership(self, pet_id: str, user_id: str) -> bool:
        """펫 소유권을 확인합니다."""
        try:
            pet_doc = self.pets_collection.document(pet_id).get()
            if not pet_doc.exists:
                return False
            
            pet_data = pet_doc.to_dict()
            return pet_data.get('user_id') == user_id
        except Exception:
            return False
    
    def _get_or_create_daily_log(self, pet_id: str, user_id: str, log_date: date) -> str:
        """
        특정 날짜의 PetCareLog 문서를 가져오거나 생성합니다.
        
        Returns:
            문서 ID (log_id)
        """
        from app.models.pet_care_log import PetCareLog
        
        log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
        doc_ref = self.care_logs_collection.document(log_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            # 새 문서 생성
            new_log = PetCareLog(
                log_id=log_id,
                pet_id=pet_id,
                user_id=user_id,
                date=log_date
            )
            doc_ref.set(self._convert_date_for_firestore(asdict(new_log)))
            logger.info(f"새 일일 로그 문서 생성: {log_id}")
        
        return log_id
    
    def _find_log_in_array(self, logs_array: list, log_id: str) -> Optional[dict]:
        """배열에서 특정 log_id를 가진 로그를 찾습니다."""
        for log in logs_array:
            if log.get('log_id') == log_id:
                return log
        return None
    
    def _update_total_and_current(self, doc_ref, field_updates: dict):
        """문서의 총합 정보와 현재 값을 업데이트합니다."""
        try:
            doc = doc_ref.get()
            if not doc.exists:
                return
            
            data = doc.to_dict()
            
            # 총합 계산 로직
            if 'food_logs' in data:
                field_updates['total_calories'] = sum(
                    log.get('calories', 0) for log in data.get('food_logs', [])
                )
            
            if 'water_logs' in data:
                field_updates['total_water_ml'] = sum(
                    log.get('amount_ml', 0) for log in data.get('water_logs', [])
                )
            
            if 'activity_logs' in data:
                field_updates['total_activity_minutes'] = sum(
                    log.get('duration_minutes', 0) for log in data.get('activity_logs', [])
                )
            
            if 'weight_logs' in data and data['weight_logs']:
                # 가장 최근 체중을 현재 체중으로 설정
                sorted_weights = sorted(
                    data['weight_logs'], 
                    key=lambda x: x.get('timestamp', datetime.min), 
                    reverse=True
                )
                field_updates['current_weight_kg'] = sorted_weights[0].get('weight_kg')
            
            # 업데이트 시간 추가
            field_updates['updated_at'] = DateTimeUtils.now()
            
            doc_ref.update(field_updates)
            
        except Exception as e:
            logger.error(f"총합 정보 업데이트 실패: {e}")
