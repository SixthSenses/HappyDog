# app/models/cartoon_job.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

class CartoonJobStatus(Enum):
    """만화 생성 작업의 상태를 나타내는 Enum

    Phase PR3 변경사항:
    - PENDING (초기) 상태 누락 문제 수정
    - CANCELLED 최종 취소 상태 추가 (기존 FAILED 혼재 제거)
    - CANCELING 은 사용자가 취소 요청했으나 아직 워커가 시작/종료 전인 전이 상태
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELING = "canceling"  # 전이 상태
    CANCELLED = "cancelled"  # 최종 취소 완료 상태

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