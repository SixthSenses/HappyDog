# app/api/pet_care/services.py
"""
통합 펫케어 서비스 클래스
기존 호환성을 유지하면서 새로운 구조로 마이그레이션
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import date

from app.utils.datetime_utils import DateTimeUtils
from .services_new import (
    DailyLogService,
    IndividualLogService,
    AnalyticsService,
    RecommendationService
)

logger = logging.getLogger(__name__)


class PetCareService:
    """
    통합된 펫케어 서비스 클래스
    기존 API와의 호환성을 유지하면서 새로운 서비스 구조를 사용
    """
    
    def __init__(self, breed_service=None):
        # 서비스 인스턴스 생성
        self.daily_log_service = DailyLogService(breed_service)
        self.individual_log_service = IndividualLogService(breed_service)
        self.analytics_service = AnalyticsService(breed_service)
        self.recommendation_service = RecommendationService(breed_service)
        
        # 기본 서비스 메서드 위임
        self._verify_pet_ownership = self.daily_log_service._verify_pet_ownership
        self._get_or_create_daily_log = self.daily_log_service._get_or_create_daily_log
    
    # ========== 일일 로그 관련 메서드 ==========
    def add_care_log(self, pet_id: str, user_id: str, log_data: Dict[str, Any]):
        """일일 펫케어 로그를 생성하거나 업데이트합니다."""
        return self.daily_log_service.create_or_update_daily_log(pet_id, user_id, log_data)
    
    def get_daily_log(self, pet_id: str, user_id: str, log_date: date):
        """특정 날짜의 펫케어 로그를 조회합니다."""
        return self.daily_log_service.get_daily_log(pet_id, user_id, log_date)
    
    def get_monthly_summary(self, pet_id: str, user_id: str, month: str):
        """월별 펫케어 로그 요약을 조회합니다."""
        # month 형식: "2025-01"
        year, month_num = month.split('-')
        return self.daily_log_service.get_monthly_summary(
            pet_id, user_id, int(year), int(month_num)
        )
    
    # ========== 개별 로그 관련 메서드 ==========
    # 음식 로그
    def add_food_log(self, pet_id: str, user_id: str, log_date: date, food_data: Dict[str, Any]):
        """음식 섭취 로그를 추가합니다."""
        return self.individual_log_service.add_food_log(pet_id, user_id, log_date, food_data)
    
    def update_food_log(self, pet_id: str, user_id: str, log_date: date, 
                       food_log_id: str, update_data: Dict[str, Any]):
        """음식 로그를 수정합니다."""
        return self.individual_log_service.update_food_log(
            pet_id, user_id, log_date, food_log_id, update_data
        )
    
    def delete_food_log(self, pet_id: str, user_id: str, log_date: date, food_log_id: str):
        """음식 로그를 삭제합니다."""
        return self.individual_log_service.delete_food_log(
            pet_id, user_id, log_date, food_log_id
        )
    
    # 물 로그
    def add_water_log(self, pet_id: str, user_id: str, log_date: date, water_data: Dict[str, Any]):
        """물 섭취 로그를 추가합니다."""
        return self.individual_log_service.add_water_log(pet_id, user_id, log_date, water_data)
    
    def update_water_log(self, pet_id: str, user_id: str, log_date: date,
                        water_log_id: str, update_data: Dict[str, Any]):
        """물 로그를 수정합니다."""
        # 간단한 구현 - 삭제 후 재추가
        self.delete_water_log(pet_id, user_id, log_date, water_log_id)
        return self.add_water_log(pet_id, user_id, log_date, update_data)
    
    def delete_water_log(self, pet_id: str, user_id: str, log_date: date, water_log_id: str):
        """물 로그를 삭제합니다."""
        return self.individual_log_service.delete_water_log(pet_id, user_id, log_date, water_log_id)
    
    # 활동 로그
    def add_activity_log(self, pet_id: str, user_id: str, log_date: date, activity_data: Dict[str, Any]):
        """활동 로그를 추가합니다."""
        return self.individual_log_service.add_activity_log(pet_id, user_id, log_date, activity_data)
    
    def update_activity_log(self, pet_id: str, user_id: str, log_date: date,
                           activity_log_id: str, update_data: Dict[str, Any]):
        """활동 로그를 수정합니다."""
        # 간단한 구현 - 삭제 후 재추가
        self.delete_activity_log(pet_id, user_id, log_date, activity_log_id)
        return self.add_activity_log(pet_id, user_id, log_date, update_data)
    
    def delete_activity_log(self, pet_id: str, user_id: str, log_date: date, activity_log_id: str):
        """활동 로그를 삭제합니다."""
        return self.individual_log_service.delete_activity_log(pet_id, user_id, log_date, activity_log_id)
    
    # 체중 로그
    def add_weight_log(self, pet_id: str, user_id: str, log_date: date, weight_data: Dict[str, Any]):
        """체중 로그를 추가합니다."""
        return self.individual_log_service.add_weight_log(pet_id, user_id, log_date, weight_data)
    
    def update_weight_log(self, pet_id: str, user_id: str, log_date: date,
                         weight_log_id: str, update_data: Dict[str, Any]):
        """체중 로그를 수정합니다."""
        # 간단한 구현 - 삭제 후 재추가
        self.delete_weight_log(pet_id, user_id, log_date, weight_log_id)
        return self.add_weight_log(pet_id, user_id, log_date, update_data)
    
    def delete_weight_log(self, pet_id: str, user_id: str, log_date: date, weight_log_id: str):
        """체중 로그를 삭제합니다."""
        return self.individual_log_service.delete_weight_log(pet_id, user_id, log_date, weight_log_id)
    
    # 배변 로그
    def add_poop_log(self, pet_id: str, user_id: str, log_date: date, poop_data: Dict[str, Any]):
        """배변 로그를 추가합니다."""
        return self.individual_log_service.add_poop_log(pet_id, user_id, log_date, poop_data)
    
    def update_poop_log(self, pet_id: str, user_id: str, log_date: date,
                       poop_log_id: str, update_data: Dict[str, Any]):
        """배변 로그를 수정합니다."""
        # 간단한 구현 - 삭제 후 재추가
        self.delete_poop_log(pet_id, user_id, log_date, poop_log_id)
        return self.add_poop_log(pet_id, user_id, log_date, update_data)
    
    def delete_poop_log(self, pet_id: str, user_id: str, log_date: date, poop_log_id: str):
        """배변 로그를 삭제합니다."""
        return self.individual_log_service.delete_poop_log(pet_id, user_id, log_date, poop_log_id)
    
    # 구토 로그
    def add_vomit_log(self, pet_id: str, user_id: str, log_date: date, vomit_data: Dict[str, Any]):
        """구토 로그를 추가합니다."""
        return self.individual_log_service.add_vomit_log(pet_id, user_id, log_date, vomit_data)
    
    def update_vomit_log(self, pet_id: str, user_id: str, log_date: date,
                        vomit_log_id: str, update_data: Dict[str, Any]):
        """구토 로그를 수정합니다."""
        # 간단한 구현 - 삭제 후 재추가
        self.delete_vomit_log(pet_id, user_id, log_date, vomit_log_id)
        return self.add_vomit_log(pet_id, user_id, log_date, update_data)
    
    def delete_vomit_log(self, pet_id: str, user_id: str, log_date: date, vomit_log_id: str):
        """구토 로그를 삭제합니다."""
        return self.individual_log_service.delete_vomit_log(pet_id, user_id, log_date, vomit_log_id)
    
    # 로그 조회
    def get_logs_by_type(self, pet_id: str, user_id: str, log_date: date, log_type: str):
        """특정 날짜의 특정 타입 로그들을 조회합니다."""
        return self.individual_log_service.get_logs_by_type(
            pet_id, user_id, log_date, log_type
        )
    
    # ========== 분석 관련 메서드 ==========
    def get_graph_data(self, pet_id: str, user_id: str, metric: str, period: str):
        """그래프 데이터를 조회합니다."""
        return self.analytics_service.get_trends(pet_id, user_id, metric, period)
    
    def get_analytics_report(self, pet_id: str, user_id: str, period: str):
        """분석 리포트를 생성합니다."""
        return self.analytics_service.get_report(pet_id, user_id, period)
    
    # ========== 권장량 관련 메서드 ==========
    def get_recommendations(self, pet_id: str, user_id: str):
        """권장량을 조회합니다."""
        return self.recommendation_service.get_recommendations(pet_id, user_id)
    
    def refresh_recommendations(self, pet_id: str, user_id: str):
        """권장량을 갱신합니다."""
        return self.recommendation_service.refresh_recommendations(pet_id, user_id)
    
    def get_care_settings(self, pet_id: str, user_id: str):
        """펫케어 설정을 조회합니다."""
        return self.recommendation_service.get_care_settings(pet_id, user_id)
    
    def update_care_settings(self, pet_id: str, user_id: str, settings: Dict[str, Any]):
        """펫케어 설정을 업데이트합니다."""
        return self.recommendation_service.update_care_settings(pet_id, user_id, settings)
    
    def calculate_recommendations(self, pet_id: str):
        """권장량을 계산합니다."""
        return self.recommendation_service.calculate_recommendations(pet_id)
    
    @property
    def pets_collection(self):
        """pets 컬렉션 참조 (호환성)"""
        return self.individual_log_service.pets_collection
    
    # ========== 빠른 액션 메서드 ==========
    def quick_add_calories(self, pet_id: str, user_id: str, log_date: date, amount: float):
        """빠른 칼로리 추가"""
        food_data = {
            'calories': amount,
            'timestamp': DateTimeUtils.now(),
            'food_type': '간식',  # FoodType.SNACK의 값
            'food_name': '빠른 추가'
        }
        return self.add_food_log(pet_id, user_id, log_date, food_data)
    
    def quick_add_water(self, pet_id: str, user_id: str, log_date: date, amount: float):
        """빠른 물 추가"""
        water_data = {
            'amount_ml': amount,
            'timestamp': DateTimeUtils.now()
        }
        return self.add_water_log(pet_id, user_id, log_date, water_data)
    
    def quick_add_activity(self, pet_id: str, user_id: str, log_date: date, minutes: int):
        """빠른 활동 추가"""
        activity_data = {
            'duration_minutes': minutes,
            'activity_type': '놀이',  # ActivityType.PLAY의 값
            'intensity': '보통',  # ActivityIntensity.MODERATE의 값
            'timestamp': DateTimeUtils.now()
        }
        return self.add_activity_log(pet_id, user_id, log_date, activity_data)
    
    # ========== 빠른 액션 총량 관리 메서드 ==========
    def quick_add_total(self, pet_id: str, user_id: str, log_date: date, metric_type: str, amount: float):
        """빠른 총량 추가 (호환성 메서드)"""
        if metric_type == 'calories':
            return self.quick_add_calories(pet_id, user_id, log_date, amount)
        elif metric_type == 'water':
            return self.quick_add_water(pet_id, user_id, log_date, amount)
        elif metric_type == 'activity':
            return self.quick_add_activity(pet_id, user_id, log_date, int(amount))
        else:
            raise ValueError(f"지원하지 않는 메트릭 타입입니다: {metric_type}")
