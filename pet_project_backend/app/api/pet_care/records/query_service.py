from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict

from .repository import PetCareRecordRepository

logger = logging.getLogger(__name__)


class PetCareRecordQueryService:
    """Read-oriented service to build daily and range summaries.

    Keeps write service small and focused on commands.
    """

    def __init__(self, repo: PetCareRecordRepository):
        self.repo = repo

    def get_daily(self, pet_id: str, date: str, record_type: Optional[str] = None) -> Dict[str, Any]:
        rows = self.repo.list_by_date(pet_id, date)
        logger.debug(f"PetCareRecordQueryService.get_daily: pet_id={pet_id}, date={date}, "
                    f"total_records={len(rows)}, filter_type={record_type}")
        if record_type:
            rows = [r for r in rows if r.get('record_type') == record_type]
        summary = self._summarize_daily(rows)
        logger.debug(f"Daily summary for {date}: {summary}")
        return {'date': date, 'records': rows, 'summary': summary}

    def get_range_grouped(self, pet_id: str, start_date: str, end_date: str) -> Dict[str, Any]:
        rows = self.repo.list_by_range(pet_id, start_date, end_date)
        by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in rows:
            by_date[r.get('searchDate', '')].append(r)
        meta = {}
        return {'records_by_date': dict(by_date), 'meta': meta}

    @staticmethod
    def _summarize_daily(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize daily records by type.
        
        Logic:
        - meal_count: Last value (cumulative count throughout the day)
        - activity: Total sum (multiple sessions should be added)
        - weight, bcs, stool, vomit: Last value (latest measurement)
        """
        summary: Dict[str, Any] = {
            'meal_count': None,
            'activity_minutes': None,
            'weight': None,
            'bcs': None,
            'stool': None,
            'vomit': None,
        }
        
        # Accumulator for activity (sum all sessions)
        activity_total = 0
        activity_found = False
        
        for doc in rows:
            rtype = doc.get('record_type')
            val = doc.get('data')
            
            if rtype == 'meal_count':
                # Last value (cumulative)
                summary['meal_count'] = val
            elif rtype == 'activity':
                # Sum all activity sessions
                if val is not None:
                    try:
                        activity_total += int(val)
                        activity_found = True
                    except (ValueError, TypeError):
                        pass  # Skip invalid values
            elif rtype == 'weight':
                # Last value
                summary['weight'] = val
            elif rtype == 'bcs':
                # Last value
                summary['bcs'] = val
            elif rtype == 'stool':
                # Last value
                summary['stool'] = val
            elif rtype == 'vomit':
                # Last value
                summary['vomit'] = val
        
        # Set activity_minutes to total if any activity was found
        if activity_found:
            summary['activity_minutes'] = activity_total
            
        return summary
