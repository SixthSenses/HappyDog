# app/models/post.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.utils.datetime_utils import DateTimeUtils

@dataclass
class Author:
    """Post 문서 내부에 저장될 작성자 정보."""
    user_id: str
    nickname: str
    # profile_image_url는 Pet 정보에서 가져오도록 변경됨

@dataclass
class PetInfo:
    """Post 문서 내부에 저장될 반려동물 정보."""
    pet_id: str
    name: str
    breed: str
    birthdate: datetime
    profile_image_url: Optional[str] = None  # Pet 프로필 이미지 추가

@dataclass
class Post:
    """
    Firestore 'posts' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    """
    post_id: str
    author: Author
    pet: PetInfo
    image_urls: List[str]
    text: str
    like_count: int = 0
    comment_count: int = 0
    created_at: datetime = field(default_factory=DateTimeUtils.now)
    updated_at: datetime = field(default_factory=DateTimeUtils.now)