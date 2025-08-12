# app/models/post.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

@dataclass
class Author:
    """Post 문서 내부에 저장될 작성자 정보."""
    user_id: str
    nickname: str
    profile_image_url: Optional[str] = None

@dataclass
class PetInfo:
    """Post 문서 내부에 저장될 반려동물 정보."""
    pet_id: str
    name: str
    breed: str
    birthdate: datetime

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
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)