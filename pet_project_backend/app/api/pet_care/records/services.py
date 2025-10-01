# app/api/pet_care/records/services.py
import logging
from typing import Any, Dict
from .repository import PetCareRecordRepository, FirestorePetCareRecordRepository
from .query_service import PetCareRecordQueryService

class PetCareRecordService:
    """Command-oriented service handling CRUD only. Read models are in PetCareRecordQueryService."""

    def __init__(self, repo: PetCareRecordRepository):
        self.repo = repo
        logging.info("PetCareRecordService initialized with repository: %s", type(repo).__name__)

    def create_record(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single pet care record. In DOCS_MODE returns echo payload with generated IDs."""
        try:
            result = self.repo.insert(pet_id, record_data)
            logging.info(f"펫케어 기록 생성됨: pet_id={pet_id}, type={record_data['record_type']}")
            return result
        except Exception as e:
            logging.error(f"펫케어 기록 생성 실패: {e}", exc_info=True)
            raise

    def update_record(self, pet_id: str, log_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing record. In DOCS_MODE returns placeholder synthetic data."""
        try:
            result = self.repo.update(pet_id, log_id, update_data)
            logging.info(f"펫케어 기록 수정됨: pet_id={pet_id}, log_id={log_id}")
            return result
        except Exception as e:
            logging.error(f"펫케어 기록 수정 실패: {e}", exc_info=True)
            raise

    def delete_record(self, pet_id: str, log_id: str) -> None:
        """Delete a pet care record. No-op in DOCS_MODE."""
        try:
            self.repo.delete(pet_id, log_id)
            logging.info(f"펫케어 기록 삭제됨: pet_id={pet_id}, log_id={log_id}")
        except Exception as e:
            logging.error(f"펫케어 기록 삭제 실패: {e}", exc_info=True)
            raise

    def get_daily_records(self, pet_id: str, date: str) -> Dict[str, Any]:
        """Fetch all records for a date. In DOCS_MODE returns empty list & null summary fields."""
        # Backward compatibility: delegate to query service
        try:
            query = PetCareRecordQueryService(self.repo)
            result = query.get_daily(pet_id, date)
            logging.info(f"일별 펫케어 기록 조회됨: pet_id={pet_id}, date={date}, count={len(result.get('records', []))}")
            return result
        except Exception as e:
            logging.error(f"일별 펫케어 기록 조회 실패: {e}", exc_info=True)
            raise
