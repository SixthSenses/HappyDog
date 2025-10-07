# app/models/comment.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
from app.utils.datetime_utils import DateTimeUtils

@dataclass
class CommentAuthor:
    """Comment 문서 내부에 저장될 작성자 정보."""
    user_id: str
    nickname: str
    # profile_image_url는 Pet 정보에서 가져오도록 변경됨

@dataclass
class CommentPetInfo:
    """Comment 문서 내부에 저장될 반려동물 정보."""
    pet_id: str
    name: str
    breed: str
    profile_image_url: Optional[str] = None  # Pet 프로필 이미지 추가

@dataclass
class Comment:
    """
    Firestore 'comments' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    """
    comment_id: str
    post_id: str
    author: CommentAuthor  # 사용자 정보만 포함
    pet: CommentPetInfo  # 반려동물 정보와 프로필 이미지 포함
    text: str
    like_count: int = 0
    created_at: datetime = field(default_factory=DateTimeUtils.now)