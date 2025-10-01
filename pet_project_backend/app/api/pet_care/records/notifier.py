from __future__ import annotations
from typing import Any, Dict


class PetCareNotifier:
    def __init__(self, notification_service=None):
        self.notification_service = notification_service

    def notify_goal(self, pet_id: str, goal_type: str, payload: Dict[str, Any]) -> None:
        if not self.notification_service:
            return
        try:
            # Using a generic notification type for goal achievements
            self.notification_service.send_notification(
                pet_id=pet_id,
                n_type='PET_CARE_GOAL_REACHED',
                message=payload.get('message', ''),
                data=payload,
            )
        except Exception:
            # Best-effort; do not raise in request flow
            pass
