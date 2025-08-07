# app/models/cartoon_job.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class CartoonJob:
    """Firestore 'cartoon_jobs' 컬렉션의 문서 구조를 정의하는 데이터클래스."""
    job_id: str
    user_id: str
    status: str = 'processing' # 'processing', 'completed', 'failed'
    source_image_urls: List[str]
    source_text: str
    result_cartoon_url: str = None
    created_at: datetime = field(default_factory=datetime.now)

# cartoon_jobs 문서에 저장될 내용:

# job_id: 작업 고유 ID

# user_id: 요청한 사용자 ID

# status: 'processing', 'completed', 'failed' (작업 상태)

# source_image_urls: 만화로 만들 원본 이미지 URL 목록

# source_text: 사용자가 입력한 원본 텍스트

# result_cartoon_url: (작업 완료 후 채워짐) 완성된 만화 이미지 URL

# created_at: 의뢰 시간