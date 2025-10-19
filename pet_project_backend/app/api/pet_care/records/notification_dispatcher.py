"""Pet Care Notification Dispatcher.

Dispatches notifications based on goal achievements and other pet care events.
This service is responsible for determining when and what notifications to send.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.utils import metrics


class PetCareNotificationDispatcher:
    """Dispatches notifications for pet care events.
    
    This service focuses on notification decision logic and dispatching,
    determining when notifications should be sent based on events and achievements.
    """

    def __init__(self, notifier):
        """Initialize dispatcher with dependencies.
        
        Args:
            notifier: PetCareNotifier instance for actual notification delivery
        """
        self.notifier = notifier
        logging.info("PetCareNotificationDispatcher initialized.")

    def dispatch_achievement_notifications(
        self, 
        pet_id: str, 
        goal_analysis: Dict[str, Any], 
        record_data: Dict[str, Any]
    ) -> None:
        """Dispatch notifications when goals are achieved.
        
        Args:
            pet_id: The pet's unique identifier
            goal_analysis: Goal analysis results
            record_data: Record data that triggered the check
        """
        try:
            if not goal_analysis or 'achievements' not in goal_analysis:
                return
            
            achievements = goal_analysis['achievements']
            
            # Check meal goal achievement
            if 'meal' in achievements:
                meal_info = achievements['meal']
                if isinstance(meal_info, dict) and meal_info.get('achieved'):
                    self._send_meal_goal_notification(pet_id, meal_info)
            
            # Check activity goal achievement
            if 'activity' in achievements:
                activity_info = achievements['activity']
                if isinstance(activity_info, dict) and activity_info.get('achieved'):
                    self._send_activity_goal_notification(pet_id, activity_info)
            
            # Check weight goal achievement
            if 'weight' in achievements:
                weight_info = achievements['weight']
                if isinstance(weight_info, dict) and weight_info.get('achieved'):
                    self._send_weight_goal_notification(pet_id, weight_info)
                    
        except Exception as e:
            # Best-effort notification; don't fail the main operation
            logging.warning(f"Failed to dispatch achievement notifications for pet {pet_id}: {e}")

    def _send_meal_goal_notification(self, pet_id: str, meal_info: Dict[str, Any]) -> None:
        """Send meal goal achievement notification."""
        try:
            payload = {
                'goal_type': 'meal',
                'message': f"오늘의 식사 목표를 달성했어요! ({meal_info.get('actual')}/{meal_info.get('goal')})",
                'actual': meal_info.get('actual'),
                'goal': meal_info.get('goal'),
            }
            self.notifier.notify_goal(pet_id, 'meal', payload)
            metrics.increment('pet_care_notification_sent', goal_type='meal')
        except Exception as e:
            logging.warning(f"Failed to send meal goal notification for pet {pet_id}: {e}")

    def _send_activity_goal_notification(self, pet_id: str, activity_info: Dict[str, Any]) -> None:
        """Send activity goal achievement notification."""
        try:
            payload = {
                'goal_type': 'activity',
                'message': f"오늘의 활동 목표를 달성했어요! ({activity_info.get('actual')}분/{activity_info.get('goal')}분)",
                'actual': activity_info.get('actual'),
                'goal': activity_info.get('goal'),
            }
            self.notifier.notify_goal(pet_id, 'activity', payload)
            metrics.increment('pet_care_notification_sent', goal_type='activity')
        except Exception as e:
            logging.warning(f"Failed to send activity goal notification for pet {pet_id}: {e}")

    def _send_weight_goal_notification(self, pet_id: str, weight_info: Dict[str, Any]) -> None:
        """Send weight goal achievement notification."""
        try:
            payload = {
                'goal_type': 'weight',
                'message': f"목표 체중을 달성했어요! (현재: {weight_info.get('actual')}kg, 목표: {weight_info.get('goal')}kg)",
                'actual': weight_info.get('actual'),
                'goal': weight_info.get('goal'),
            }
            self.notifier.notify_goal(pet_id, 'weight', payload)
            metrics.increment('pet_care_notification_sent', goal_type='weight')
        except Exception as e:
            logging.warning(f"Failed to send weight goal notification for pet {pet_id}: {e}")
