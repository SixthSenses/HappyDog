# 클라이언트 증분값 전송 시 백엔드 수정 범위 분석

**날짜**: 2025-10-14  
**시나리오**: 클라이언트가 meal_count를 증분값(+1씩)으로 전송하는 경우  
**목표**: 백엔드에서 누적합을 계산하도록 수정하는 방안 분석

---

## 🔍 현재 아키텍처 분석

### 1. 데이터 흐름 (Data Flow)

```
클라이언트
    ↓ POST /api/pet-care/{pet_id}/records
    ↓ { "record_type": "meal_count", "data": 1, "timestamp": ... }
    ↓
routes.py (create_care_record)
    ↓
RecordIntegrationService.create_record_with_goals()
    ↓
PetCareRecordService.create_record()  [CRUD]
    ↓
FirestorePetCareRecordRepository.insert()
    ↓
Firestore: pet_care_logs/{log_id}
    {
        log_id: "uuid",
        pet_id: "pet123",
        record_type: "meal_count",
        data: 1,  ← 증분값 그대로 저장
        timestamp: DateTime,
        searchDate: "2025-10-14"
    }
```

### 2. 조회 흐름 (Query Flow)

```
GET /api/pet-care/{pet_id}/records/daily/summary?date=2025-10-14
    ↓
RecordIntegrationService.get_daily_summary_with_goals()
    ↓
QueryService.get_daily()
    ↓
Repository.list_by_date()
    ↓
Firestore Query: WHERE pet_id == "pet123" AND searchDate == "2025-10-14"
    ↓
반환: [
    { record_type: "meal_count", data: 1, timestamp: 09:00 },
    { record_type: "meal_count", data: 1, timestamp: 13:00 },
    { record_type: "meal_count", data: 1, timestamp: 18:00 }
]
    ↓
QueryService._summarize_daily()
    ↓ meal_count: Last value만 사용
    ↓
결과: meal_count = 1  ← ❌ 잘못된 결과 (3이어야 함)
```

### 3. 현재 코드의 가정

**파일**: `query_service.py` (Line 41-91)
```python
@staticmethod
def _summarize_daily(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize daily records by type.
    
    Logic:
    - meal_count: Last value (cumulative count throughout the day)  ← 가정: 누적값
    - activity: Total sum (multiple sessions should be added)        ← 합계
    - weight, bcs, stool, vomit: Last value (latest measurement)
    """
    for doc in rows:
        rtype = doc.get('record_type')
        val = doc.get('data')
        
        if rtype == 'meal_count':
            # Last value (cumulative)
            summary['meal_count'] = val  ← 마지막 값만 사용
```

**문제**: 클라이언트가 증분값(+1)을 보내면 `meal_count = 1`이 됨

---

## 🎯 3가지 구현 방안 비교

### 방안 1: **저장 시점 누적 (Write-Time Aggregation)** ⭐ 추천

#### 개념
클라이언트가 보낸 증분값을 **기록 생성 시** 기존 값에 더해서 저장

#### 장점
- ✅ **성능 최적화**: 조회 시 계산 불필요
- ✅ **데이터 정합성**: 저장 시점에 누적값 확정
- ✅ **기존 로직 유지**: `_summarize_daily()`와 `GoalAnalyzer` 수정 불필요
- ✅ **캐시 친화적**: 누적값이 이미 저장되어 있어 캐시 효율 높음

#### 단점
- ⚠️ **동시성 이슈**: 같은 날짜에 동시 요청 시 race condition 가능
- ⚠️ **트랜잭션 필요**: Firestore 트랜잭션 또는 Lock 필요

#### 구현 위치
**파일**: `services.py` (Line 14-22)

