from __future__ import annotations
from typing import Any, Dict, List, Optional
from collections import defaultdict

from .repository import PetCareRecordRepository


class PetCareRecordQueryService:
    """Read-oriented service to build daily and range summaries.

    Keeps write service small and focused on commands.
    """

    def __init__(self, repo: PetCareRecordRepository):
        self.repo = repo

    def get_daily(self, pet_id: str, date: str, record_type: Optional[str] = None) -> Dict[str, Any]:
        rows = self.repo.list_by_date(pet_id, date)
        if record_type:
            rows = [r for r in rows if r.get('record_type') == record_type]
        summary = self._summarize_daily(rows)
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
        summary: Dict[str, Any] = {
            'meal_count': None,
            'activity_minutes': None,
            'weight': None,
            'bcs': None,
            'stool': None,
            'vomit': None,
        }
        for doc in rows:
            rtype = doc.get('record_type')
            val = doc.get('data')
            if rtype == 'meal_count':
                summary['meal_count'] = val
            elif rtype == 'activity':
                summary['activity_minutes'] = val
            elif rtype == 'weight':
                summary['weight'] = val
            elif rtype == 'bcs':
                summary['bcs'] = val
            elif rtype == 'stool':
                summary['stool'] = val
            elif rtype == 'vomit':
                summary['vomit'] = val
        return summary
