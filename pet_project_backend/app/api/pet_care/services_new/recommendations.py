# app/api/pet_care/services_new/recommendations.py
"""
펫케어 권장량 계산 및 관리 서비스
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from .base import BasePetCareService
from app.utils.datetime_utils import DateTimeUtils

logger = logging.getLogger(__name__)


class RecommendationService(BasePetCareService):
    """
    반려동물별 권장량 계산 및 관리를 담당하는 서비스
    """
    
    # 기본 칼로리 계산 상수
    BASE_CALORIE_MULTIPLIERS = {
        'puppy': 3.0,           # 강아지
        'young': 2.0,           # 어린 개 (1-3세)
        'adult': 1.6,           # 성견 (3-7세)
        'senior': 1.4,          # 노견 (7세 이상)
        'pregnant': 2.0,        # 임신견
        'lactating': 3.0        # 수유견
    }
    
    ACTIVITY_MULTIPLIERS = {
        'low': 0.8,             # 활동량 적음
        'moderate': 1.0,        # 보통 활동량
        'high': 1.2,            # 활동량 많음
        'very_high': 1.4        # 매우 활동적
    }
    
    def calculate_recommendations(self, pet_id: str) -> Dict[str, Any]:
        """
        펫의 권장량을 계산합니다 (소유권 검증 없이).
        
        Args:
            pet_id: 반려동물 ID
            
        Returns:
            권장량 정보
        """
        try:
            # 펫 정보 조회
            pet_doc = self.pets_collection.document(pet_id).get()
            if not pet_doc.exists:
                raise ValueError("반려동물을 찾을 수 없습니다.")
            
            pet_data = pet_doc.to_dict()
            
            # 권장량 계산
            recommendations = self._calculate_recommendations(pet_data)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"권장량 계산 실패 ({pet_id}): {e}")
            raise

    def get_recommendations(self, pet_id: str, user_id: str) -> Dict[str, Any]:
        """
        반려동물의 현재 권장량을 조회합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            
        Returns:
            권장량 정보
        """
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 펫 정보 조회
            pet_doc = self.pets_collection.document(pet_id).get()
            if not pet_doc.exists:
                raise ValueError("반려동물을 찾을 수 없습니다.")
            
            pet_data = pet_doc.to_dict()
            
            # 권장량 계산
            recommendations = self._calculate_recommendations(pet_data)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"권장량 조회 실패 ({pet_id}): {e}")
            raise
    
    def refresh_recommendations(self, pet_id: str, user_id: str) -> Dict[str, Any]:
        """
        권장량을 수동으로 갱신합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            
        Returns:
            갱신된 권장량 정보
        """
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 펫 정보 조회
            pet_doc = self.pets_collection.document(pet_id).get()
            if not pet_doc.exists:
                raise ValueError("반려동물을 찾을 수 없습니다.")
            
            pet_data = pet_doc.to_dict()
            
            # 권장량 재계산
            recommendations = self._calculate_recommendations(pet_data)
            
            # 펫 문서에 권장량 업데이트
            self.pets_collection.document(pet_id).update({
                'recommended_daily_calories': recommendations['daily_calories'],
                'recommended_daily_water_ml': recommendations['daily_water_ml'],
                'recommendations_updated_at': DateTimeUtils.now()
            })
            
            logger.info(f"권장량 갱신 완료: {pet_id}")
            return recommendations
            
        except Exception as e:
            logger.error(f"권장량 갱신 실패 ({pet_id}): {e}")
            raise
    
    def get_care_settings(self, pet_id: str, user_id: str) -> Dict[str, Any]:
        """
        펫케어 설정을 조회합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            
        Returns:
            펫케어 설정
        """
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            pet_doc = self.pets_collection.document(pet_id).get()
            if not pet_doc.exists:
                raise ValueError("반려동물을 찾을 수 없습니다.")
            
            pet_data = pet_doc.to_dict()
            care_settings = pet_data.get('care_settings', {})
            
            # 기본값 설정
            default_settings = {
                'food_increment': 50,       # 음식 빠른 추가 단위 (g)
                'water_increment': 100,     # 물 빠른 추가 단위 (ml)
                'activity_increment': 15    # 활동 빠른 추가 단위 (분)
            }
            
            # 기본값과 병합
            settings = {**default_settings, **care_settings}
            
            return settings
            
        except Exception as e:
            logger.error(f"펫케어 설정 조회 실패 ({pet_id}): {e}")
            raise
    
    def update_care_settings(self, pet_id: str, user_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        펫케어 설정을 업데이트합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            settings: 업데이트할 설정
            
        Returns:
            업데이트된 설정
        """
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 유효성 검사
            if 'food_increment' in settings:
                if not 10 <= settings['food_increment'] <= 500:
                    raise ValueError("음식 증가량은 10-500g 사이여야 합니다.")
            
            if 'water_increment' in settings:
                if not 50 <= settings['water_increment'] <= 1000:
                    raise ValueError("물 증가량은 50-1000ml 사이여야 합니다.")
            
            if 'activity_increment' in settings:
                if not 5 <= settings['activity_increment'] <= 60:
                    raise ValueError("활동 증가량은 5-60분 사이여야 합니다.")
            
            # 업데이트
            self.pets_collection.document(pet_id).update({
                'care_settings': settings,
                'care_settings_updated_at': DateTimeUtils.now()
            })
            
            logger.info(f"펫케어 설정 업데이트 완료: {pet_id}")
            return settings
            
        except Exception as e:
            logger.error(f"펫케어 설정 업데이트 실패 ({pet_id}): {e}")
            raise
    
    def _calculate_recommendations(self, pet_data: Dict[str, Any]) -> Dict[str, Any]:
        """펫 데이터를 기반으로 권장량을 계산합니다."""
        
        # 기본 정보 추출
        weight_kg = pet_data.get('current_weight', 0)
        activity_level = pet_data.get('activity_level', 'moderate')
        age = self._calculate_age(pet_data.get('birthdate'))
        is_neutered = pet_data.get('is_neutered', False)
        
        # 생애 단계 결정
        life_stage = self._determine_life_stage(age)
        
        # 기초 대사율 계산 (RER: Resting Energy Requirement)
        rer = 70 * (weight_kg ** 0.75)
        
        # 일일 칼로리 필요량 계산 (DER: Daily Energy Requirement)
        base_multiplier = self.BASE_CALORIE_MULTIPLIERS.get(life_stage, 1.6)
        activity_multiplier = self.ACTIVITY_MULTIPLIERS.get(activity_level, 1.0)
        
        # 중성화 여부에 따른 조정
        if is_neutered and life_stage == 'adult':
            base_multiplier *= 0.8
        
        # 최종 일일 칼로리
        daily_calories = rer * base_multiplier * activity_multiplier
        
        # 일일 물 필요량 (체중 1kg당 50-70ml)
        daily_water_ml = weight_kg * 60
        
        # 체중 상태 평가
        weight_status = self._evaluate_weight_status(pet_data)
        
        # 권장사항 생성
        recommendations = self._generate_specific_recommendations(
            pet_data, life_stage, weight_status
        )
        
        return {
            'daily_calories': round(daily_calories),
            'daily_water_ml': round(daily_water_ml),
            'multiplier_used': base_multiplier * activity_multiplier,
            'multiplier_reason': f"{life_stage} + {activity_level} 활동량",
            'weight_status': weight_status,
            'recommendations': recommendations,
            'calculated_at': DateTimeUtils.now()
        }
    
    def _calculate_age(self, birthdate) -> float:
        """생년월일로부터 나이를 계산합니다."""
        if not birthdate:
            return 0
        
        today = datetime.now().date()
        if isinstance(birthdate, datetime):
            birthdate = birthdate.date()
        
        age_days = (today - birthdate).days
        return age_days / 365.25
    
    def _determine_life_stage(self, age: float) -> str:
        """나이를 기반으로 생애 단계를 결정합니다."""
        if age < 1:
            return 'puppy'
        elif age < 3:
            return 'young'
        elif age < 7:
            return 'adult'
        else:
            return 'senior'
    
    def _evaluate_weight_status(self, pet_data: Dict[str, Any]) -> str:
        """체중 상태를 평가합니다."""
        # BCS 기반 평가 (있는 경우)
        bcs_level = None
        weight_logs = pet_data.get('weight_logs', [])
        if weight_logs:
            latest_weight = max(weight_logs, key=lambda x: x.get('timestamp', datetime.min))
            bcs_level = latest_weight.get('bcs_level')
        
        if bcs_level:
            if bcs_level <= 3:
                return 'underweight'
            elif bcs_level <= 5:
                return 'normal'
            elif bcs_level <= 7:
                return 'overweight'
            else:
                return 'obese'
        
        # 품종별 표준 체중과 비교 (추후 구현)
        return 'normal'
    
    def _generate_specific_recommendations(self, pet_data: Dict, 
                                         life_stage: str, 
                                         weight_status: str) -> list:
        """구체적인 권장사항을 생성합니다."""
        recommendations = []
        
        # 체중 관련 권장사항
        if weight_status == 'underweight':
            recommendations.append("체중이 부족합니다. 사료량을 10-20% 늘려보세요.")
        elif weight_status == 'overweight':
            recommendations.append("체중이 과다합니다. 사료량을 10-20% 줄이고 운동량을 늘려주세요.")
        elif weight_status == 'obese':
            recommendations.append("비만 상태입니다. 수의사와 상담하여 체중 감량 계획을 세우세요.")
        
        # 나이별 권장사항
        if life_stage == 'puppy':
            recommendations.append("성장기입니다. 고품질 퍼피 사료를 급여하세요.")
        elif life_stage == 'senior':
            recommendations.append("노령기입니다. 관절 건강과 소화가 쉬운 사료를 고려하세요.")
        
        # 활동량 관련
        activity_level = pet_data.get('activity_level', 'moderate')
        if activity_level == 'low':
            recommendations.append("활동량이 적습니다. 매일 산책 시간을 늘려주세요.")
        
        return recommendations