```python
def create_record(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a single pet care record."""
    try:
        # meal_count인 경우 증분값을 누적값으로 변환
        if record_data['record_type'] == 'meal_count':
            record_data = self._convert_meal_increment_to_cumulative(pet_id, record_data)
        
        result = self.repo.insert(pet_id, record_data)
        logging.info(f"펫케어 기록 생성됨: pet_id={pet_id}, type={record_data['record_type']}")
        return result
    except Exception as e:
        logging.error(f"펫케어 기록 생성 실패: {e}", exc_info=True)
        raise

def _convert_meal_increment_to_cumulative(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
    """증분값을 누적값으로 변환"""
    from app.utils.datetime_utils import DateTimeUtils
    
    # 같은 날짜의 기존 meal_count 기록 조회
    ts_ms = record_data['timestamp']
    ts_dt = DateTimeUtils.from_timestamp_ms(ts_ms)
    search_date = DateTimeUtils.to_kst_date_str(ts_dt)
    
    # QueryService를 사용하여 기존 기록 조회
    query_service = PetCareRecordQueryService(self.repo)
    existing_records = query_service.get_daily(pet_id, search_date, record_type='meal_count')
    
    # 기존 최대값 찾기
    current_max = 0
    for r in existing_records['records']:
        val = r.get('data')
        if isinstance(val, int) and val > current_max:
            current_max = val
    
    # 증분값 더하기
    increment = record_data['data']
    new_cumulative = current_max + increment
    
    # record_data 업데이트
    updated_data = record_data.copy()
    updated_data['data'] = new_cumulative
    
    logging.info(f"meal_count 변환: 증분 {increment} → 누적 {new_cumulative} (기존 최대: {current_max})")
    return updated_data
```

#### 동시성 문제 해결 (Firestore Transaction)
```python
def _convert_meal_increment_to_cumulative_safe(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
    """트랜잭션을 사용한 안전한 증분값 변환"""
    from firebase_admin import firestore
    
    db = self.repo.db
    if not db:
        # docs mode에서는 트랜잭션 없이 진행
        return self._convert_meal_increment_to_cumulative(pet_id, record_data)
    
    ts_ms = record_data['timestamp']
    ts_dt = DateTimeUtils.from_timestamp_ms(ts_ms)
    search_date = DateTimeUtils.to_kst_date_str(ts_dt)
    
    transaction = db.transaction()
    
    @firestore.transactional
    def update_in_transaction(transaction, pet_id, search_date, increment):
        # 트랜잭션 내에서 기존 최대값 조회
        query = (
            db.collection('pet_care_logs')
            .where('pet_id', '==', pet_id)
            .where('searchDate', '==', search_date)
            .where('record_type', '==', 'meal_count')
            .order_by('data', direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        docs = list(query.stream())
        current_max = docs[0].to_dict()['data'] if docs else 0
        new_cumulative = current_max + increment
        return new_cumulative
    
    increment = record_data['data']
    new_cumulative = update_in_transaction(transaction, pet_id, search_date, increment)
    
    updated_data = record_data.copy()
    updated_data['data'] = new_cumulative
    return updated_data
```

---

### 방안 2: **조회 시점 누적 (Read-Time Aggregation)**

#### 개념
데이터는 증분값 그대로 저장하고, **조회 시** 합계 계산

#### 장점
- ✅ **저장 단순**: 클라이언트가 보낸 값 그대로 저장
- ✅ **동시성 이슈 없음**: 각 기록이 독립적
- ✅ **히스토리 보존**: 각 식사 시간대별 증분값 추적 가능

#### 단점
- ⚠️ **성능 저하**: 조회할 때마다 합계 계산
- ⚠️ **복잡도 증가**: `_summarize_daily()`와 `GoalAnalyzer` 모두 수정 필요
- ⚠️ **일관성 문제**: activity는 합계, meal_count도 합계 → 로직 중복

#### 구현 위치
**파일**: `query_service.py` (Line 41-91)

```python
@staticmethod
def _summarize_daily(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize daily records by type.
    
    Logic:
    - meal_count: Total sum (각 식사마다 +1)  ← 변경
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
    
    # Accumulator for meal_count and activity
    meal_total = 0
    meal_found = False
    activity_total = 0
    activity_found = False
    
    for doc in rows:
        rtype = doc.get('record_type')
        val = doc.get('data')
        
        if rtype == 'meal_count':
            # Sum all meal increments  ← 변경
            if val is not None:
                try:
                    meal_total += int(val)
                    meal_found = True
                except (ValueError, TypeError):
                    pass
        elif rtype == 'activity':
            # Sum all activity sessions
            if val is not None:
                try:
                    activity_total += int(val)
                    activity_found = True
                except (ValueError, TypeError):
                    pass
        # ... 나머지 로직
    
    # Set totals
    if meal_found:
        summary['meal_count'] = meal_total
    if activity_found:
        summary['activity_minutes'] = activity_total
        
    return summary
```

