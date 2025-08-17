# app/services/notification_service.py
import logging
import uuid
from dataclasses import asdict
from firebase_admin import firestore
from typing import Optional

from app.models.notification import Notification, NotificationType

class NotificationService:
    """
    알림 관련 비즈니스 로직을 담당하는 공용 서비스 클래스.
    """
    def __init__(self):
        self.db = firestore.client()
        self.notifications_ref = self.db.collection('notifications')
        self.users_ref = self.db.collection('users')

    def create_notification(self, recipient_id: str, sender_id: str, n_type: NotificationType, target_id: str, target_summary: Optional[str] = None):
        """
        다양한 종류의 알림을 생성하여 Firestore에 저장합니다.
        - 자기 자신에게 보내는 알림은 생성하지 않습니다.
        
        :param recipient_id: 알림을 받을 사용자 ID
        :param sender_id: 알림을 유발한 사용자 ID
        :param n_type: 알림 유형 (NotificationType Enum)
        :param target_id: 알림의 대상이 되는 객체 ID (post_id, comment_id 등)
        :param target_summary: 알림에 표시될 요약 텍스트 (예: 댓글 내용)
        """
        if recipient_id == sender_id:
            return  # 자기 자신에게는 알림을 생성하지 않음

        try:
            sender_data = {}
            if sender_id == "system":
                sender_data = {
                    "user_id": "system",
                    "nickname": "HappyDog",
                    "profile_image_url": None  # 또는 기본 시스템 이미지 URL
                }
            else:
                # 발신자 정보 조회 (알림에 표시될 닉네임, 프로필 이미지 등)
                sender_doc = self.users_ref.document(sender_id).get()
                if not sender_doc.exists:
                    logging.warning(f"알림 생성 실패: 발신자(sender)를 찾을 수 없음 (ID: {sender_id})")
                    return

                sender_info = sender_doc.to_dict()
                sender_data = {
                    "user_id": sender_info.get('user_id'),
                    "nickname": sender_info.get('nickname'),
                    "profile_image_url": sender_info.get('profile_image_url')
                }

            notification = Notification(
                notification_id=str(uuid.uuid4()),
                recipient_id=recipient_id,
                sender=sender_data,
                type=n_type,
                target_id=target_id,
                target_summary=target_summary
            )
            
            # Enum 멤버를 문자열 값으로 변환하여 저장
            notification_dict = asdict(notification)
            notification_dict['type'] = notification.type.value

            self.notifications_ref.document(notification.notification_id).set(notification_dict)
            logging.info(f"{n_type.value} 알림 생성 완료: {sender_id} -> {recipient_id}")

        except Exception as e:
            logging.error(f"알림 생성 중 오류 발생: {e}", exc_info=True)

# 서비스 인스턴스는 app/__init__.py에서 생성 및 주입됩니다.
notification_service: Optional[NotificationService] = None