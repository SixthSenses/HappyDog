"""Pagination Regression Tests (Sprint A/B)\n=======================================\n단위 수준에서 V2 서비스 페이지네이션 핵심 규칙 검증.\nFirestore 의존성을 직접 호출하지 않고 서비스 메서드 단위 모킹.\n"""
from datetime import datetime, timedelta, timezone

import pytest

from app.api.pet_care.records.services_v2 import PetCareRecordServiceV2


class DummyDoc:
    def __init__(self, id_, data):
        self.id = id_
        self._data = data
    def to_dict(self):
        return self._data


class DummyQuery:
    def __init__(self, docs):
        self._docs = docs
    def where(self, *a, **k):
        return self
    def order_by(self, *a, **k):
        return self
    def start_after(self, *a, **k):
        # 단순히 skip 구현 (테스트에서 커서 id 기반)
        if a and hasattr(a[0], 'id'):
            found = False
            new_docs = []
            for d in self._docs:
                if found:
                    new_docs.append(d)
                if d.id == a[0].id:
                    found = True
            self._docs = new_docs
        return self
    def limit(self, n):
        return DummyStream(self._docs[:n])

class DummyStream:
    def __init__(self, docs):
        self._docs = docs
    def stream(self):
        for d in self._docs:
            yield d


class DummyV1:
    def __init__(self, docs):
        self.logs_ref = DummyLogsRef(docs)

class DummyLogsRef:
    def __init__(self, docs):
        self._docs = docs  # list[DummyDoc]
    def where(self, *a, **k):
        return DummyQuery(self._docs.copy())
    def document(self, id_):
        for d in self._docs:
            if d.id == id_:
                return d
        class _NF:
            exists = False
        return _NF()


def _make_docs(count: int, date: str):
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    docs = []
    for i in range(count):
        ts = base + timedelta(minutes=i)
        docs.append(DummyDoc(f"doc{i}", {
            'log_id': f"doc{i}",
            'pet_id': 'p1',
            'record_type': 'water',
            'timestamp': ts,
            'searchDate': date,
            'data': i
        }))
    return docs


def test_daily_pagination_cross_page_ordering():
    docs = _make_docs(25, '2025-09-09')
    svc = PetCareRecordServiceV2(DummyV1(docs))
    first = svc.get_daily_v2('p1', '2025-09-09', limit=10)
    assert len(first['data']['water']) == 10
    assert first['meta']['has_more'] is True
    c1 = first['meta']['next_cursor']
    second = svc.get_daily_v2('p1', '2025-09-09', limit=10, cursor=c1)
    assert len(second['data']['water']) == 10
    ids_first = [d['log_id'] for d in first['data']['water']]
    ids_second = [d['log_id'] for d in second['data']['water']]
    assert set(ids_first).isdisjoint(ids_second)  # no overlap
    third = svc.get_daily_v2('p1', '2025-09-09', limit=10, cursor=second['meta']['next_cursor'])
    # 남은 5개만
    assert len(third['data']['water']) == 5
    assert third['meta']['has_more'] is False
    assert third['meta']['next_cursor'] is None


def test_range_pagination_last_page_cursor_none():
    # 두 날짜에 12개 (각 6개) -> limit 7 사용
    docs = _make_docs(6, '2025-09-08') + _make_docs(6, '2025-09-09')
    svc = PetCareRecordServiceV2(DummyV1(docs))
    first = svc.get_range_v2('p1', '2025-09-08', '2025-09-09', limit=7)
    assert first['meta']['has_more'] is True
    c1 = first['meta']['next_cursor']
    second = svc.get_range_v2('p1', '2025-09-08', '2025-09-09', limit=7, cursor=c1)
    assert second['meta']['has_more'] is False
    assert second['meta']['next_cursor'] is None