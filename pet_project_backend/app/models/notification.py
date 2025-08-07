# app/models/notification.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class NotificationActor:
    """알림 내부에 저장될 행위자 정보."""
    user_id: str
    nickname: str
    profile_image_url: Optional[str] = None

@dataclass
class Notification:
    """Firestore 'notifications' 컬렉션의 문서 구조를 정의하는 데이터클래스."""
    notification_id: str
    recipient_id: str # 알림을 받는 사람
    actor: NotificationActor # 알림을 발생시킨 사람
    type: str # 'LIKE', 'COMMENT' 등
    post_id: str # 관련된 게시물 ID
    is_read: bool = False
    created_at: datetime = field(default_factory=datetime.now)
