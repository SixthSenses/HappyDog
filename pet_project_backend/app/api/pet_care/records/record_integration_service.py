"""Pet Care Record Integration Service (Facade).

This service acts as a Facade coordinating specialized sub-services:
- CrudOrchestrator: Basic CRUD with cache management
- GoalCoordinator: Goal analysis and tracking
- NotificationDispatcher: Achievement notifications
- TrendAnalyzer: Trend analysis

Maintains backward compatibility while delegating to focused services.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.utils.datetime_utils import DateTimeUtils
from app.utils import metrics
from .analyzers import GoalAnalyzer, TrendAnalyzer, MonthlyMessageBuilder, WeightMonthlyAnalyzer
from .notifier import PetCareNotifier
from .crud_orchestrator import PetCareCrudOrchestrator
from .goal_coordinator import PetCareGoalCoordinator
from .notification_dispatcher import PetCareNotificationDispatcher


class PetCareRecordIntegration:
    """Integration Facade coordinating specialized pet care services.
    
    This facade delegates to specialized services while maintaining
    backward compatibility with existing API contracts.
    """

    def __init__(
        self, 
        crud_service, 
        query_service, 
        cache_service, 
        settings_service, 
        goal_analyzer=None,
        trend_analyzer=None,
        notifier=None,
        # New Phase 2 coordinators (optional for backward compatibility)
        crud_orchestrator=None,
        goal_coordinator=None,
        notification_dispatcher=None
    ):
        """Initialize integration facade with dependency injection.
        
        Args:
            crud_service: CRUD operations service
            query_service: Query operations service
            cache_service: Cache service
            settings_service: Pet care settings service
            goal_analyzer: Optional GoalAnalyzer instance
            trend_analyzer: Optional TrendAnalyzer instance
            notifier: Optional PetCareNotifier instance
            crud_orchestrator: Optional CrudOrchestrator (Phase 2)
            goal_coordinator: Optional GoalCoordinator (Phase 2)
            notification_dispatcher: Optional NotificationDispatcher (Phase 2)
        """
        self.settings = settings_service
        
        # Legacy direct dependencies (for backward compatibility)
        self.goal_analyzer = goal_analyzer if goal_analyzer is not None else GoalAnalyzer()
        self.trend_analyzer = trend_analyzer if trend_analyzer is not None else TrendAnalyzer()
        self.notifier = notifier if notifier is not None else PetCareNotifier(notification_service=None)
        
        # Phase 2 specialized coordinators (create if not provided)
        self.crud_orchestrator = crud_orchestrator if crud_orchestrator is not None else PetCareCrudOrchestrator(
            crud_service, query_service, cache_service
        )
        self.goal_coordinator = goal_coordinator if goal_coordinator is not None else PetCareGoalCoordinator(
            query_service, settings_service, self.goal_analyzer
        )
        self.notification_dispatcher = notification_dispatcher if notification_dispatcher is not None else PetCareNotificationDispatcher(
            self.notifier
        )
        
        logging.info("PetCareRecordIntegration (Facade) initialized with specialized coordinators.")

    def create_record_with_goals(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a record and check against daily goals.
        
        Args:
            pet_id: The pet's unique identifier
            record_data: Validated record data
            
        Returns:
            dict: Created record with goal analysis
        """
        try:
            # Delegate CRUD to orchestrator (handles cache invalidation)
            result = self.crud_orchestrator.create_record(pet_id, record_data)
            
            # Enrich with goal analysis via coordinator
            search_date = result.get('searchDate')
            if search_date:
                result = self.goal_coordinator.enrich_with_goal_analysis(pet_id, result, search_date)
                
                # Dispatch achievement notifications
                if 'goal_analysis' in result:
                    self.notification_dispatcher.dispatch_achievement_notifications(
                        pet_id, result['goal_analysis'], record_data
                    )
                
            metrics.increment('pet_care_record_created_with_goals', 
                            record_type=record_data['record_type'])
            
            return result
            
        except Exception as e:
            logging.error(f"Failed to create record with goals for pet {pet_id}: {e}", exc_info=True)
            raise

    def get_daily_summary_with_goals(self, pet_id: str, date: str) -> Dict[str, Any]:
        """Get daily records summary with goal progress.
        
        Args:
            pet_id: The pet's unique identifier
            date: Date in YYYY-MM-DD format
            
        Returns:
            dict: Daily summary with goal progress analysis
        """
        try:
            # Delegate to CRUD orchestrator for basic summary
            summary = self.crud_orchestrator.get_daily_records(pet_id, date)
            
            # Add goal progress via coordinator
            goal_progress = self.goal_coordinator.get_daily_goal_progress(pet_id, date)
            if goal_progress:
                summary['goal_progress'] = goal_progress
                
            metrics.increment('daily_summary_with_goals_retrieved')
            
            return summary
            
        except Exception as e:
            logging.error(f"Failed to get daily summary with goals for pet {pet_id}, date {date}: {e}", exc_info=True)
            raise

    def get_range_summary_with_trends(self, pet_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get range records with trend analysis and goal tracking.
        
        Args:
            pet_id: The pet's unique identifier
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            dict: Range summary with trends and goal analysis
        """
        try:
            # Get range records
            records_result = self.query.get_range_grouped(pet_id, start_date, end_date)
            
            # Get historical settings covering the date range
            settings_map = self.settings.get_settings_for_range(pet_id, start_date, end_date)
            
            # Build enhanced summary
            summary = {
                'start_date': start_date,
                'end_date': end_date,
                'records_by_date': records_result['records_by_date'],
                'meta': records_result['meta']
            }
            
            # Add trend analysis
            summary['trends'] = self.trend_analyzer.build_trends(records_result['records_by_date'])
            
            # Add goal tracking if settings available
            if settings_map:
                goal_tracking = self.goal_analyzer.analyze_range_with_history(
                    records_result['records_by_date'], settings_map
                )
                summary['goal_tracking'] = goal_tracking
                
                # Build monthly summary with individual goal details
                days_achieved = goal_tracking.get('days_achieved', {})
                achievement_dates = goal_tracking.get('achievement_dates', {})
                
                total_hits = sum(days_achieved.values())
                
                summary.setdefault('meta', {})['monthly'] = {
                    'encouragement_count': total_hits,
                    'message': MonthlyMessageBuilder.build(total_hits),
                    # Individual goal achievements for UI (캘린더 표시용)
                    'meal': {
                        'achievement_count': days_achieved.get('meal', 0),
                        'achievement_dates': achievement_dates.get('meal', [])
                    },
                    'activity': {
                        'achievement_count': days_achieved.get('activity', 0),
                        'achievement_dates': achievement_dates.get('activity', [])
                    }
                }
                
            metrics.increment('range_summary_with_trends_retrieved')
            
            return summary
            
        except Exception as e:
            logging.error(f"Failed to get range summary with trends for pet {pet_id}: {e}", exc_info=True)
            raise

    # Legacy analysis methods removed (moved to GoalAnalyzer/TrendAnalyzer).

    # Range analysis moved to GoalAnalyzer.

    # Helper methods moved to specialized coordinators:
    # - _count_by_type: moved to CrudOrchestrator
    # - _send_achievement_notifications: replaced by NotificationDispatcher
    # - Trend analysis: already in TrendAnalyzer

    def get_weight_monthly_analysis(self, pet_id: str) -> Dict[str, Any]:
        """
        몸무게 월간 분석 (6개월 데이터 + 비교 텍스트)
        
        중요: 항상 오늘을 기준으로 최근 6개월 데이터를 반환합니다.
        과거 데이터를 조회하더라도 기준 시점은 오늘입니다.
        
        Args:
            pet_id: 반려동물 ID
            
        Returns:
            dict: {
                'analysis': {
                    'title': str,
                    'description': str,
                    'current_month_avg': float or None,
                    'six_months_ago_avg': float or None,
                    'difference': float or None
                },
                'monthly_data': [
                    {
                        'year_month': str,  # 'YYYY-MM'
                        'label': str,  # '5월'
                        'average_weight': float or None,
                        'record_count': int
                    },
                    ...
                ],
                'meta': {
                    'reference_date': str,  # 'YYYY-MM-DD'
                    'timezone': str
                }
            }
        """
        try:
            from datetime import datetime, timedelta
            from dateutil.relativedelta import relativedelta
            
            # 항상 오늘 기준
            today = DateTimeUtils.now()
            reference_date = today.strftime('%Y-%m-%d')
            
            # 최근 6개월 계산 (현재 월 포함)
            # 예: 2025-10 -> [2025-05, 2025-06, 2025-07, 2025-08, 2025-09, 2025-10]
            target_months = []
            for i in range(5, -1, -1):
                month_date = today - relativedelta(months=i)
                target_months.append(month_date.strftime('%Y-%m'))
            
            # 데이터 조회 기간 설정 (6개월 전 1일 ~ 오늘)
            start_date = (today - relativedelta(months=5)).replace(day=1).strftime('%Y-%m-%d')
            end_date = reference_date
            
            # 기간 내 모든 몸무게 기록 조회
            records_result = self.query.get_range_grouped(pet_id, start_date, end_date)
            
            # 월별 평균 계산
            monthly_averages = WeightMonthlyAnalyzer.calculate_monthly_averages(
                records_result['records_by_date'],
                target_months
            )
            
            # 현재 월과 6개월 전 월 평균
            current_month = target_months[-1]  # 가장 최근 월
            six_months_ago_month = target_months[0]  # 6개월 전 월
            
            current_avg = monthly_averages.get(current_month, {}).get('average_weight')
            six_months_ago_avg = monthly_averages.get(six_months_ago_month, {}).get('average_weight')
            
            # 분석 텍스트 생성
            analysis = WeightMonthlyAnalyzer.generate_analysis_text(
                current_avg,
                six_months_ago_avg
            )
            
            # 월별 데이터 구조화
            monthly_data = []
            for month in target_months:
                month_info = monthly_averages.get(month, {})
                
                # 월 라벨 생성 (예: '5월', '6월')
                month_num = int(month.split('-')[1])
                label = f"{month_num}월"
                
                monthly_data.append({
                    'year_month': month,
                    'label': label,
                    'average_weight': month_info.get('average_weight'),
                    'record_count': month_info.get('record_count', 0)
                })
            
            result = {
                'analysis': analysis,
                'monthly_data': monthly_data,
                'meta': {
                    'reference_date': reference_date,
                    'timezone': 'Asia/Seoul'
                }
            }
            
            metrics.increment('weight_monthly_analysis_retrieved')
            
            return result
            
        except Exception as e:
            logging.error(f"Failed to get weight monthly analysis for pet {pet_id}: {e}", exc_info=True)
            raise
