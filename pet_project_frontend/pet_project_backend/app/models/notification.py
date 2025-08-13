# app/models/notification.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

class NotificationType(Enum):
    """알림 유형을 정의하는 Enum 클래스"""
    POST_LIKE = "POST_LIKE"
    COMMENT_LIKE = "COMMENT_LIKE"
    COMMENT = "COMMENT"
    MENTION = "MENTION"
    CARTOON_SUCCESS = "CARTOON_SUCCESS"
    CARTOON_FAILED = "CARTOON_FAILED"

@dataclass
class Notification:
    """
    Firestore 'notifications' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    """
    notification_id: str
    recipient_id: str      # 알림을 받는 사용자 ID
    sender: Dict[str, Any] # 알림을 유발한 사용자/시스템 정보
    type: NotificationType
    target_id: str         # 알림의 대상 객체 ID (post_id, comment_id, job_id 등)
    target_summary: Optional[str] = None # "회원님의 게시글에...", "회원님의 댓글을..."
    is_read: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)