**파일**: `analyzers.py` (Line 18)도 수정 필요

```python
def analyze_daily(self, rows: List[Dict[str, Any]], date: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    # meal_count = self._extract_last(rows, 'meal_count')  ← 제거
    meal_count = self._extract_total(rows, 'meal_count')  ← 변경 (activity와 동일)
    activity_minutes = self._extract_total(rows, 'activity')
    weight = self._extract_last(rows, 'weight')
    # ... 나머지 로직
```

---

### 방안 3: **집계 레이어 추가 (Aggregation Layer)** 🏗️ 대규모 시스템용

#### 개념
별도의 일별 집계 문서(예: `pet_care_daily_summary`)를 유지

#### 장점
- ✅ **최고 성능**: 조회 시 O(1) (집계 문서만 읽음)
- ✅ **확장성**: 수백만 기록도 빠르게 조회
- ✅ **통계 친화적**: 일별/주별/월별 집계 쉽게 구현

#### 단점
- ⚠️ **복잡도 대폭 증가**: 집계 문서 관리 로직 필요
- ⚠️ **일관성 문제**: 집계 문서와 원본 데이터 동기화
- ⚠️ **삭제/수정 처리**: 집계 문서 재계산 필요
- ⚠️ **오버엔지니어링**: 현재 규모에 과도함

#### 구조
```
Firestore Collections:
- pet_care_logs/{log_id}  ← 원본 데이터 (증분값)
- pet_care_daily_summary/{pet_id}_{date}  ← 집계 데이터
    {
        pet_id: "pet123",
        date: "2025-10-14",
        meal_count_total: 3,
        activity_minutes_total: 120,
        last_weight: 5.2,
        record_count: 8,
        updated_at: DateTime
    }
```

#### 구현 (간략)
```python
def create_record(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
    # 1. 원본 기록 저장
    result = self.repo.insert(pet_id, record_data)
    
    # 2. 집계 문서 업데이트 (트랜잭션)
    if record_data['record_type'] == 'meal_count':
        self._update_daily_summary(pet_id, search_date, 'meal_count', increment=record_data['data'])
    
    return result

def _update_daily_summary(self, pet_id: str, date: str, field: str, increment: int):
    """일별 집계 문서 업데이트"""
    summary_id = f"{pet_id}_{date}"
    summary_ref = self.repo.db.collection('pet_care_daily_summary').document(summary_id)
    
    # Firestore increment 사용
    summary_ref.set({
        'pet_id': pet_id,
        'date': date,
        f'{field}_total': firestore.Increment(increment),
        'updated_at': firestore.SERVER_TIMESTAMP
    }, merge=True)
```

---

## 📊 방안 비교표

| 항목 | 방안 1: 저장 시점 | 방안 2: 조회 시점 | 방안 3: 집계 레이어 |
|------|------------------|------------------|-------------------|
| **구현 복잡도** | ⭐⭐ 중간 | ⭐ 낮음 | ⭐⭐⭐⭐ 매우 높음 |
| **조회 성능** | ⭐⭐⭐ 우수 | ⭐⭐ 보통 (매번 계산) | ⭐⭐⭐⭐ 최고 (O(1)) |
| **저장 성능** | ⭐⭐ 보통 (조회 필요) | ⭐⭐⭐ 우수 | ⭐ 낮음 (2번 쓰기) |
| **동시성** | ⚠️ 트랜잭션 필요 | ✅ 문제 없음 | ⚠️ 트랜잭션 필요 |
| **데이터 정합성** | ⭐⭐⭐ 우수 | ⭐⭐⭐ 우수 | ⚠️ 동기화 필요 |
| **수정 범위** | 1개 파일 | 2개 파일 | 5개 이상 파일 |
| **히스토리 추적** | ⚠️ 증분값 소실 | ✅ 증분값 보존 | ✅ 원본 보존 |
| **캐시 효율** | ⭐⭐⭐ 우수 | ⭐⭐ 보통 | ⭐⭐⭐⭐ 최고 |
| **적합 규모** | 소~중규모 | 소규모 | 대규모 |

