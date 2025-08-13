# app/models/analysis_history.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any

@dataclass
class AnalysisHistory:
    """
    Firestore 'analysis_history' 컬렉션의 문서 구조를 정의하는 데이터클래스.
    """
    analysis_id: str
    user_id: str
    pet_id: str
    analysis_type: str  # 'eye'
    image_url: str
    result: Dict[str, Any]
    raw_predictions: Dict[str, float]
    created_at: datetime = field(default_factory=datetime.utcnow)