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
        """Create a single pet care record. In DOCS_MODE returns echo payload with generated IDs.
        
        For meal_count records, supports both increment (+1 per meal) and cumulative (1, 2, 3...) values.
        Increment values are automatically converted to cumulative before storage.
        """
        try:
            # meal_count인 경우 증분값을 누적값으로 변환
            if record_data.get('record_type') == 'meal_count':
                record_data = self._convert_meal_increment_to_cumulative(pet_id, record_data)
            
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

    def _convert_meal_increment_to_cumulative(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert meal_count increment value to cumulative value.
        
        Supports both client patterns:
        - Increment: client sends +1 per meal (1, 1, 1) → backend converts to (1, 2, 3)
        - Cumulative: client sends cumulative (1, 2, 3) → backend stores as-is
        
        Args:
            pet_id: Pet identifier
            record_data: Record with increment or cumulative value in 'data' field
            
        Returns:
            Updated record_data with cumulative value in 'data' field
            
        Note:
            This method queries existing records for the same date to find the current
            maximum value, then adds the increment. This ensures both patterns work correctly:
            - Pure increment: 0+1=1, 1+1=2, 2+1=3
            - Pure cumulative: 0+1=1, 1+1=2, 2+1=3 (same result by coincidence)
        """
        from app.utils.datetime_utils import DateTimeUtils
        
        try:
            # 타임스탬프에서 KST 날짜 추출
            ts_ms = record_data['timestamp']
            ts_dt = DateTimeUtils.from_timestamp_ms(ts_ms)
            search_date = DateTimeUtils.to_kst_date_str(ts_dt)
            
            # 같은 날짜의 기존 meal_count 기록 조회
            query_service = PetCareRecordQueryService(self.repo)
            existing_result = query_service.get_daily(pet_id, search_date, record_type='meal_count')
            existing_records = existing_result.get('records', [])
            
            # 기존 최대값 찾기 (누적값이므로 최신 = 최대)
            current_max = 0
            for r in existing_records:
                val = r.get('data')
                if isinstance(val, int) and val > current_max:
                    current_max = val
            
            # 증분값을 누적값으로 변환
            increment = record_data['data']
            new_cumulative = current_max + increment
            
            # record_data 복사 및 업데이트 (원본 변경 방지)
            updated_data = record_data.copy()
            updated_data['data'] = new_cumulative
            
            # 디버깅 로그 (운영 환경에서는 info 레벨)
            logging.info(f"meal_count 누적 변환: pet_id={pet_id}, date={search_date}, "
                        f"증분={increment}, 기존최대={current_max}, 새누적={new_cumulative}")
            
            return updated_data
            
        except Exception as e:
            logging.error(f"meal_count 변환 실패: pet_id={pet_id}, error={e}", exc_info=True)
            # 변환 실패 시 원본 데이터 반환 (fail-safe)
            logging.warning(f"meal_count 변환 실패로 원본 데이터 사용: data={record_data.get('data')}")
            return record_data
