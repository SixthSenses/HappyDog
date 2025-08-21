# app/api/pet_care/services_new/daily_logs.py
"""
일일 종합 로그 관리 서비스
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import asdict

from .base import BasePetCareService
from app.models.pet_care_log import PetCareLog
from app.utils.datetime_utils import DateTimeUtils

logger = logging.getLogger(__name__)


class DailyLogService(BasePetCareService):
    """
    일일 종합 로그 관리를 담당하는 서비스
    """
    
    def create_or_update_daily_log(self, pet_id: str, user_id: str, log_data: Dict[str, Any]) -> PetCareLog:
        """
        일일 펫케어 로그를 생성하거나 업데이트합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID  
            log_data: 로그 데이터 (date 필드 필수)
            
        Returns:
            생성/업데이트된 PetCareLog 객체
        """
        try:
            # 소유권 확인
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 날짜 확인
            log_date = log_data.get('date')
            if not log_date:
                raise ValueError("날짜(date) 필드가 필요합니다.")
            
            # 문서 ID 생성
            log_id = self._get_or_create_daily_log(pet_id, user_id, log_date)
            
            # 기존 데이터 조회
            doc_ref = self.care_logs_collection.document(log_id)
            doc = doc_ref.get()
            
            if doc.exists:
                # 기존 로그 업데이트
                update_data = {
                    'updated_at': DateTimeUtils.now()
                }
                
                # 메타데이터 업데이트
                if 'general_notes' in log_data:
                    update_data['general_notes'] = log_data['general_notes']
                if 'mood' in log_data:
                    update_data['mood'] = log_data['mood']
                
                doc_ref.update(update_data)
                logger.info(f"일일 로그 업데이트 완료: {log_id}")
                
            else:
                # 새 로그 생성
                new_log = PetCareLog(
                    log_id=log_id,
                    pet_id=pet_id,
                    user_id=user_id,
                    date=log_date,
                    general_notes=log_data.get('general_notes'),
                    mood=log_data.get('mood')
                )
                
                doc_ref.set(self._convert_date_for_firestore(asdict(new_log)))
                logger.info(f"새 일일 로그 생성 완료: {log_id}")
            
            # 업데이트된 데이터 반환
            return self.get_daily_log(pet_id, user_id, log_date)
            
        except Exception as e:
            logger.error(f"일일 로그 생성/업데이트 실패 ({pet_id}, {log_date}): {e}")
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
            # 소유권 확인
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
            logger.error(f"일일 로그 조회 실패 ({pet_id}, {log_date}): {e}")
            raise
    
    def get_monthly_summary(self, pet_id: str, user_id: str, year: int, month: int) -> Dict[str, Any]:
        """
        월별 펫케어 로그 요약을 조회합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            year: 연도
            month: 월
            
        Returns:
            월별 요약 데이터
        """
        try:
            # 소유권 확인
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 해당 월의 시작일과 종료일 계산
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            
            # 해당 기간의 로그 조회
            logs = []
            current_date = start_date
            while current_date <= end_date:
                log = self.get_daily_log(pet_id, user_id, current_date)
                if log:
                    logs.append(log)
                current_date += timedelta(days=1)
            
            # 요약 생성
            summary = {
                'pet_id': pet_id,
                'year': year,
                'month': month,
                'total_days': len(logs),
                'average_daily_calories': 0,
                'average_daily_water_ml': 0,
                'average_daily_activity_minutes': 0,
                'weight_trend': [],
                'logs_by_type': {
                    'food': 0,
                    'water': 0,
                    'poop': 0,
                    'activity': 0,
                    'weight': 0,
                    'vomit': 0
                }
            }
            
            if logs:
                # 평균 계산
                total_calories = sum(log.total_calories for log in logs)
                total_water = sum(log.total_water_ml for log in logs)
                total_activity = sum(log.total_activity_minutes for log in logs)
                
                summary['average_daily_calories'] = total_calories / len(logs)
                summary['average_daily_water_ml'] = total_water / len(logs)
                summary['average_daily_activity_minutes'] = total_activity / len(logs)
                
                # 로그 타입별 카운트
                for log in logs:
                    summary['logs_by_type']['food'] += len(log.food_logs)
                    summary['logs_by_type']['water'] += len(log.water_logs)
                    summary['logs_by_type']['poop'] += len(log.poop_logs)
                    summary['logs_by_type']['activity'] += len(log.activity_logs)
                    summary['logs_by_type']['weight'] += len(log.weight_logs)
                    summary['logs_by_type']['vomit'] += len(log.vomit_logs)
                    
                    # 체중 트렌드 수집
                    for weight_log in log.weight_logs:
                        summary['weight_trend'].append({
                            'date': log.date.isoformat(),
                            'weight_kg': weight_log.weight_kg
                        })
            
            logger.info(f"월별 요약 조회 완료: {pet_id} {year}-{month}")
            return summary
            
        except PermissionError:
            raise
        except Exception as e:
            logger.error(f"월별 요약 조회 실패 ({pet_id}, {year}-{month}): {e}")
            raise
