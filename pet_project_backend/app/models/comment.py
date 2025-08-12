# app/models/comment.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any

@dataclass
class Comment:
    """
    Firestore 'comments' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    """
    comment_id: str
    post_id: str
    author: Dict[str, Any]  # {'user_id', 'nickname', 'profile_image_url'}
    text: str
    like_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)