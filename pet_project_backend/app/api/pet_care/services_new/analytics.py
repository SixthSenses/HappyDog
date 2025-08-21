# app/api/pet_care/services_new/analytics.py
"""
펫케어 데이터 분석 서비스
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List
from dateutil.relativedelta import relativedelta

from .base import BasePetCareService
from app.utils.datetime_utils import DateTimeUtils

logger = logging.getLogger(__name__)


class AnalyticsService(BasePetCareService):
    """
    펫케어 데이터 분석 및 통계를 담당하는 서비스
    """
    
    def get_trends(self, pet_id: str, user_id: str, metric: str, period: str) -> Dict[str, Any]:
        """
        특정 메트릭의 트렌드 데이터를 조회합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            metric: 분석할 메트릭 (weight, calories, water, activity)
            period: 기간 (weekly, monthly, yearly)
            
        Returns:
            트렌드 데이터
        """
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 기간 계산
            end_date = date.today()
            if period == 'weekly':
                start_date = end_date - timedelta(weeks=1)
            elif period == 'monthly':
                start_date = end_date - relativedelta(months=1)
            elif period == 'yearly':
                start_date = end_date - relativedelta(years=1)
            else:
                raise ValueError(f"지원하지 않는 기간입니다: {period}")
            
            # 데이터 수집
            data_points = []
            current_date = start_date
            
            while current_date <= end_date:
                log_id = f"{pet_id}_{current_date.strftime('%Y%m%d')}"
                doc = self.care_logs_collection.document(log_id).get()
                
                if doc.exists:
                    log_data = doc.to_dict()
                    
                    if metric == 'weight':
                        weight_logs = log_data.get('weight_logs', [])
                        if weight_logs:
                            # 가장 최근 체중 기록
                            latest_weight = max(weight_logs, key=lambda x: x.get('timestamp', datetime.min))
                            data_points.append({
                                'date': current_date.isoformat(),
                                'value': latest_weight.get('weight_kg'),
                                'bcs_level': latest_weight.get('bcs_level')
                            })
                    
                    elif metric == 'calories':
                        data_points.append({
                            'date': current_date.isoformat(),
                            'value': log_data.get('total_calories', 0)
                        })
                    
                    elif metric == 'water':
                        data_points.append({
                            'date': current_date.isoformat(),
                            'value': log_data.get('total_water_ml', 0)
                        })
                    
                    elif metric == 'activity':
                        data_points.append({
                            'date': current_date.isoformat(),
                            'value': log_data.get('total_activity_minutes', 0)
                        })
                
                current_date += timedelta(days=1)
            
            # 트렌드 분석
            trend_data = self._analyze_trend(data_points, metric)
            
            return {
                'metric': metric,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'data_points': data_points,
                'analysis': trend_data
            }
            
        except Exception as e:
            logger.error(f"트렌드 조회 실패 ({pet_id}, {metric}, {period}): {e}")
            raise
    
    def get_graph_data(self, pet_id: str, user_id: str, graph_type: str, 
                      date_range: str) -> Dict[str, Any]:
        """
        그래프용 데이터를 조회합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            graph_type: 그래프 타입
            date_range: 날짜 범위
            
        Returns:
            그래프 데이터
        """
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 날짜 범위 계산
            end_date = date.today()
            if date_range == 'weekly':
                start_date = end_date - timedelta(weeks=1)
                interval = 'daily'
            elif date_range == 'monthly':
                start_date = end_date - relativedelta(months=1)
                interval = 'daily'
            elif date_range == 'quarterly':
                start_date = end_date - relativedelta(months=3)
                interval = 'weekly'
            elif date_range == 'yearly':
                start_date = end_date - relativedelta(years=1)
                interval = 'monthly'
            else:
                raise ValueError(f"지원하지 않는 날짜 범위입니다: {date_range}")
            
            # 데이터 수집 및 집계
            graph_data = self._collect_graph_data(
                pet_id, start_date, end_date, graph_type, interval
            )
            
            return {
                'graph_type': graph_type,
                'date_range': date_range,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'interval': interval,
                'data': graph_data
            }
            
        except Exception as e:
            logger.error(f"그래프 데이터 조회 실패 ({pet_id}, {graph_type}): {e}")
            raise
    
    def get_report(self, pet_id: str, user_id: str, report_period: str) -> Dict[str, Any]:
        """
        종합 리포트를 생성합니다.
        
        Args:
            pet_id: 반려동물 ID
            user_id: 사용자 ID
            report_period: 리포트 기간 (weekly, monthly)
            
        Returns:
            종합 리포트
        """
        try:
            if not self._verify_pet_ownership(pet_id, user_id):
                raise PermissionError(f"펫 {pet_id}에 대한 접근 권한이 없습니다.")
            
            # 기간 설정
            end_date = date.today()
            if report_period == 'weekly':
                start_date = end_date - timedelta(weeks=1)
            elif report_period == 'monthly':
                start_date = end_date - relativedelta(months=1)
            else:
                raise ValueError(f"지원하지 않는 리포트 기간입니다: {report_period}")
            
            # 데이터 수집
            report_data = {
                'pet_id': pet_id,
                'period': report_period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'summary': {},
                'highlights': [],
                'recommendations': []
            }
            
            # 기간 내 모든 로그 수집
            logs = []
            current_date = start_date
            while current_date <= end_date:
                log_id = f"{pet_id}_{current_date.strftime('%Y%m%d')}"
                doc = self.care_logs_collection.document(log_id).get()
                if doc.exists:
                    logs.append(doc.to_dict())
                current_date += timedelta(days=1)
            
            if logs:
                # 요약 통계
                report_data['summary'] = {
                    'total_days': len(logs),
                    'average_calories': sum(log.get('total_calories', 0) for log in logs) / len(logs),
                    'average_water_ml': sum(log.get('total_water_ml', 0) for log in logs) / len(logs),
                    'average_activity_minutes': sum(log.get('total_activity_minutes', 0) for log in logs) / len(logs),
                    'total_food_logs': sum(len(log.get('food_logs', [])) for log in logs),
                    'total_water_logs': sum(len(log.get('water_logs', [])) for log in logs),
                    'total_activity_logs': sum(len(log.get('activity_logs', [])) for log in logs),
                    'total_poop_logs': sum(len(log.get('poop_logs', [])) for log in logs),
                    'total_vomit_logs': sum(len(log.get('vomit_logs', [])) for log in logs)
                }
                
                # 하이라이트 생성
                report_data['highlights'] = self._generate_highlights(logs)
                
                # 권장사항 생성
                report_data['recommendations'] = self._generate_recommendations(report_data['summary'])
            
            return report_data
            
        except Exception as e:
            logger.error(f"리포트 생성 실패 ({pet_id}, {report_period}): {e}")
            raise
    
    def _analyze_trend(self, data_points: List[Dict], metric: str) -> Dict[str, Any]:
        """트렌드 분석을 수행합니다."""
        if not data_points:
            return {'trend': 'no_data'}
        
        values = [p['value'] for p in data_points if p.get('value') is not None]
        if not values:
            return {'trend': 'no_data'}
        
        # 간단한 트렌드 분석
        if len(values) >= 2:
            first_half = values[:len(values)//2]
            second_half = values[len(values)//2:]
            
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            
            if avg_second > avg_first * 1.1:
                trend = 'increasing'
            elif avg_second < avg_first * 0.9:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'trend': trend,
            'average': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
            'latest': values[-1]
        }
    
    def _collect_graph_data(self, pet_id: str, start_date: date, 
                           end_date: date, graph_type: str, interval: str) -> List[Dict]:
        """그래프용 데이터를 수집합니다."""
        data = []
        
        if interval == 'daily':
            current_date = start_date
            while current_date <= end_date:
                log_id = f"{pet_id}_{current_date.strftime('%Y%m%d')}"
                doc = self.care_logs_collection.document(log_id).get()
                
                if doc.exists:
                    log_data = doc.to_dict()
                    data.append({
                        'date': current_date.isoformat(),
                        'calories': log_data.get('total_calories', 0),
                        'water_ml': log_data.get('total_water_ml', 0),
                        'activity_minutes': log_data.get('total_activity_minutes', 0),
                        'weight_kg': log_data.get('current_weight_kg')
                    })
                else:
                    data.append({
                        'date': current_date.isoformat(),
                        'calories': 0,
                        'water_ml': 0,
                        'activity_minutes': 0,
                        'weight_kg': None
                    })
                
                current_date += timedelta(days=1)
        
        # TODO: weekly, monthly 집계 구현
        
        return data
    
    def _generate_highlights(self, logs: List[Dict]) -> List[str]:
        """리포트 하이라이트를 생성합니다."""
        highlights = []
        
        # 가장 활동적인 날
        most_active = max(logs, key=lambda x: x.get('total_activity_minutes', 0))
        if most_active.get('total_activity_minutes', 0) > 0:
            highlights.append(
                f"가장 활동적인 날: {most_active.get('date')} "
                f"({most_active.get('total_activity_minutes')}분)"
            )
        
        # 칼로리 섭취 패턴
        calories = [log.get('total_calories', 0) for log in logs]
        if calories:
            avg_calories = sum(calories) / len(calories)
            highlights.append(f"평균 일일 칼로리 섭취: {avg_calories:.0f}kcal")
        
        return highlights
    
    def _generate_recommendations(self, summary: Dict) -> List[str]:
        """요약 데이터를 기반으로 권장사항을 생성합니다."""
        recommendations = []
        
        # 물 섭취량 체크
        if summary.get('average_water_ml', 0) < 500:
            recommendations.append("물 섭취량이 적습니다. 더 자주 물을 제공해주세요.")
        
        # 활동량 체크
        if summary.get('average_activity_minutes', 0) < 30:
            recommendations.append("활동량이 부족합니다. 산책이나 놀이 시간을 늘려주세요.")
        
        return recommendations