---

## ✅ 권장 방안: **방안 1 (저장 시점 누적)**

### 선택 이유
1. **현재 아키텍처와 잘 맞음**: `_summarize_daily()` 수정 불필요
2. **성능 우수**: 조회 시 계산 불필요, 캐시 효율 높음
3. **구현 범위 명확**: `services.py` 한 곳만 수정
4. **프로젝트 규모 적합**: 과도한 엔지니어링 아님

### 우려사항 해결
- **동시성 이슈**: Firestore Transaction 사용으로 해결
- **증분값 소실**: 필요 시 `original_increment` 필드 추가 저장 가능

---

## 🔧 상세 구현 계획 (방안 1)

### Phase 1: 기본 구현
**파일**: `pet_project_backend/app/api/pet_care/records/services.py`

#### 1.1 증분값 변환 메서드 추가
```python
from .query_service import PetCareRecordQueryService
from app.utils.datetime_utils import DateTimeUtils

class PetCareRecordService:
    def _convert_meal_increment_to_cumulative(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert meal_count increment to cumulative value.
        
        Args:
            pet_id: Pet identifier
            record_data: Record with increment value in 'data' field
            
        Returns:
            Updated record_data with cumulative value
        """
        # 타임스탬프에서 날짜 추출
        ts_ms = record_data['timestamp']
        ts_dt = DateTimeUtils.from_timestamp_ms(ts_ms)
        search_date = DateTimeUtils.to_kst_date_str(ts_dt)
        
        # 같은 날짜의 기존 meal_count 기록 조회
        query_service = PetCareRecordQueryService(self.repo)
        existing_records = query_service.get_daily(pet_id, search_date, record_type='meal_count')
        
        # 기존 최대값 찾기 (누적값이므로 최신 = 최대)
        current_max = 0
        for r in existing_records['records']:
            val = r.get('data')
            if isinstance(val, int) and val > current_max:
                current_max = val
        
        # 증분값을 누적값으로 변환
        increment = record_data['data']
        new_cumulative = current_max + increment
        
        # 원본 데이터 복사 및 업데이트
        updated_data = record_data.copy()
        updated_data['data'] = new_cumulative
        
        # 디버깅용 로그
        logging.info(f"meal_count 누적 변환: pet_id={pet_id}, date={search_date}, "
                    f"증분={increment}, 기존최대={current_max}, 새누적={new_cumulative}")
        
        # 선택사항: 원본 증분값 보존
        if increment != new_cumulative:
            updated_data['_original_increment'] = increment
        
        return updated_data
```

#### 1.2 create_record 메서드 수정
```python
def create_record(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a single pet care record. In DOCS_MODE returns echo payload with generated IDs."""
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
```

### Phase 2: 동시성 안전성 추가 (선택사항)

#### 2.1 Firestore Transaction 버전
```python
def _convert_meal_increment_to_cumulative_safe(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
    """Thread-safe version using Firestore transaction.
    
    Prevents race condition when multiple meal records are created simultaneously.
    """
    from firebase_admin import firestore
    
    db = self.repo.db
    if not db:
        # docs mode: 트랜잭션 없이 진행
        return self._convert_meal_increment_to_cumulative(pet_id, record_data)
    
    ts_ms = record_data['timestamp']
    ts_dt = DateTimeUtils.from_timestamp_ms(ts_ms)
    search_date = DateTimeUtils.to_kst_date_str(ts_dt)
    increment = record_data['data']
    
    # 트랜잭션 내에서 읽기-쓰기 수행
    @firestore.transactional
    def get_max_in_transaction(transaction, pet_id, search_date):
        query = (
            db.collection('pet_care_logs')
            .where('pet_id', '==', pet_id)
            .where('searchDate', '==', search_date)
            .where('record_type', '==', 'meal_count')
        )
        docs = [doc.to_dict() for doc in query.stream()]
        
        if not docs:
            return 0
        
        # 최대값 찾기
        return max(doc.get('data', 0) for doc in docs if isinstance(doc.get('data'), int))
    
    transaction = db.transaction()
    current_max = get_max_in_transaction(transaction, pet_id, search_date)
    new_cumulative = current_max + increment
    
    updated_data = record_data.copy()
    updated_data['data'] = new_cumulative
    
    logging.info(f"meal_count 트랜잭션 변환: pet_id={pet_id}, date={search_date}, "
                f"증분={increment}, 기존최대={current_max}, 새누적={new_cumulative}")
    
    return updated_data
```

