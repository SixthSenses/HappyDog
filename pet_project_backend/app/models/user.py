# app/models/user.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from app.utils.datetime_utils import DateTimeUtils

@dataclass
class User:
    """
    Firestore 'users' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    """
    user_id: str
    google_id: str
    email: str
    nickname: str
    join_date: datetime = field(default_factory=DateTimeUtils.now)
    fcm_token: Optional[str] = None # Phase 3: 푸시 알림을 위한 FCM 토큰 필드
    has_pet: bool = False  # 단일 반려동물 정책 제어
    pet_id: Optional[str] = None  # 등록된 반려동물 ID
    # 알림 시스템 연동: 읽지 않은 알림 수 (Firestore에서 증분/감소; 기본 0)
    notification_unread_count: int = 0

    # 추후 Firestore 문서에 존재하지만 데이터클래스에 정의되지 않은 필드가 있어도
    # 인스턴스화 시 오류가 발생하지 않도록 서비스 레이어에서 필터링 처리합니다.