"""Pet Care Record Integration Service.

This service integrates record operations with settings and provides
enhanced functionality including goal tracking and daily summaries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.utils.datetime_utils import DateTimeUtils
from app.utils import metrics


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
        self.notification_service = notification_service
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
            
            # Add goal analysis
            if settings and record_data.get('search_date'):
                goal_analysis = self._analyze_daily_goals(
                    pet_id, 
                    record_data['search_date'],
                    settings
                )
                result['goal_analysis'] = goal_analysis
                
                # Send achievement notifications if goals are met
                self._send_achievement_notifications(pet_id, goal_analysis, record_data)
            
            # Invalidate affected caches
            affected_dates = [record_data.get('search_date')]
            if affected_dates and affected_dates[0]:
                self.cache.invalidate_affected_caches(pet_id, affected_dates)
                
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
            records_result = self.query.get_daily_records(pet_id, date)
            
            # Get pet settings
            settings = self.settings.get_settings(pet_id)
            
            # Build summary with goal analysis
            summary = {
                'date': date,
                'records': records_result['records'],
                'record_counts': self._count_by_type(records_result['records']),
                'meta': records_result['meta']
            }
            
            # Add goal analysis if settings available
            if settings:
                goal_progress = self._analyze_daily_goals(pet_id, date, settings)
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
            records_result = self.query.get_range_records(pet_id, start_date, end_date)
            
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
            summary['trends'] = self._analyze_trends(records_result['records_by_date'])
            
            # Add goal tracking if settings available
            if settings:
                goal_tracking = self._analyze_range_goals(
                    pet_id, start_date, end_date, settings, records_result['records_by_date']
                )
                summary['goal_tracking'] = goal_tracking
                summary['goal_tracking'] = goal_tracking
                
            metrics.increment('range_summary_with_trends_retrieved')
            
            return summary
            
        except Exception as e:
            logging.error(f"Failed to get range summary with trends for pet {pet_id}: {e}", exc_info=True)
            raise

    def _analyze_daily_goals(self, pet_id: str, date: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze daily records against goals.
        
        Args:
            pet_id: The pet's unique identifier
            date: Date in YYYY-MM-DD format
            settings: Pet settings with goals
            
        Returns:
            dict: Goal analysis results
        """
        try:
            records_result = self.query.get_daily_records(pet_id, date)
            records = records_result['records']
            
            analysis = {
                'date': date,
                'goals': {},
                'achievements': {},
                'recommendations': []
            }
            
            # Analyze meal goals
            if 'daily_meal_count_goal' in settings:
                meal_goal = settings['daily_meal_count_goal']
                meal_records = [r for r in records if r.get('record_type') == 'meal']
                meal_count = len(meal_records)
                
                analysis['goals']['meal_count'] = meal_goal
                analysis['achievements']['meal_count'] = {
                    'actual': meal_count,
                    'goal': meal_goal,
                    'percentage': (meal_count / meal_goal * 100) if meal_goal > 0 else 0,
                    'achieved': meal_count >= meal_goal
                }
                
                if meal_count < meal_goal:
                    analysis['recommendations'].append({
                        'type': 'meal_shortage',
                        'message': f'오늘 식사 목표({meal_goal}회)보다 {meal_goal - meal_count}회 부족합니다.'
                    })
            
            # Analyze activity goals
            if 'daily_activity_duration_goal' in settings:
                activity_goal = settings['daily_activity_duration_goal']  # in minutes
                activity_records = [r for r in records if r.get('record_type') == 'activity']
                total_activity = sum(r.get('data', {}).get('duration', 0) for r in activity_records)
                
                analysis['goals']['activity_duration'] = activity_goal
                analysis['achievements']['activity_duration'] = {
                    'actual': total_activity,
                    'goal': activity_goal,
                    'percentage': (total_activity / activity_goal * 100) if activity_goal > 0 else 0,
                    'achieved': total_activity >= activity_goal,
                    'unit': 'minutes'
                }
                
                if total_activity < activity_goal:
                    remaining = activity_goal - total_activity
                    analysis['recommendations'].append({
                        'type': 'activity_shortage',
                        'message': f'오늘 활동 목표({activity_goal}분)보다 {remaining}분 부족합니다.'
                    })
            
            # Analyze weight goals
            if 'target_weight' in settings:
                target_weight = settings['target_weight']
                weight_records = [r for r in records if r.get('record_type') == 'weight']
                
                if weight_records:
                    latest_weight = weight_records[-1].get('data', {}).get('weight', 0)
                    weight_diff = latest_weight - target_weight
                    
                    analysis['goals']['target_weight'] = target_weight
                    analysis['achievements']['current_weight'] = {
                        'actual': latest_weight,
                        'goal': target_weight,
                        'difference': weight_diff,
                        'at_goal': abs(weight_diff) <= 0.1,  # Within 0.1kg tolerance
                        'unit': 'kg'
                    }
                    
                    if weight_diff > 0.1:
                        analysis['recommendations'].append({
                            'type': 'weight_over',
                            'message': f'목표 체중({target_weight}kg)보다 {weight_diff:.1f}kg 높습니다.'
                        })
                    elif weight_diff < -0.1:
                        analysis['recommendations'].append({
                            'type': 'weight_under',
                            'message': f'목표 체중({target_weight}kg)보다 {weight_diff:.1f}kg 낮습니다.'
                        })
                        
            return analysis
            
        except Exception as e:
            logging.error(f"Failed to analyze daily goals for pet {pet_id}, date {date}: {e}", exc_info=True)
            return {'error': str(e)}

    def _analyze_range_goals(self, pet_id: str, start_date: str, end_date: str, 
                                 settings: Dict[str, Any], records_by_date: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """Analyze goal achievement over a date range.
        
        Args:
            pet_id: The pet's unique identifier
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            settings: Pet settings with goals
            records_by_date: Records grouped by date
            
        Returns:
            dict: Range goal analysis
        """
        try:
            tracking = {
                'period': {'start_date': start_date, 'end_date': end_date},
                'daily_achievements': {},
                'overall_stats': {}
            }
            
            total_days = len(records_by_date)
            if total_days == 0:
                return tracking
            
            # Analyze each day
            achievement_counts = {'meal': 0, 'activity': 0, 'weight': 0}
            
            for date, records in records_by_date.items():
                daily_analysis = self._analyze_daily_goals(pet_id, date, settings)
                tracking['daily_achievements'][date] = daily_analysis.get('achievements', {})
                
                # Count achievements
                for goal_type, achievement in daily_analysis.get('achievements', {}).items():
                    if achievement.get('achieved'):
                        if 'meal' in goal_type:
                            achievement_counts['meal'] += 1
                        elif 'activity' in goal_type:
                            achievement_counts['activity'] += 1
                        elif 'weight' in goal_type:
                            achievement_counts['weight'] += 1
            
            # Calculate overall statistics
            tracking['overall_stats'] = {
                'total_days': total_days,
                'goal_achievement_rates': {
                    'meal': (achievement_counts['meal'] / total_days * 100) if total_days > 0 else 0,
                    'activity': (achievement_counts['activity'] / total_days * 100) if total_days > 0 else 0,
                    'weight': (achievement_counts['weight'] / total_days * 100) if total_days > 0 else 0
                }
            }
            
            return tracking
            
        except Exception as e:
            logging.error(f"Failed to analyze range goals for pet {pet_id}: {e}", exc_info=True)
            return {'error': str(e)}

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

    def _analyze_trends(self, records_by_date: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """Analyze trends in the record data.
        
        Args:
            records_by_date: Records grouped by date
            
        Returns:
            dict: Trend analysis results
        """
        try:
            trends = {
                'weight_trend': [],
                'meal_frequency_trend': [],
                'activity_trend': []
            }
            
            for date in sorted(records_by_date.keys()):
                records = records_by_date[date]
                
                # Weight trend
                weight_records = [r for r in records if r.get('record_type') == 'weight']
                if weight_records:
                    latest_weight = weight_records[-1].get('data', {}).get('weight', 0)
                    trends['weight_trend'].append({'date': date, 'weight': latest_weight})
                
                # Meal frequency
                meal_count = len([r for r in records if r.get('record_type') == 'meal'])
                trends['meal_frequency_trend'].append({'date': date, 'meal_count': meal_count})
                
                # Activity duration
                activity_records = [r for r in records if r.get('record_type') == 'activity']
                total_activity = sum(r.get('data', {}).get('duration', 0) for r in activity_records)
                trends['activity_trend'].append({'date': date, 'activity_duration': total_activity})
            
            return trends
            
        except Exception as e:
            logging.error(f"Failed to analyze trends: {e}", exc_info=True)
            return {}

    def _send_achievement_notifications(self, pet_id: str, goal_analysis: Dict[str, Any], record_data: Dict[str, Any]) -> None:
        """Send notifications when goals are achieved.
        
        Args:
            pet_id: The pet's unique identifier
            goal_analysis: Goal analysis results
            record_data: Record data that triggered the check
        """
        if not self.notification_service:
            logging.debug("Notification service not available, skipping achievement notifications")
            return
            
        try:
            achievements = goal_analysis.get('achievements', {})
            pet_name = record_data.get('pet_name', '반려동물')  # Default name if not provided
            date = goal_analysis.get('date')
            
            notifications_sent = []
            
            # Check meal goal achievement
            meal_achievement = achievements.get('meal_count', {})
            if meal_achievement.get('achieved') and meal_achievement.get('percentage', 0) >= 100:
                # Only notify on exact achievement (first time reaching 100%)
                if meal_achievement.get('actual') == meal_achievement.get('goal'):
                    message = f"🎉 {pet_name}의 오늘 식사 목표를 달성했어요! ({meal_achievement['actual']}/{meal_achievement['goal']}회)"
                    self._send_notification(pet_id, 'meal_goal_achieved', message, {
                        'pet_id': pet_id,
                        'date': date,
                        'goal_type': 'meal',
                        'actual': meal_achievement['actual'],
                        'goal': meal_achievement['goal']
                    })
                    notifications_sent.append('meal_goal')
            
            # Check activity goal achievement  
            activity_achievement = achievements.get('activity_duration', {})
            if activity_achievement.get('achieved') and activity_achievement.get('percentage', 0) >= 100:
                # Check if this record pushed us over the goal line
                previous_duration = activity_achievement.get('actual', 0) - record_data.get('data', {}).get('duration', 0)
                if previous_duration < activity_achievement.get('goal', 0):
                    message = f"🏃 {pet_name}의 오늘 활동 목표를 달성했어요! ({activity_achievement['actual']}/{activity_achievement['goal']}분)"
                    self._send_notification(pet_id, 'activity_goal_achieved', message, {
                        'pet_id': pet_id,
                        'date': date,
                        'goal_type': 'activity',
                        'actual': activity_achievement['actual'],
                        'goal': activity_achievement['goal'],
                        'unit': 'minutes'
                    })
                    notifications_sent.append('activity_goal')
            
            # Check weight goal achievement
            weight_achievement = achievements.get('current_weight', {})
            if weight_achievement.get('at_goal'):
                # Only notify for weight records
                if record_data.get('record_type') == 'weight':
                    message = f"⚖️ {pet_name}의 목표 체중을 달성했어요! (현재: {weight_achievement['actual']}kg, 목표: {weight_achievement['goal']}kg)"
                    self._send_notification(pet_id, 'weight_goal_achieved', message, {
                        'pet_id': pet_id,
                        'date': date,
                        'goal_type': 'weight',
                        'actual': weight_achievement['actual'],
                        'goal': weight_achievement['goal'],
                        'unit': 'kg'
                    })
                    notifications_sent.append('weight_goal')
            
            if notifications_sent:
                logging.info(f"Sent achievement notifications for pet {pet_id}: {notifications_sent}")
                metrics.increment('pet_care_achievement_notifications_sent', 
                                notification_types=','.join(notifications_sent))
                
        except Exception as e:
            logging.error(f"Failed to send achievement notifications for pet {pet_id}: {e}", exc_info=True)

    def _send_notification(self, pet_id: str, notification_type: str, message: str, data: Dict[str, Any]) -> None:
        """Send a notification to the pet owner.
        
        Args:
            pet_id: The pet's unique identifier
            notification_type: Type of notification
            message: Notification message
            data: Additional data for the notification
        """
        try:
            # Get user_id from the record data
            user_id = data.get('user_id')
            
            if not user_id:
                logging.warning(f"No user_id found for pet {pet_id}, cannot send notification")
                return
            
            # Import NotificationType enum
            from app.models.notification import NotificationType
            
            # Use the notification service's create_notification method
            # Since this is a pet care achievement, we'll use a custom notification type
            # or use a general system notification type
            self.notification_service.create_notification(
                recipient_id=user_id,
                sender_id='system',  # System-generated notification
                n_type=NotificationType.SYSTEM,  # Assuming there's a SYSTEM type
                target_id=pet_id,
                target_summary=message
            )
            
            logging.info(f"Sent {notification_type} notification to user {user_id} for pet {pet_id}")
            
        except Exception as e:
            logging.error(f"Failed to send notification {notification_type} for pet {pet_id}: {e}", exc_info=True)