**주의**: Firestore Transaction은 읽기 전용 쿼리만 지원하므로, 실제로는 Optimistic Locking 또는 분산 Lock 필요할 수 있음.

#### 2.2 간단한 대안: Retry 로직
```python
def _convert_meal_increment_to_cumulative_retry(self, pet_id: str, record_data: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """Simple retry logic for race condition handling."""
    import time
    
    for attempt in range(max_retries):
        try:
            return self._convert_meal_increment_to_cumulative(pet_id, record_data)
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"meal_count 변환 재시도 {attempt + 1}/{max_retries}: {e}")
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff
            else:
                raise
```

### Phase 3: 테스트 작성

#### 3.1 단위 테스트
```python
# tests/test_pet_care_meal_count.py
import pytest
from app.api.pet_care.records.services import PetCareRecordService
from app.api.pet_care.records.repository import InMemoryPetCareRecordRepository

def test_meal_count_increment_to_cumulative():
    """증분값이 누적값으로 변환되는지 테스트"""
    repo = InMemoryPetCareRecordRepository()
    service = PetCareRecordService(repo)
    
    pet_id = "test_pet"
    base_timestamp = 1697270400000  # 2023-10-14 09:00:00 KST
    
    # 첫 번째 식사: 증분 +1 → 누적 1
    record1 = service.create_record(pet_id, {
        'record_type': 'meal_count',
        'timestamp': base_timestamp,
        'data': 1,
        'memo': '아침'
    })
    assert record1['data'] == 1
    
    # 두 번째 식사: 증분 +1 → 누적 2
    record2 = service.create_record(pet_id, {
        'record_type': 'meal_count',
        'timestamp': base_timestamp + 4 * 3600 * 1000,  # +4시간
        'data': 1,
        'memo': '점심'
    })
    assert record2['data'] == 2
    
    # 세 번째 식사: 증분 +1 → 누적 3
    record3 = service.create_record(pet_id, {
        'record_type': 'meal_count',
        'timestamp': base_timestamp + 9 * 3600 * 1000,  # +9시간
        'data': 1,
        'memo': '저녁'
    })
    assert record3['data'] == 3

def test_meal_count_goal_analysis():
    """누적값 기반 목표 분석 테스트"""
    repo = InMemoryPetCareRecordRepository()
    service = PetCareRecordService(repo)
    
    # ... 테스트 로직
```

---

## 📋 수정 파일 목록

### ✏️ 수정 필요 (방안 1)
1. **`pet_project_backend/app/api/pet_care/records/services.py`**
   - `create_record()` 메서드 수정
   - `_convert_meal_increment_to_cumulative()` 메서드 추가
   - 예상 라인: +40줄

### 📝 테스트 추가
2. **`pet_project_backend/tests/test_pet_care_meal_count.py`** (신규)
   - 증분값 → 누적값 변환 테스트
   - 동시성 테스트 (선택)
   - 예상 라인: +100줄

### 📚 문서 업데이트
3. **`docs/api/pet_care.quick_reference.md`**
   - "올바른 방식" 섹션에 **증분값도 지원** 명시
4. **`docs/api/pet_care.meal_achievement_audit.md`**
   - "증분값 전송 시 백엔드가 자동 누적" 추가

---

## 🔄 하위 호환성 분석

### 기존 클라이언트 (누적값 전송)
```json
POST { "record_type": "meal_count", "data": 1 }  // 첫 식사
POST { "record_type": "meal_count", "data": 2 }  // 두번째
POST { "record_type": "meal_count", "data": 3 }  // 세번째
```

**문제**: 백엔드가 증분값으로 인식하여 `1 → 1+1=2 → 2+1=3` 계산 → 최종 `3`  
**결과**: ✅ **여전히 정상 작동** (우연히 같은 결과)

### 새 클라이언트 (증분값 전송)
```json
POST { "record_type": "meal_count", "data": 1 }  // +1
POST { "record_type": "meal_count", "data": 1 }  // +1
POST { "record_type": "meal_count", "data": 1 }  // +1
```

