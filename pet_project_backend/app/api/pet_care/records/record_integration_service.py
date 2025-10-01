"""Pet Care Record Integration Service.

This service integrates record operations with settings and provides
enhanced functionality including goal tracking and daily summaries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.utils.datetime_utils import DateTimeUtils
from app.utils import metrics
from .analyzers import GoalAnalyzer, TrendAnalyzer, MonthlyMessageBuilder
from .notifier import PetCareNotifier


class PetCareRecordIntegration:
    """Integration service that coordinates record operations with pet settings.
    
    This service provides enhanced functionality by combining record data
    with pet settings to offer goal tracking and intelligent recommendations.
    """

    def __init__(self, crud_service, query_service, cache_service, settings_service, notification_service=None):
        self.crud = crud_service
        self.query = query_service
        self.cache = cache_service
        self.settings = settings_service
        self.goal_analyzer = GoalAnalyzer()
        self.trend_analyzer = TrendAnalyzer()
        self.notifier = PetCareNotifier(notification_service)
        logging.info("PetCareRecordIntegration initialized.")

    def create_record_with_goals(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a record and check against daily goals.
        
        Args:
            pet_id: The pet's unique identifier
            record_data: Validated record data
            
        Returns:
            dict: Created record with goal analysis
        """
        try:
            # Create the record
            result = self.crud.create_record(pet_id, record_data)
            
            # Get pet settings for goal comparison
            settings = self.settings.get_settings(pet_id)
            
            # record_service 는 'searchDate' 키로 반환하므로 내부 처리용 snake_case 필드 추가
            search_date = result.get('searchDate')
            if search_date:
                record_data['search_date'] = search_date  # 후속 goal 분석 로직에서 사용

            # Add goal analysis (settings 존재 + search_date 확보 시)
            if settings and search_date:
                goal_analysis = self.goal_analyzer.analyze_daily(
                    self.query.get_daily(pet_id, search_date)['records'],
                    search_date,
                    settings,
                )
                result['goal_analysis'] = goal_analysis

                # Send achievement notifications if goals are met
                self._send_achievement_notifications(pet_id, goal_analysis, record_data)
            
            # Invalidate affected caches (optional cache service)
            affected_dates = [record_data.get('search_date')]
            if affected_dates and affected_dates[0] and self.cache:
                try:
                    self.cache.invalidate_affected_caches(pet_id, affected_dates)
                except Exception as ce:
                    # Cache is best-effort; do not fail record creation on cache errors
                    logging.warning(f"Cache invalidation failed for pet {pet_id}, dates={affected_dates}: {ce}")
                
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
            # Get daily records
            records_result = self.query.get_daily(pet_id, date)
            
            # Get pet settings
            settings = self.settings.get_settings(pet_id)
            
            # Build summary with goal analysis
            summary = {
                'date': date,
                'records': records_result.get('records', []),
                'record_counts': self._count_by_type(records_result.get('records', [])),
                # QueryService.get_daily()는 'summary' 키를 반환하므로 이를 meta로 노출
                'meta': records_result.get('summary', {})
            }
            
            # Add goal analysis if settings available
            if settings:
                goal_progress = self.goal_analyzer.analyze_daily(records_result['records'], date, settings)
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
            
            # Get pet settings
            settings = self.settings.get_settings(pet_id)
            
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
            if settings:
                goal_tracking = self.goal_analyzer.analyze_range(
                    records_result['records_by_date'], settings
                )
                summary['goal_tracking'] = goal_tracking
                # Monthly encouragement text (simple convention)
                total_hits = sum(goal_tracking.get('days_achieved', {}).values())
                summary.setdefault('meta', {})['monthly'] = {
                    'encouragement_count': total_hits,
                    'message': MonthlyMessageBuilder.build(total_hits),
                }
                
            metrics.increment('range_summary_with_trends_retrieved')
            
            return summary
            
        except Exception as e:
            logging.error(f"Failed to get range summary with trends for pet {pet_id}: {e}", exc_info=True)
            raise

    # Legacy analysis methods removed (moved to GoalAnalyzer/TrendAnalyzer).

    # Range analysis moved to GoalAnalyzer.

    def _count_by_type(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count records by type.
        
        Args:
            records: List of records
            
        Returns:
            dict: Count by record type
        """
        counts = {}
        for record in records:
            record_type = record.get('record_type', 'unknown')
            counts[record_type] = counts.get(record_type, 0) + 1
        return counts

    # Trend analysis moved to TrendAnalyzer.

    def _send_achievement_notifications(self, pet_id: str, goal_analysis: Dict[str, Any], record_data: Dict[str, Any]) -> None:
        """Send notifications when goals are achieved.
        
        Args:
            pet_id: The pet's unique identifier
            goal_analysis: Goal analysis results
            record_data: Record data that triggered the check
        """
        try:
            achievements = goal_analysis.get('achievements', {})
            pet_name = record_data.get('pet_name', '반려동물')
            date = goal_analysis.get('date')

            meal = achievements.get('meal')
            if meal and meal.get('achieved'):
                self.notifier.notify_goal(pet_id, 'meal', {
                    'message': f"{pet_name}의 오늘 식사 목표를 달성했어요! ({meal['actual']}/{meal['goal']}회)",
                    'date': date,
                    'goal_type': 'meal',
                    'actual': meal['actual'],
                    'goal': meal['goal'],
                })

            act = achievements.get('activity')
            if act and act.get('achieved'):
                detail = act.get('detail') or {}
                sessions = detail.get('sessions')
                per_session = detail.get('minutes_per_session')
                if sessions and per_session:
                    msg_extra = f" (세션 {sessions}회 × {per_session}분)"
                else:
                    msg_extra = ""
                self.notifier.notify_goal(pet_id, 'activity', {
                    'message': f"{pet_name}의 오늘 활동 목표를 달성했어요! ({act['actual']}/{act['goal']}분){msg_extra}",
                    'date': date,
                    'goal_type': 'activity',
                    'actual': act['actual'],
                    'goal': act['goal'],
                })

            wt = achievements.get('weight')
            if wt and wt.get('at_goal'):
                self.notifier.notify_goal(pet_id, 'weight', {
                    'message': f"{pet_name}의 목표 체중을 달성했어요! (현재: {wt['actual']}kg, 목표: {wt['goal']}kg)",
                    'date': date,
                    'goal_type': 'weight',
                    'actual': wt['actual'],
                    'goal': wt['goal'],
                })
        except Exception as e:
            logging.error(f"Failed to send achievement notifications for pet {pet_id}: {e}", exc_info=True)

    # Direct notification helper removed; notifier handles transport.
