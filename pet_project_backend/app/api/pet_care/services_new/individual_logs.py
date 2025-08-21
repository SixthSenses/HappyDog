# app/api/pet_care/services_new/individual_logs.py
"""
개별 로그 타입별 관리 서비스
"""

import logging
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from dataclasses import asdict
import uuid
from firebase_admin import firestore

from .base import BasePetCareService
from app.models.pet_care_log import (
    FoodLog, WaterLog, PoopLog, ActivityLog, 
    VomitLog, WeightLog, FoodType, ActivityType,
    ActivityIntensity, PoopShape, PoopColor, VomitType
)
from app.utils.datetime_utils import DateTimeUtils

logger = logging.getLogger(__name__)


class IndividualLogService(BasePetCareService):
    """
    개별 로그 타입별 CRUD를 담당하는 서비스
    """
    
    # 음식 로그 관련 메서드
    def add_food_log(self, pet_id: str, user_id: str, log_date: date, food_data: Dict[str, Any]) -> str:
        """음식 섭취 로그를 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            doc_ref = self.care_logs_collection.document(log_id)
            
            # 새 음식 로그 생성
            new_food_log = FoodLog(
                log_id=str(uuid.uuid4()),
                calories=food_data['calories'],
                timestamp=food_data['timestamp'],
                date=log_date,
                food_type=FoodType(food_data['food_type']),
                food_name=food_data.get('food_name'),
                amount_g=food_data.get('amount_g'),
                notes=food_data.get('notes')
            )
            
            # Enum을 문자열로 변환
            food_log_dict = asdict(new_food_log)
            food_log_dict['food_type'] = new_food_log.food_type.value
            
            # Firestore 업데이트
            doc_ref.update({
                'food_logs': firestore.ArrayUnion([
                    self._convert_date_for_firestore(food_log_dict)
                ])
            })
            
            # 총합 업데이트
            self._update_total_and_current(doc_ref, {})
            
            logger.info(f"음식 로그 추가 완료: {new_food_log.log_id}")
            return new_food_log.log_id
            
        except Exception as e:
            logger.error(f"음식 로그 추가 실패: {e}")
            raise
    
    def update_food_log(self, pet_id: str, user_id: str, log_date: date, 
                       food_log_id: str, update_data: Dict[str, Any]) -> bool:
        """음식 로그를 수정합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            doc_ref = self.care_logs_collection.document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ValueError("해당 날짜의 로그가 존재하지 않습니다.")
            
            data = doc.to_dict()
            food_logs = data.get('food_logs', [])
            
            # 해당 로그 찾기 및 수정
            updated = False
            for i, log in enumerate(food_logs):
                if log.get('log_id') == food_log_id:
                    # 업데이트 데이터 적용
                    if 'calories' in update_data:
                        food_logs[i]['calories'] = update_data['calories']
                    if 'food_name' in update_data:
                        food_logs[i]['food_name'] = update_data['food_name']
                    if 'amount_g' in update_data:
                        food_logs[i]['amount_g'] = update_data['amount_g']
                    if 'notes' in update_data:
                        food_logs[i]['notes'] = update_data['notes']
                    
                    updated = True
                    break
            
            if not updated:
                raise ValueError("해당 음식 로그를 찾을 수 없습니다.")
            
            # Firestore 업데이트
            doc_ref.update({
                'food_logs': food_logs,
                'updated_at': DateTimeUtils.now()
            })
            
            # 총합 업데이트
            self._update_total_and_current(doc_ref, {})
            
            logger.info(f"음식 로그 수정 완료: {food_log_id}")
            return True
            
        except Exception as e:
            logger.error(f"음식 로그 수정 실패: {e}")
            raise
    
    def delete_food_log(self, pet_id: str, user_id: str, log_date: date, food_log_id: str) -> bool:
        """음식 로그를 삭제합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            doc_ref = self.care_logs_collection.document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ValueError("해당 날짜의 로그가 존재하지 않습니다.")
            
            data = doc.to_dict()
            food_logs = data.get('food_logs', [])
            
            # 해당 로그 제거
            food_logs = [log for log in food_logs if log.get('log_id') != food_log_id]
            
            # Firestore 업데이트
            doc_ref.update({
                'food_logs': food_logs,
                'updated_at': DateTimeUtils.now()
            })
            
            # 총합 업데이트
            self._update_total_and_current(doc_ref, {})
            
            logger.info(f"음식 로그 삭제 완료: {food_log_id}")
            return True
            
        except Exception as e:
            logger.error(f"음식 로그 삭제 실패: {e}")
            raise
    
    # 물 로그 관련 메서드
    def add_water_log(self, pet_id: str, user_id: str, log_date: date, water_data: Dict[str, Any]) -> str:
        """물 섭취 로그를 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            doc_ref = self.care_logs_collection.document(log_id)
            
            # 새 물 로그 생성
            new_water_log = WaterLog(
                log_id=str(uuid.uuid4()),
                amount_ml=water_data['amount_ml'],
                timestamp=water_data['timestamp'],
                date=log_date,
                notes=water_data.get('notes')
            )
            
            # Firestore 업데이트
            doc_ref.update({
                'water_logs': firestore.ArrayUnion([
                    self._convert_date_for_firestore(asdict(new_water_log))
                ])
            })
            
            # 총합 업데이트
            self._update_total_and_current(doc_ref, {})
            
            logger.info(f"물 로그 추가 완료: {new_water_log.log_id}")
            return new_water_log.log_id
            
        except Exception as e:
            logger.error(f"물 로그 추가 실패: {e}")
            raise
    
    # 활동 로그 관련 메서드
    def add_activity_log(self, pet_id: str, user_id: str, log_date: date, activity_data: Dict[str, Any]) -> str:
        """활동 로그를 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            doc_ref = self.care_logs_collection.document(log_id)
            
            # 새 활동 로그 생성
            new_activity_log = ActivityLog(
                log_id=str(uuid.uuid4()),
                duration_minutes=activity_data['duration_minutes'],
                activity_type=ActivityType(activity_data['activity_type']),
                intensity=ActivityIntensity(activity_data['intensity']),
                timestamp=activity_data['timestamp'],
                date=log_date,
                distance_km=activity_data.get('distance_km'),
                notes=activity_data.get('notes')
            )
            
            # Enum을 문자열로 변환
            activity_log_dict = asdict(new_activity_log)
            activity_log_dict['activity_type'] = new_activity_log.activity_type.value
            activity_log_dict['intensity'] = new_activity_log.intensity.value
            
            # Firestore 업데이트
            doc_ref.update({
                'activity_logs': firestore.ArrayUnion([
                    self._convert_date_for_firestore(activity_log_dict)
                ])
            })
            
            # 총합 업데이트
            self._update_total_and_current(doc_ref, {})
            
            logger.info(f"활동 로그 추가 완료: {new_activity_log.log_id}")
            return new_activity_log.log_id
            
        except Exception as e:
            logger.error(f"활동 로그 추가 실패: {e}")
            raise
    
    # 체중 로그 관련 메서드
    def add_weight_log(self, pet_id: str, user_id: str, log_date: date, weight_data: Dict[str, Any]) -> str:
        """체중 로그를 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            doc_ref = self.care_logs_collection.document(log_id)
            
            # 새 체중 로그 생성
            new_weight_log = WeightLog(
                log_id=str(uuid.uuid4()),
                weight_kg=weight_data['weight_kg'],
                timestamp=weight_data['timestamp'],
                date=log_date,
                bcs_level=weight_data.get('bcs_level'),
                notes=weight_data.get('notes')
            )
            
            # Firestore 업데이트
            doc_ref.update({
                'weight_logs': firestore.ArrayUnion([
                    self._convert_date_for_firestore(asdict(new_weight_log))
                ])
            })
            
            # 총합 업데이트 (현재 체중 포함)
            self._update_total_and_current(doc_ref, {})
            
            logger.info(f"체중 로그 추가 완료: {new_weight_log.log_id}")
            return new_weight_log.log_id
            
        except Exception as e:
            logger.error(f"체중 로그 추가 실패: {e}")
            raise
    
    # 배변 로그 관련 메서드
    def add_poop_log(self, pet_id: str, user_id: str, log_date: date, poop_data: Dict[str, Any]) -> str:
        """배변 로그를 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            doc_ref = self.care_logs_collection.document(log_id)
            
            # 새 배변 로그 생성
            new_poop_log = PoopLog(
                log_id=str(uuid.uuid4()),
                shape=PoopShape(poop_data['shape']),
                color=PoopColor(poop_data['color']),
                timestamp=poop_data['timestamp'],
                date=log_date,
                special_notes=poop_data.get('special_notes', []),
                size=poop_data.get('size'),
                notes=poop_data.get('notes')
            )
            
            # Enum을 문자열로 변환
            poop_log_dict = asdict(new_poop_log)
            poop_log_dict['shape'] = new_poop_log.shape.value
            poop_log_dict['color'] = new_poop_log.color.value
            
            # Firestore 업데이트
            doc_ref.update({
                'poop_logs': firestore.ArrayUnion([
                    self._convert_date_for_firestore(poop_log_dict)
                ])
            })
            
            logger.info(f"배변 로그 추가 완료: {new_poop_log.log_id}")
            return new_poop_log.log_id
            
        except Exception as e:
            logger.error(f"배변 로그 추가 실패: {e}")
            raise
    
    # 구토 로그 관련 메서드
    def add_vomit_log(self, pet_id: str, user_id: str, log_date: date, vomit_data: Dict[str, Any]) -> str:
        """구토 로그를 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            doc_ref = self.care_logs_collection.document(log_id)
            
            # 새 구토 로그 생성
            new_vomit_log = VomitLog(
                log_id=str(uuid.uuid4()),
                vomit_type=VomitType(vomit_data['vomit_type']),
                timestamp=vomit_data['timestamp'],
                date=log_date,
                amount=vomit_data.get('amount'),
                frequency=vomit_data.get('frequency', 1),
                notes=vomit_data.get('notes')
            )
            
            # Enum을 문자열로 변환
            vomit_log_dict = asdict(new_vomit_log)
            vomit_log_dict['vomit_type'] = new_vomit_log.vomit_type.value
            
            # Firestore 업데이트
            doc_ref.update({
                'vomit_logs': firestore.ArrayUnion([
                    self._convert_date_for_firestore(vomit_log_dict)
                ])
            })
            
            logger.info(f"구토 로그 추가 완료: {new_vomit_log.log_id}")
            return new_vomit_log.log_id
            
        except Exception as e:
            logger.error(f"구토 로그 추가 실패: {e}")
            raise
    
    # 범용 로그 삭제 메서드
    def _delete_log_generic(self, pet_id: str, user_id: str, log_date: date, 
                           log_id_to_delete: str, log_type: str) -> bool:
        """범용 로그 삭제 메서드"""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            doc_ref = self.care_logs_collection.document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ValueError("해당 날짜의 로그가 존재하지 않습니다.")
            
            data = doc.to_dict()
            logs_field = f"{log_type}_logs"
            logs = data.get(logs_field, [])
            
            # 해당 로그 제거
            logs = [log for log in logs if log.get('log_id') != log_id_to_delete]
            
            # Firestore 업데이트
            doc_ref.update({
                logs_field: logs,
                'updated_at': DateTimeUtils.now()
            })
            
            # 총합 업데이트
            self._update_total_and_current(doc_ref, {})
            
            logger.info(f"{log_type} 로그 삭제 완료: {log_id_to_delete}")
            return True
            
        except Exception as e:
            logger.error(f"{log_type} 로그 삭제 실패: {e}")
            raise
    
    # 다른 로그 타입들의 삭제 메서드들
    def delete_water_log(self, pet_id: str, user_id: str, log_date: date, water_log_id: str):
        """물 로그를 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, water_log_id, "water")
    
    def delete_activity_log(self, pet_id: str, user_id: str, log_date: date, activity_log_id: str):
        """활동 로그를 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, activity_log_id, "activity")
    
    def delete_weight_log(self, pet_id: str, user_id: str, log_date: date, weight_log_id: str):
        """체중 로그를 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, weight_log_id, "weight")
    
    def delete_poop_log(self, pet_id: str, user_id: str, log_date: date, poop_log_id: str):
        """배변 로그를 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, poop_log_id, "poop")
    
    def delete_vomit_log(self, pet_id: str, user_id: str, log_date: date, vomit_log_id: str):
        """구토 로그를 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, vomit_log_id, "vomit")

    # 로그 조회 메서드
    def get_logs_by_type(self, pet_id: str, user_id: str, log_date: date, 
                        log_type: str) -> List[Dict[str, Any]]:
        """특정 날짜의 특정 타입 로그들을 조회합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            doc_ref = self.care_logs_collection.document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return []
            
            data = doc.to_dict()
            logs = data.get(f"{log_type}_logs", [])
            
            # datetime 변환
            logs = [self._convert_firestore_data(log) for log in logs]
            
            return logs
            
        except Exception as e:
            logger.error(f"로그 조회 실패 ({pet_id}, {log_type}): {e}")
            raise
