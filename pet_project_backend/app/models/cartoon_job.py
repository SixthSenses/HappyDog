# app/models/cartoon_job.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

class CartoonJobStatus(Enum):
    """만화 생성 작업의 상태를 나타내는 Enum"""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELING = "canceling" # Phase 3: 사용자가 취소를 요청한 상태

@dataclass
class CartoonJob:
    """
    Firestore 'cartoon_jobs' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    """
    job_id: str
    user_id: str
    status: CartoonJobStatus
    original_image_url: str  # file_paths[0]에서 추출된 단일 이미지 URL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_text: Optional[str] = None
    result_image_url: Optional[str] = None
    error_message: Optional[str] = None