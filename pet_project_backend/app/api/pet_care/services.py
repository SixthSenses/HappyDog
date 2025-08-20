# app/api/pet_care/services.py
import uuid
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
from firebase_admin import firestore
from dateutil.relativedelta import relativedelta

from app.models.pet import Pet, PetGender, ActivityLevel, DietType
from app.models.pet_care_log import (
    PetCareLog, PetCareLogSummary, FoodLog, WaterLog, PoopLog, 
    ActivityLog, VomitLog, WeightLog, MedicationLog, SymptomsLog
)
from app.api.breeds.services import BreedService

logger = logging.getLogger(__name__)

class PetCareService:
    """
    통합된 펫케어 관련 비즈니스 로직을 처리하는 서비스 클래스
    """
    
    def __init__(self, breed_service: Optional[BreedService] = None):
        self.db = firestore.client()
        self.pets_collection = self.db.collection('pets')
        self.care_logs_collection = self.db.collection('pet_care_logs')
        self.breed_service = breed_service or BreedService()
    
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
            doc_ref.set(asdict(new_log))
            logger.info(f"새 일일 로그 문서 생성: {log_id}")
        
        return log_id
    
    def _find_log_in_array(self, logs_array: List[Dict], log_id: str) -> Optional[Dict]:
        """배열에서 특정 log_id를 가진 로그를 찾습니다."""
        for log in logs_array:
            if log.get('log_id') == log_id:
                return log
        return None
    
    def _remove_log_from_array(self, logs_array: List[Dict], log_id: str) -> List[Dict]:
        """배열에서 특정 log_id를 가진 로그를 제거합니다."""
        return [log for log in logs_array if log.get('log_id') != log_id]
    
    def _calculate_totals_from_logs(self, care_log_data: Dict[str, Any]) -> Dict[str, float]:
        """로그 데이터로부터 총량을 계산합니다."""
        total_calories = sum(log.get('calories', 0) for log in care_log_data.get('food_logs', []))
        total_water_ml = sum(log.get('amount_ml', 0) for log in care_log_data.get('water_logs', []))
        total_activity_minutes = sum(log.get('duration_minutes', 0) for log in care_log_data.get('activity_logs', []))
        
        # 가장 최근 체중 찾기
        weight_logs = care_log_data.get('weight_logs', [])
        current_weight_kg = None
        if weight_logs:
            latest_weight = max(weight_logs, key=lambda x: x.get('timestamp', datetime.min))
            current_weight_kg = latest_weight.get('weight_kg')
        
        return {
            'total_calories': total_calories,
            'total_water_ml': total_water_ml,
            'total_activity_minutes': total_activity_minutes,
            'current_weight_kg': current_weight_kg
        }
    
    def _recalculate_and_update_totals(self, log_id: str):
        """로그 배열들을 기반으로 총량을 재계산하고 업데이트합니다."""
        try:
            doc_ref = self.care_logs_collection.document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return
            
            care_log_data = doc.to_dict()
            totals = self._calculate_totals_from_logs(care_log_data)
            
            # 총량 필드 업데이트
            update_data = {
                'total_calories': totals['total_calories'],
                'total_water_ml': totals['total_water_ml'],
                'total_activity_minutes': totals['total_activity_minutes'],
                'updated_at': datetime.utcnow()
            }
            
            if totals['current_weight_kg'] is not None:
                update_data['current_weight_kg'] = totals['current_weight_kg']
            
            doc_ref.update(update_data)
            logger.debug(f"총량 재계산 완료: {log_id}")
            
        except Exception as e:
            logger.error(f"총량 재계산 실패 ({log_id}): {e}")
    
    def _convert_firestore_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Firestore 데이터를 Python 객체로 변환합니다."""
        # 복잡한 변환 로직 구현 (datetime, date 등)
        # 현재는 기본 구현만 제공
        return data
    
    def _get_logs_in_date_range(self, pet_id: str, start_date: date, end_date: date) -> List[PetCareLog]:
        """날짜 범위 내의 로그들을 조회합니다."""
        try:
            logs = []
            current_date = start_date
            
            while current_date <= end_date:
                log_id = f"{pet_id}_{current_date.strftime('%Y%m%d')}"
                doc_ref = self.care_logs_collection.document(log_id)
                doc = doc_ref.get()
                
                if doc.exists:
                    log_data = self._convert_firestore_data(doc.to_dict())
                    logs.append(PetCareLog(**log_data))
                
                current_date += timedelta(days=1)
            
            return logs
        except Exception as e:
            logger.error(f"날짜 범위 로그 조회 실패 ({pet_id}, {start_date}-{end_date}): {e}")
            return []
    
    # ================== 통합 펫케어 로그 CRUD ==================
    
    def add_care_log(self, pet_id: str, user_id: str, log_data: Dict[str, Any]) -> PetCareLog:
        """
        일일 펫케어 로그를 추가하거나 수정합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            log_data: 로그 데이터
            
        Returns:
            생성/수정된 PetCareLog 객체
        """
        try:
            # 펫 소유권 확인
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_date = log_data['date']
            log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            
            # 기존 로그가 있는지 확인
            existing_log = self.get_daily_log(pet_id, user_id, log_date)
            
            if existing_log:
                # 기존 로그 업데이트
                updated_log = self._update_existing_log(existing_log, log_data)
                doc_ref = self.care_logs_collection.document(log_id)
                doc_ref.set(asdict(updated_log))
                logger.info(f"펫케어 로그 업데이트 완료: {log_id}")
                return updated_log
            else:
                # 새 로그 생성
                new_log = PetCareLog(
                    log_id=log_id,
                    pet_id=pet_id,
                    user_id=user_id,
                    date=log_date,
                    **{k: v for k, v in log_data.items() if k != 'date'}
                )
                new_log.calculate_totals()
                
                doc_ref = self.care_logs_collection.document(log_id)
                doc_ref.set(asdict(new_log))
                logger.info(f"새 펫케어 로그 생성 완료: {log_id}")
                return new_log
                
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"펫케어 로그 추가 실패 ({pet_id}, {log_date}): {e}")
            raise
    
    def get_daily_log(self, pet_id: str, user_id: str, log_date: date) -> Optional[PetCareLog]:
        """
        특정 날짜의 펫케어 로그를 조회합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            log_date: 조회할 날짜
            
        Returns:
            PetCareLog 객체 또는 None
        """
        try:
            # 펫 소유권 확인
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            doc_ref = self.care_logs_collection.document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            log_data = doc.to_dict()
            # datetime 필드들을 적절히 변환
            log_data = self._convert_firestore_data(log_data)
            
            logger.info(f"일일 펫케어 로그 조회 완료: {log_id}")
            return PetCareLog(**log_data)
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"일일 펫케어 로그 조회 실패 ({pet_id}, {log_date}): {e}")
            raise
    
    def get_monthly_summary(self, pet_id: str, user_id: str, year: int, month: int) -> Dict[str, Any]:
        """
        월별 펫케어 로그 요약을 조회합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            year: 년도
            month: 월
            
        Returns:
            월별 요약 딕셔너리
        """
        try:
            # 펫 소유권 확인
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 해당 월의 첫째 날과 마지막 날 계산
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            # 해당 월의 모든 로그 조회
            logs = self._get_logs_in_date_range(pet_id, start_date, end_date)
            
            # 요약 데이터 생성
            summary = self._generate_monthly_summary(pet_id, user_id, year, month, logs)
            
            logger.info(f"월별 요약 조회 완료: {pet_id} {year}-{month:02d}")
            return summary
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"월별 요약 조회 실패 ({pet_id}, {year}-{month}): {e}")
            raise
    
    def get_graph_data(self, pet_id: str, user_id: str, metric: str, period: str) -> Dict[str, Any]:
        """
        그래프 데이터를 조회합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            metric: 지표 (weight, calories, water, activity)
            period: 기간 (weekly, monthly, yearly)
            
        Returns:
            그래프 데이터 딕셔너리
        """
        try:
            # 펫 소유권 확인
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 기간에 따른 날짜 범위 계산
            end_date = date.today()
            if period == 'weekly':
                start_date = end_date - timedelta(weeks=4)  # 4주
            elif period == 'monthly':
                start_date = end_date - relativedelta(months=6)  # 6개월
            elif period == 'yearly':
                start_date = end_date - relativedelta(years=2)  # 2년
            else:
                raise ValueError(f"지원하지 않는 기간입니다: {period}")
            
            # 해당 기간의 로그 조회
            logs = self._get_logs_in_date_range(pet_id, start_date, end_date)
            
            # 그래프 데이터 생성
            graph_data = self._generate_graph_data(logs, metric, period)
            
            logger.info(f"그래프 데이터 조회 완료: {pet_id} {metric} {period}")
            return graph_data
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"그래프 데이터 조회 실패 ({pet_id}, {metric}, {period}): {e}")
            raise
    
    # ================== 개별 로그 타입 CRUD 메서드들 ==================
    
    def add_food_log(self, pet_id: str, user_id: str, log_date: date, food_data: Dict[str, Any]) -> FoodLog:
        """음식 기록을 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            
            food_log = FoodLog(
                calories=food_data['calories'],
                timestamp=datetime.fromisoformat(food_data['timestamp'].replace('Z', '+00:00')),
                food_type=food_data['food_type'],
                food_name=food_data.get('food_name'),
                amount_g=food_data.get('amount_g'),
                notes=food_data.get('notes')
            )
            
            doc_ref = self.care_logs_collection.document(log_id)
            doc_ref.update({
                'food_logs': firestore.ArrayUnion([asdict(food_log)]),
                'updated_at': datetime.utcnow()
            })
            
            self._recalculate_and_update_totals(log_id)
            logger.info(f"음식 기록 추가 완료: {pet_id} - {food_log.log_id}")
            return food_log
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"음식 기록 추가 실패 ({pet_id}, {log_date}): {e}")
            raise
    
    def update_food_log(self, pet_id: str, user_id: str, log_date: date, 
                       food_log_id: str, update_data: Dict[str, Any]) -> Optional[FoodLog]:
        """음식 기록을 수정합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            doc_ref = self.care_logs_collection.document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ValueError("해당 날짜의 기록을 찾을 수 없습니다.")
            
            care_log_data = doc.to_dict()
            food_logs = care_log_data.get('food_logs', [])
            
            target_log = self._find_log_in_array(food_logs, food_log_id)
            if not target_log:
                raise ValueError("수정할 음식 기록을 찾을 수 없습니다.")
            
            updated_logs = self._remove_log_from_array(food_logs, food_log_id)
            target_log.update(update_data)
            target_log['timestamp'] = datetime.fromisoformat(target_log['timestamp'].replace('Z', '+00:00')) if isinstance(target_log['timestamp'], str) else target_log['timestamp']
            updated_logs.append(target_log)
            
            doc_ref.update({
                'food_logs': updated_logs,
                'updated_at': datetime.utcnow()
            })
            
            self._recalculate_and_update_totals(log_id)
            updated_food_log = FoodLog(**target_log)
            logger.info(f"음식 기록 수정 완료: {pet_id} - {food_log_id}")
            return updated_food_log
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"음식 기록 수정 실패 ({pet_id}, {food_log_id}): {e}")
            raise
    
    def delete_food_log(self, pet_id: str, user_id: str, log_date: date, food_log_id: str) -> bool:
        """음식 기록을 삭제합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            doc_ref = self.care_logs_collection.document(log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ValueError("해당 날짜의 기록을 찾을 수 없습니다.")
            
            care_log_data = doc.to_dict()
            food_logs = care_log_data.get('food_logs', [])
            
            target_log = self._find_log_in_array(food_logs, food_log_id)
            if not target_log:
                raise ValueError("삭제할 음식 기록을 찾을 수 없습니다.")
            
            updated_logs = self._remove_log_from_array(food_logs, food_log_id)
            
            doc_ref.update({
                'food_logs': updated_logs,
                'updated_at': datetime.utcnow()
            })
            
            self._recalculate_and_update_totals(log_id)
            logger.info(f"음식 기록 삭제 완료: {pet_id} - {food_log_id}")
            return True
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"음식 기록 삭제 실패 ({pet_id}, {food_log_id}): {e}")
            raise
    
    def add_water_log(self, pet_id: str, user_id: str, log_date: date, water_data: Dict[str, Any]) -> WaterLog:
        """물 섭취 기록을 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            
            water_log = WaterLog(
                amount_ml=water_data['amount_ml'],
                timestamp=datetime.fromisoformat(water_data['timestamp'].replace('Z', '+00:00')),
                notes=water_data.get('notes')
            )
            
            doc_ref = self.care_logs_collection.document(log_id)
            doc_ref.update({
                'water_logs': firestore.ArrayUnion([asdict(water_log)]),
                'updated_at': datetime.utcnow()
            })
            
            self._recalculate_and_update_totals(log_id)
            logger.info(f"물 섭취 기록 추가 완료: {pet_id} - {water_log.log_id}")
            return water_log
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"물 섭취 기록 추가 실패 ({pet_id}, {log_date}): {e}")
            raise
    
    def update_water_log(self, pet_id: str, user_id: str, log_date: date, 
                        water_log_id: str, update_data: Dict[str, Any]) -> Optional[WaterLog]:
        """물 섭취 기록을 수정합니다."""
        return self._update_log_generic(pet_id, user_id, log_date, water_log_id, update_data, 'water_logs', WaterLog)
    
    def delete_water_log(self, pet_id: str, user_id: str, log_date: date, water_log_id: str) -> bool:
        """물 섭취 기록을 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, water_log_id, 'water_logs')
    
    def add_poop_log(self, pet_id: str, user_id: str, log_date: date, poop_data: Dict[str, Any]) -> PoopLog:
        """배변 기록을 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            
            poop_log = PoopLog(
                shape=poop_data['shape'],
                color=poop_data['color'],
                timestamp=datetime.fromisoformat(poop_data['timestamp'].replace('Z', '+00:00')),
                special_notes=poop_data.get('special_notes', []),
                size=poop_data.get('size'),
                notes=poop_data.get('notes')
            )
            
            doc_ref = self.care_logs_collection.document(log_id)
            doc_ref.update({
                'poop_logs': firestore.ArrayUnion([asdict(poop_log)]),
                'updated_at': datetime.utcnow()
            })
            
            logger.info(f"배변 기록 추가 완료: {pet_id} - {poop_log.log_id}")
            return poop_log
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"배변 기록 추가 실패 ({pet_id}, {log_date}): {e}")
            raise
    
    def update_poop_log(self, pet_id: str, user_id: str, log_date: date, 
                       poop_log_id: str, update_data: Dict[str, Any]) -> Optional[PoopLog]:
        """배변 기록을 수정합니다."""
        return self._update_log_generic(pet_id, user_id, log_date, poop_log_id, update_data, 'poop_logs', PoopLog)
    
    def delete_poop_log(self, pet_id: str, user_id: str, log_date: date, poop_log_id: str) -> bool:
        """배변 기록을 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, poop_log_id, 'poop_logs')
    
    def add_activity_log(self, pet_id: str, user_id: str, log_date: date, activity_data: Dict[str, Any]) -> ActivityLog:
        """활동 기록을 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            
            activity_log = ActivityLog(
                duration_minutes=activity_data['duration_minutes'],
                activity_type=activity_data['activity_type'],
                intensity=activity_data['intensity'],
                timestamp=datetime.fromisoformat(activity_data['timestamp'].replace('Z', '+00:00')),
                distance_km=activity_data.get('distance_km'),
                calories_burned=activity_data.get('calories_burned'),
                notes=activity_data.get('notes')
            )
            
            doc_ref = self.care_logs_collection.document(log_id)
            doc_ref.update({
                'activity_logs': firestore.ArrayUnion([asdict(activity_log)]),
                'updated_at': datetime.utcnow()
            })
            
            self._recalculate_and_update_totals(log_id)
            logger.info(f"활동 기록 추가 완료: {pet_id} - {activity_log.log_id}")
            return activity_log
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"활동 기록 추가 실패 ({pet_id}, {log_date}): {e}")
            raise
    
    def update_activity_log(self, pet_id: str, user_id: str, log_date: date, 
                           activity_log_id: str, update_data: Dict[str, Any]) -> Optional[ActivityLog]:
        """활동 기록을 수정합니다."""
        return self._update_log_generic(pet_id, user_id, log_date, activity_log_id, update_data, 'activity_logs', ActivityLog)
    
    def delete_activity_log(self, pet_id: str, user_id: str, log_date: date, activity_log_id: str) -> bool:
        """활동 기록을 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, activity_log_id, 'activity_logs')
    
    def add_weight_log(self, pet_id: str, user_id: str, log_date: date, weight_data: Dict[str, Any]) -> WeightLog:
        """체중 기록을 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            
            weight_log = WeightLog(
                weight_kg=weight_data['weight_kg'],
                timestamp=datetime.fromisoformat(weight_data['timestamp'].replace('Z', '+00:00')),
                bcs_level=weight_data.get('bcs_level'),
                measurement_method=weight_data.get('measurement_method'),
                notes=weight_data.get('notes')
            )
            
            doc_ref = self.care_logs_collection.document(log_id)
            doc_ref.update({
                'weight_logs': firestore.ArrayUnion([asdict(weight_log)]),
                'updated_at': datetime.utcnow()
            })
            
            self._recalculate_and_update_totals(log_id)
            logger.info(f"체중 기록 추가 완료: {pet_id} - {weight_log.log_id}")
            return weight_log
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"체중 기록 추가 실패 ({pet_id}, {log_date}): {e}")
            raise
    
    def update_weight_log(self, pet_id: str, user_id: str, log_date: date, 
                         weight_log_id: str, update_data: Dict[str, Any]) -> Optional[WeightLog]:
        """체중 기록을 수정합니다."""
        return self._update_log_generic(pet_id, user_id, log_date, weight_log_id, update_data, 'weight_logs', WeightLog)
    
    def delete_weight_log(self, pet_id: str, user_id: str, log_date: date, weight_log_id: str) -> bool:
        """체중 기록을 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, weight_log_id, 'weight_logs')
    
    def add_vomit_log(self, pet_id: str, user_id: str, log_date: date, vomit_data: Dict[str, Any]) -> VomitLog:
        """구토 기록을 추가합니다."""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            
            vomit_log = VomitLog(
                vomit_type=vomit_data['vomit_type'],
                timestamp=datetime.fromisoformat(vomit_data['timestamp'].replace('Z', '+00:00')),
                amount=vomit_data.get('amount'),
                frequency=vomit_data.get('frequency', 1),
                notes=vomit_data.get('notes')
            )
            
            doc_ref = self.care_logs_collection.document(log_id)
            doc_ref.update({
                'vomit_logs': firestore.ArrayUnion([asdict(vomit_log)]),
                'updated_at': datetime.utcnow()
            })
            
            logger.info(f"구토 기록 추가 완료: {pet_id} - {vomit_log.log_id}")
            return vomit_log
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"구토 기록 추가 실패 ({pet_id}, {log_date}): {e}")
            raise
    
    def update_vomit_log(self, pet_id: str, user_id: str, log_date: date, 
                        vomit_log_id: str, update_data: Dict[str, Any]) -> Optional[VomitLog]:
        """구토 기록을 수정합니다."""
        return self._update_log_generic(pet_id, user_id, log_date, vomit_log_id, update_data, 'vomit_logs', VomitLog)
    
    def delete_vomit_log(self, pet_id: str, user_id: str, log_date: date, vomit_log_id: str) -> bool:
        """구토 기록을 삭제합니다."""
        return self._delete_log_generic(pet_id, user_id, log_date, vomit_log_id, 'vomit_logs')
    
    # ================== 제네릭 CRUD 헬퍼 메서드들 ==================
    
    def _update_log_generic(self, pet_id: str, user_id: str, log_date: date, 
                           log_id: str, update_data: Dict[str, Any], field_name: str, log_class) -> Optional[Any]:
        """제네릭 로그 수정 메서드"""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            daily_log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            doc_ref = self.care_logs_collection.document(daily_log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ValueError("해당 날짜의 기록을 찾을 수 없습니다.")
            
            care_log_data = doc.to_dict()
            logs = care_log_data.get(field_name, [])
            
            target_log = self._find_log_in_array(logs, log_id)
            if not target_log:
                raise ValueError(f"수정할 {field_name} 기록을 찾을 수 없습니다.")
            
            updated_logs = self._remove_log_from_array(logs, log_id)
            target_log.update(update_data)
            
            # timestamp 필드 처리
            if 'timestamp' in target_log:
                target_log['timestamp'] = datetime.fromisoformat(target_log['timestamp'].replace('Z', '+00:00')) if isinstance(target_log['timestamp'], str) else target_log['timestamp']
            
            updated_logs.append(target_log)
            
            doc_ref.update({
                field_name: updated_logs,
                'updated_at': datetime.utcnow()
            })
            
            # 필요한 경우 총량 재계산
            if field_name in ['food_logs', 'water_logs', 'activity_logs', 'weight_logs']:
                self._recalculate_and_update_totals(daily_log_id)
            
            updated_log = log_class(**target_log)
            logger.info(f"{field_name} 수정 완료: {pet_id} - {log_id}")
            return updated_log
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"{field_name} 수정 실패 ({pet_id}, {log_id}): {e}")
            raise
    
    def _delete_log_generic(self, pet_id: str, user_id: str, log_date: date, 
                           log_id: str, field_name: str) -> bool:
        """제네릭 로그 삭제 메서드"""
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            daily_log_id = f"{pet_id}_{log_date.strftime('%Y%m%d')}"
            doc_ref = self.care_logs_collection.document(daily_log_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                raise ValueError("해당 날짜의 기록을 찾을 수 없습니다.")
            
            care_log_data = doc.to_dict()
            logs = care_log_data.get(field_name, [])
            
            target_log = self._find_log_in_array(logs, log_id)
            if not target_log:
                raise ValueError(f"삭제할 {field_name} 기록을 찾을 수 없습니다.")
            
            updated_logs = self._remove_log_from_array(logs, log_id)
            
            doc_ref.update({
                field_name: updated_logs,
                'updated_at': datetime.utcnow()
            })
            
            # 필요한 경우 총량 재계산
            if field_name in ['food_logs', 'water_logs', 'activity_logs', 'weight_logs']:
                self._recalculate_and_update_totals(daily_log_id)
            
            logger.info(f"{field_name} 삭제 완료: {pet_id} - {log_id}")
            return True
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"{field_name} 삭제 실패 ({pet_id}, {log_id}): {e}")
            raise
    
    # ================== 빠른 증감 기능 ==================
    
    def quick_add_total(self, pet_id: str, user_id: str, log_date: date, 
                       log_type: str, amount: float) -> Dict[str, Any]:
        """
        빠른 증감 기능: 총량 필드를 직접 증감합니다.
        
        Args:
            log_type: 'calories', 'water', 'activity'
            amount: 증감할 양 (음수도 가능)
        """
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            doc_ref = self.care_logs_collection.document(log_id)
            
            # 현재 값 조회
            doc = doc_ref.get()
            current_data = doc.to_dict()
            
            if log_type == 'calories':
                field = 'total_calories'
                current_value = current_data.get(field, 0.0)
                new_value = max(0, current_value + amount)  # 음수 방지
            elif log_type == 'water':
                field = 'total_water_ml'
                current_value = current_data.get(field, 0.0)
                new_value = max(0, current_value + amount)  # 음수 방지
            elif log_type == 'activity':
                field = 'total_activity_minutes'
                current_value = current_data.get(field, 0)
                new_value = max(0, int(current_value + amount))  # 음수 방지
            else:
                raise ValueError(f"지원하지 않는 로그 타입: {log_type}")
            
            # Firestore 업데이트
            doc_ref.update({
                field: new_value,
                'updated_at': datetime.utcnow()
            })
            
            logger.info(f"빠른 증감 완료: {pet_id} - {log_type}: {current_value} -> {new_value}")
            return {
                'log_type': log_type,
                'previous_value': current_value,
                'new_value': new_value,
                'change': amount
            }
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"빠른 증감 실패 ({pet_id}, {log_type}): {e}")
            raise
    
    # ================== 권장량 계산 ==================
    
    def calculate_recommendations(self, pet_id: str) -> Dict[str, Any]:
        """
        반려동물의 권장 칼로리 및 음수량을 계산합니다.
        
        Args:
            pet_id: 반려동물 ID
            
        Returns:
            권장량 계산 결과 딕셔너리
        """
        try:
            # 펫 정보 조회
            pet_doc = self.pets_collection.document(pet_id).get()
            if not pet_doc.exists:
                raise ValueError(f"펫을 찾을 수 없습니다: {pet_id}")
            
            pet_data = pet_doc.to_dict()
            
            # 나이 계산 (월 단위)
            birthdate = pet_data['birthdate']
            if isinstance(birthdate, str):
                birthdate = datetime.strptime(birthdate, '%Y-%m-%d').date()
            
            age_months = self._calculate_age_months(birthdate)
            
            # 품종별 이상 체중 조회
            breed_name = pet_data['breed']
            gender = pet_data['gender']
            ideal_weight = self.breed_service.get_breed_ideal_weight(breed_name, gender)
            
            if not ideal_weight:
                raise ValueError(f"품종 '{breed_name}'의 이상 체중 정보를 찾을 수 없습니다.")
            
            # RER 계산 (휴식대사율)
            rer_calories = 70 * (ideal_weight ** 0.75)
            
            # 승수 선택 및 MER 계산
            multiplier, multiplier_reason = self._select_mer_multiplier(pet_data, age_months)
            mer_calories = rer_calories * multiplier
            
            # 권장 음수량 계산
            recommended_water_ml = self._calculate_water_intake(mer_calories, pet_data.get('diet_type'))
            
            # 체중 상태 평가
            current_weight = pet_data.get('current_weight')
            weight_status = self._evaluate_weight_status(current_weight, ideal_weight)
            
            # 추가 권장사항 생성
            recommendations = self._generate_recommendations(weight_status, age_months, pet_data)
            
            result = {
                'pet_id': pet_id,
                'current_weight_kg': current_weight,
                'ideal_weight_kg': ideal_weight,
                'age_months': age_months,
                'rer_calories': round(rer_calories, 1),
                'mer_calories': round(mer_calories, 1),
                'recommended_water_ml': round(recommended_water_ml, 1),
                'multiplier_used': multiplier,
                'multiplier_reason': multiplier_reason,
                'weight_status': weight_status,
                'recommendations': recommendations,
                'calculated_at': datetime.utcnow()
            }
            
            logger.info(f"권장량 계산 완료: {pet_id} - MER: {mer_calories}kcal, 물: {recommended_water_ml}ml")
            return result
            
        except Exception as e:
            logger.error(f"권장량 계산 실패 ({pet_id}): {e}")
            raise
    
    # ================== 헬퍼 메서드들 ==================
    
    def _update_existing_log(self, existing_log: PetCareLog, new_data: Dict[str, Any]) -> PetCareLog:
        """기존 로그를 새 데이터로 업데이트합니다."""
        # 기존 로그의 데이터를 새 데이터로 병합
        for field, value in new_data.items():
            if field != 'date' and hasattr(existing_log, field):
                if isinstance(value, list):
                    # 리스트 필드는 기존 데이터에 추가
                    existing_list = getattr(existing_log, field, [])
                    existing_list.extend(value)
                    setattr(existing_log, field, existing_list)
                else:
                    setattr(existing_log, field, value)
        
        # 총합 재계산
        existing_log.calculate_totals()
        return existing_log
    
    def _generate_monthly_summary(self, pet_id: str, user_id: str, year: int, month: int, 
                                 logs: List[PetCareLog]) -> Dict[str, Any]:
        """월별 요약 데이터를 생성합니다."""
        daily_records = {}
        total_calories = 0
        total_water = 0
        total_activity = 0
        logged_days = 0
        
        for log in logs:
            date_str = log.date.strftime('%Y-%m-%d')
            record_types = []
            
            if log.food_logs:
                record_types.append('food')
                total_calories += log.total_calories
            if log.water_logs:
                record_types.append('water')
                total_water += log.total_water_ml
            if log.poop_logs:
                record_types.append('poop')
            if log.activity_logs:
                record_types.append('activity')
                total_activity += log.total_activity_minutes
            if log.vomit_logs:
                record_types.append('vomit')
            if log.weight_logs:
                record_types.append('weight')
            if log.medication_logs:
                record_types.append('medication')
            if log.symptoms_logs:
                record_types.append('symptoms')
            
            if record_types:
                daily_records[date_str] = record_types
                logged_days += 1
        
        return {
            'month': f"{year}-{month:02d}",
            'pet_id': pet_id,
            'user_id': user_id,
            'daily_records': daily_records,
            'total_logged_days': logged_days,
            'avg_calories_per_day': round(total_calories / max(logged_days, 1), 1),
            'avg_water_ml_per_day': round(total_water / max(logged_days, 1), 1),
            'avg_activity_minutes_per_day': round(total_activity / max(logged_days, 1))
        }
    
    def _generate_graph_data(self, logs: List[PetCareLog], metric: str, period: str) -> Dict[str, Any]:
        """그래프 데이터를 생성합니다."""
        data_points = []
        values = []
        
        for log in logs:
            if metric == 'weight' and log.current_weight_kg:
                value = log.current_weight_kg
            elif metric == 'calories':
                value = log.total_calories
            elif metric == 'water':
                value = log.total_water_ml
            elif metric == 'activity':
                value = log.total_activity_minutes
            else:
                continue
            
            data_points.append({
                'date': log.date,
                'value': value
            })
            values.append(value)
        
        # 통계 계산
        if values:
            min_value = min(values)
            max_value = max(values)
            avg_value = sum(values) / len(values)
            
            # 트렌드 계산 (간단한 선형 회귀)
            if len(values) >= 2:
                first_half = values[:len(values)//2]
                second_half = values[len(values)//2:]
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                
                if second_avg > first_avg * 1.05:
                    trend = 'increasing'
                elif second_avg < first_avg * 0.95:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            else:
                trend = 'stable'
        else:
            min_value = max_value = avg_value = 0
            trend = 'stable'
        
        return {
            'metric': metric,
            'period': period,
            'data_points': data_points,
            'min_value': round(min_value, 1),
            'max_value': round(max_value, 1),
            'avg_value': round(avg_value, 1),
            'trend': trend
        }
    
    def _calculate_age_months(self, birthdate: date) -> int:
        """나이를 월 단위로 계산합니다."""
        today = date.today()
        age_months = (today.year - birthdate.year) * 12 + (today.month - birthdate.month)
        return max(0, age_months)
    
    def _select_mer_multiplier(self, pet_data: Dict[str, Any], age_months: int) -> Tuple[float, str]:
        """MER 승수를 선택합니다."""
        # 생애 주기 확인
        if age_months < 4:
            return 3.0, "자견 (4개월 미만)"
        elif age_months < 12:
            return 2.0, "자견 (4개월 이상)"
        
        # 성견의 경우
        is_neutered = pet_data.get('is_neutered')
        activity_level = pet_data.get('activity_level')
        
        # 중성화 상태에 따른 기본 승수
        if is_neutered is True:
            base_multiplier = 1.6
            base_reason = "중성화한 성견"
        elif is_neutered is False:
            base_multiplier = 1.8
            base_reason = "중성화하지 않은 성견"
        else:
            base_multiplier = 1.6  # 기본값
            base_reason = "성견 (중성화 여부 불명)"
        
        # 활동 수준에 따른 조정
        if activity_level:
            if activity_level == ActivityLevel.INACTIVE.value:
                return 1.4, "비활동적 / 비만 경향"
            elif activity_level == ActivityLevel.LIGHT.value:
                return 2.0, "가벼운 활동"
            elif activity_level == ActivityLevel.MODERATE.value:
                return 3.0, "중간 수준 활동"
            elif activity_level in [ActivityLevel.ACTIVE.value, ActivityLevel.VERY_ACTIVE.value]:
                return 6.0, "격렬한 활동 (워킹독)"
        
        return base_multiplier, base_reason
    
    def _calculate_water_intake(self, mer_calories: float, diet_type: Optional[str]) -> float:
        """권장 음수량을 계산합니다."""
        base_water_ml = mer_calories
        
        # 식단 타입에 따른 조정
        if diet_type == DietType.WET_FOOD.value:
            # 습식사료는 수분 함량이 높으므로 권장량의 40% 정도로 조정
            return base_water_ml * 0.4
        elif diet_type == DietType.MIXED.value:
            # 혼합식은 70% 정도로 조정
            return base_water_ml * 0.7
        else:
            # 건사료 또는 기타
            return base_water_ml
    
    def _evaluate_weight_status(self, current_weight: Optional[float], ideal_weight: float) -> str:
        """체중 상태를 평가합니다."""
        if not current_weight:
            return "unknown"
        
        ratio = current_weight / ideal_weight
        
        if ratio < 0.85:
            return "underweight"
        elif ratio <= 1.15:
            return "normal"
        elif ratio <= 1.3:
            return "overweight"
        else:
            return "obese"
    
    def _generate_recommendations(self, weight_status: str, age_months: int, pet_data: Dict[str, Any]) -> List[str]:
        """추가 권장사항을 생성합니다."""
        recommendations = []
        
        # 체중 상태별 권장사항
        if weight_status == "underweight":
            recommendations.append("체중 증가를 위해 고칼로리 사료를 고려해보세요.")
            recommendations.append("수의사와 상담하여 건강 상태를 확인해보세요.")
        elif weight_status == "overweight":
            recommendations.append("체중 감량을 위해 칼로리를 줄이고 운동량을 늘려보세요.")
            recommendations.append("간식량을 줄이고 저칼로리 사료로 바꾸는 것을 고려해보세요.")
        elif weight_status == "obese":
            recommendations.append("비만 관리를 위해 수의사와 상담하세요.")
            recommendations.append("체중 감량 식단과 운동 계획이 필요합니다.")
        
        # 나이별 권장사항
        if age_months < 6:
            recommendations.append("자견기이므로 성장에 필요한 영양소가 충분한 사료를 급여하세요.")
        elif age_months > 84:  # 7세 이상
            recommendations.append("시니어견이므로 관절 건강과 소화 기능을 고려한 사료를 선택하세요.")
        
        # 활동 수준별 권장사항
        activity_level = pet_data.get('activity_level')
        if activity_level == ActivityLevel.INACTIVE.value:
            recommendations.append("운동량을 늘려 건강한 체중을 유지하세요.")
        elif activity_level in [ActivityLevel.ACTIVE.value, ActivityLevel.VERY_ACTIVE.value]:
            recommendations.append("활동량이 많으므로 충분한 칼로리와 수분 섭취가 중요합니다.")
        
        return recommendations