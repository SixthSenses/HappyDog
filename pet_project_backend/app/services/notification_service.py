# app/services/notification_service.py
import logging
import uuid
from dataclasses import asdict
from firebase_admin import firestore, messaging
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
        # 기본 정책: 인앱+푸시 동시 제공
        self.default_delivery = "both"  # values: "inapp", "push", "both"

    def create_notification(self, recipient_id: str, sender_id: str, n_type: NotificationType, target_id: str, target_summary: Optional[str] = None, delivery: Optional[str] = None):
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
            # 수신자 설정 조회
            recipient_doc = self.users_ref.document(recipient_id).get()
            if not recipient_doc.exists:
                logging.warning(f"알림 생성 실패: 수신자(recipient)를 찾을 수 없음 (ID: {recipient_id})")
                return
            recipient_info = recipient_doc.to_dict()
            recipient_prefs = (recipient_info.get('notification_preferences') or {})
            # 타입별 설정 체크 (기본 허용)
            types_prefs = recipient_prefs.get('types') or {}
            type_key = n_type.value
            if type_key in types_prefs and not types_prefs[type_key]:
                logging.info(f"수신자 설정에 의해 알림 차단됨(type={type_key}, recipient={recipient_id})")
                return
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

            # 인앱 알림(데이터 저장)
            self.notifications_ref.document(notification.notification_id).set(notification_dict)

            # 푸시 전송 정책 결정
            # per-user 모드 우선
            user_mode = (recipient_prefs.get('mode') or '').lower()
            delivery_policy = (user_mode or (delivery or self.default_delivery)).lower()
            if delivery_policy in ("push", "both"):
                try:
                    token = recipient_info.get('fcm_token')
                    if token:
                        self._send_push_notification_with_token(token, notification)
                    else:
                        raise ValueError("수신자의 FCM 토큰이 없습니다.")
                except Exception as push_err:
                    logging.warning(f"푸시 알림 전송 실패: {push_err}")

            logging.info(f"{n_type.value} 알림 생성 완료: {sender_id} -> {recipient_id}")

        except Exception as e:
            logging.error(f"알림 생성 중 오류 발생: {e}", exc_info=True)

    def list_notifications(self, user_id: str, limit: int = 20, cursor: Optional[str] = None):
        """
        사용자의 알림 목록을 커서 기반으로 조회합니다.
        반환: (items, next_cursor)
        """
        query = self.notifications_ref.where('recipient_id', '==', user_id).order_by('created_at', direction=firestore.Query.DESCENDING)
        if cursor:
            cursor_doc = self.notifications_ref.document(cursor).get()
            if cursor_doc.exists:
                query = query.start_after(cursor_doc)
        docs = query.limit(limit + 1).stream()
        items = []
        last_doc = None
        for doc in docs:
            if len(items) >= limit:
                last_doc = doc
                break
            item = doc.to_dict()
            # created_at(Timestamp) 직렬화 보조: ISO 문자열로 내보내기
            ts = item.get('created_at')
            if ts and hasattr(ts, 'isoformat'):
                try:
                    item['created_at'] = ts.isoformat()
                except Exception:
                    pass
            items.append(item)
        next_cursor = last_doc.id if last_doc else None
        return items, next_cursor

    def ack_notification(self, user_id: str, notification_id: str) -> bool:
        """알림을 읽음 처리합니다."""
        ref = self.notifications_ref.document(notification_id)
        snap = ref.get()
        if not snap.exists:
            return False
        data = snap.to_dict()
        if data.get('recipient_id') != user_id:
            return False
        ref.update({'is_read': True})
        return True

    def get_unread_count(self, user_id: str) -> int:
        """미확인(in-app) 알림 개수를 반환합니다."""
        # Firestore에서 카운트 집계는 비용이 높아질 수 있음: 추후 집계 컬렉션 고려
        query = self.notifications_ref.where('recipient_id', '==', user_id).where('is_read', '==', False)
        # 서버 사이드 count() 기능이 있다면 사용, 없으면 개수 stream
        try:
            # 일부 SDK는 .count() 지원, 미지원 시 fallback
            if hasattr(query, 'count'):
                return query.count().get()[0][0].value
        except Exception:
            pass
        return sum(1 for _ in query.stream())

    def _send_push_notification_with_token(self, token: str, notification: Notification):
        """FCM을 통해 푸시 알림을 전송합니다."""

        title = self._build_title(notification)
        body = self._build_body(notification)

        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data={
                'notification_id': notification.notification_id,
                'type': notification.type.value,
                'target_id': notification.target_id,
                'deeplink': self._build_deeplink(notification)
            }
        )
        response = messaging.send(message)
        logging.info(f"FCM message sent: {response}")

    def _build_title(self, n: Notification) -> str:
        if n.type.name.startswith('CARTOON'):
            return "카툰 작업 알림"
        if n.type in (NotificationType.POST_LIKE, NotificationType.COMMENT_LIKE):
            return "새로운 좋아요"
        if n.type == NotificationType.COMMENT:
            return "새로운 댓글"
        if n.type == NotificationType.MENTION:
            return "나를 언급했어요"
        if n.type in (NotificationType.PET_CARE_GOAL_REACHED, NotificationType.PET_CARE_DAILY_SUMMARY):
            return "펫케어 알림"
        return "알림"

    def _build_body(self, n: Notification) -> str:
        nick = n.sender.get('nickname') or '누군가'
        summary = n.target_summary or ''
        if n.type == NotificationType.COMMENT:
            return f"{nick}님이 댓글을 남겼습니다: {summary}"
        if n.type == NotificationType.MENTION:
            return f"{nick}님이 나를 언급했습니다: {summary}"
        if n.type == NotificationType.POST_LIKE:
            return f"{nick}님이 게시물을 좋아합니다"
        if n.type == NotificationType.COMMENT_LIKE:
            return f"{nick}님이 댓글을 좋아합니다: {summary}"
        if n.type == NotificationType.CARTOON_SUCCESS:
            return "카툰 생성이 완료되었습니다"
        if n.type == NotificationType.CARTOON_FAILED:
            return "카툰 생성에 실패했습니다"
        if n.type == NotificationType.CARTOON_PROGRESS:
            return "카툰 작업이 진행 중입니다"
        if n.type == NotificationType.CARTOON_COMPLETED:
            return "카툰 작업이 완료되었습니다"
        if n.type == NotificationType.PET_CARE_GOAL_REACHED:
            return "오늘 목표를 달성했어요!"
        if n.type == NotificationType.PET_CARE_DAILY_SUMMARY:
            return "오늘의 펫케어 요약을 확인하세요"
        return summary or "HappyDog 알림"

    def _build_deeplink(self, n: Notification) -> str:
        # 간단한 딥링크 규칙 제안
        if n.type.name.startswith('CARTOON'):
            return f"app://cartoon-jobs/{n.target_id}"
        if n.type in (NotificationType.COMMENT, NotificationType.POST_LIKE, NotificationType.MENTION):
            return f"app://posts/{n.target_id}"
        if n.type in (NotificationType.COMMENT_LIKE,):
            return f"app://comments/{n.target_id}"
        if n.type.name.startswith('PET_CARE'):
            return "app://pet-care/dashboard"
        return "app://home"

# 서비스 인스턴스는 app/__init__.py에서 생성 및 주입됩니다.
notification_service: Optional[NotificationService] = None