**처리**: 백엔드가 `0+1=1 → 1+1=2 → 2+1=3` 계산 → 최종 `3`  
**결과**: ✅ **정상 작동**

### ⚠️ 혼용 시나리오 (위험)
```json
POST { "data": 2 }  // 누적값 (기존 클라이언트)
POST { "data": 1 }  // 증분값 (새 클라이언트)
```

**처리**: 백엔드가 `0+2=2 → 2+1=3` 계산  
**결과**: ⚠️ **혼란 가능** (클라이언트가 혼용하면 안 됨)

### 해결 방안
1. **클라이언트 버전 통일**: 모든 클라이언트가 증분값 전송으로 통일
2. **명시적 플래그 추가** (선택):
   ```json
   {
       "record_type": "meal_count",
       "data": 1,
       "is_increment": true  ← 명시적 표시
   }
   ```
   백엔드에서 `is_increment` 확인 후 처리 결정

---

## ⏱️ 예상 작업 시간

| 작업 | 시간 | 비고 |
|------|------|------|
| Phase 1: 기본 구현 | 2시간 | 메서드 추가 + 테스트 |
| Phase 2: 동시성 처리 | 3시간 | 트랜잭션 또는 Retry |
| Phase 3: 테스트 작성 | 2시간 | 단위/통합 테스트 |
| 문서 업데이트 | 1시간 | API 문서 수정 |
| **총 예상 시간** | **8시간** | 1일 작업 |

---

## 🚀 배포 전략

### Step 1: 백엔드 배포 (하위 호환)
- Phase 1 구현 배포
- 기존 클라이언트(누적값)도 정상 작동
- 신규 클라이언트(증분값)도 정상 작동

### Step 2: 클라이언트 업데이트 (점진적)
- 안드로이드 앱: 증분값 전송으로 변경
- iOS 앱: 증분값 전송으로 변경
- 웹 앱: 증분값 전송으로 변경

### Step 3: 모니터링
- `meal_count` 기록의 `data` 값 분포 확인
- 목표 달성률 정확도 확인
- 성능 지표 (p50, p95, p99 latency)

### Step 4: 최적화 (필요 시)
- Phase 2 (트랜잭션) 적용
- 캐시 레이어 추가

---

## 📊 성능 영향 분석

### 현재 (누적값 전송)
```
POST /records
  └─ insert() → Firestore Write (1회)
  
GET /records/daily/summary
  └─ list_by_date() → Firestore Query (1회)
  └─ _summarize_daily() → 메모리 계산
```

### 방안 1 적용 후 (증분값 전송 + 저장 시점 변환)
```
POST /records
  ├─ list_by_date() → Firestore Query (1회 추가) ← 오버헤드
  ├─ _convert... → 메모리 계산
  └─ insert() → Firestore Write (1회)
  
GET /records/daily/summary
  └─ list_by_date() → Firestore Query (1회)
  └─ _summarize_daily() → 메모리 계산
```

**쓰기 성능**: +1 Query (약 50-100ms 추가)  
**읽기 성능**: 변화 없음 (동일)  
**전체 영향**: 쓰기 10% 느려지지만, 읽기는 유지 (읽기가 쓰기보다 많으므로 전체적으로 유리)

---

## ✅ 최종 권장 사항

### 1. **방안 1 채택** (저장 시점 누적)
- 구현 복잡도와 성능의 균형
- 현재 아키텍처와 잘 맞음

### 2. **Phase 1만 먼저 구현**
- 동시성 이슈는 실제 발생 시 Phase 2로 대응
- 사용자 수가 적으면 동시성 문제 거의 없음

### 3. **클라이언트 변경 점진적 적용**
- 백엔드 먼저 배포 (하위 호환)
- 클라이언트는 순차적으로 업데이트

### 4. **모니터링 강화**
- `meal_count` 값 분포 확인
- 이상값(100 이상 등) 탐지 알림

### 5. **문서화 필수**
- API 문서에 "증분값 전송 권장" 명시
- 예제 코드 제공

---

**다음 단계**: 
1. 이 분석 검토 및 승인
2. Phase 1 구현 시작
3. 테스트 환경에서 검증
4. 프로덕션 배포
