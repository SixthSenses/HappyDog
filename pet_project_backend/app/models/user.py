# app/models/user.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class User:
    """
    Firestore 'users' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    """
    user_id: str
    google_id: str
    email: str
    nickname: str
    join_date: datetime = field(default_factory=datetime.utcnow)
    profile_image_url: Optional[str] = None
    fcm_token: Optional[str] = None # Phase 3: 푸시 알림을 위한 FCM 토큰 필드