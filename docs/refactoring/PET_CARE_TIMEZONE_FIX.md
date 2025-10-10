# 펫케어 기록 타임존 문제 해결

## 문제 상황

**증상:**
- 프론트엔드에서 10월 10일 00:48 (KST)에 기록을 생성
- Firestore에 저장된 데이터:
  - `timestamp`: 2025-10-10T00:48:07+09:00 (정상)
  - `searchDate`: "2025-10-09" (잘못됨 - 하루 전)

**원인:**
```python
# 기존 코드 (repository.py)
ts_dt = DateTimeUtils.from_timestamp_ms(ts_ms)  # UTC로 변환 → 10월 9일 15:48 UTC
search_date = DateTimeUtils.to_date_str(ts_dt)  # UTC 날짜 추출 → "2025-10-09"
```

프론트엔드에서 보낸 timestamp(ms)를 UTC datetime으로 변환 후, UTC 기준으로 날짜를 추출했기 때문에 **KST 기준 날짜와 9시간 차이**가 발생했습니다.

## 해결 방안

### 1. DateTimeUtils 개선

**추가된 상수 및 함수:**

```python
# app/utils/datetime_utils.py

# KST timezone 정의
KST_OFFSET = timedelta(hours=9)  # UTC+9
KST = timezone(KST_OFFSET, name='KST')

@staticmethod
def today_kst() -> date:
    """오늘 날짜를 KST(한국 시간) 기준으로 반환"""
    return datetime.now(KST).date()

@staticmethod
def today_kst_as_date_str() -> str:
    """오늘 날짜를 KST 기준 YYYY-MM-DD 문자열로 반환"""
    return DateTimeUtils.today_kst().strftime('%Y-%m-%d')

@staticmethod
def to_kst_date(dt: datetime) -> date:
    """
    UTC datetime을 KST(한국 시간) 기준 date로 변환
    
    Example:
        >>> utc_dt = datetime(2025, 10, 9, 15, 48, 0, tzinfo=timezone.utc)
        >>> DateTimeUtils.to_kst_date(utc_dt)
        date(2025, 10, 10)  # KST 기준으로 10월 10일
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    kst_dt = dt.astimezone(KST)
    return kst_dt.date()

@staticmethod
def to_kst_date_str(dt: datetime) -> str:
    """
    UTC datetime을 KST 기준 YYYY-MM-DD 문자열로 변환
    
    Example:
        >>> utc_dt = datetime(2025, 10, 9, 15, 48, 0, tzinfo=timezone.utc)
        >>> DateTimeUtils.to_kst_date_str(utc_dt)
        "2025-10-10"
    """
    kst_date = DateTimeUtils.to_kst_date(dt)
    return DateTimeUtils.to_date_string(kst_date)
```

### 2. Repository 수정

**변경 전:**
```python
ts_dt = DateTimeUtils.from_timestamp_ms(ts_ms)
search_date = DateTimeUtils.to_date_str(ts_dt)  # UTC 기준
```

**변경 후:**
```python
ts_dt = DateTimeUtils.from_timestamp_ms(ts_ms)
# searchDate는 KST 기준으로 생성 (사용자가 기록한 날짜와 일치)
search_date = DateTimeUtils.to_kst_date_str(ts_dt)  # KST 기준
```

**영향받는 파일:**
- `app/api/pet_care/records/repository.py` - `insert()` 메서드

## 동작 예시

### Before (문제 상황)
```python
# 프론트엔드에서 전송
timestamp_ms = 1728492487000  # 2025-10-10T00:48:07+09:00 (KST)

# 백엔드 처리 (기존)
ts_dt = from_timestamp_ms(1728492487000)  
# → 2025-10-09T15:48:07+00:00 (UTC)

search_date = to_date_str(ts_dt)  
# → "2025-10-09" (UTC 날짜)

# 결과: timestamp와 searchDate 날짜 불일치
```

### After (해결)
```python
# 프론트엔드에서 전송
timestamp_ms = 1728492487000  # 2025-10-10T00:48:07+09:00 (KST)

# 백엔드 처리 (수정)
ts_dt = from_timestamp_ms(1728492487000)  
# → 2025-10-09T15:48:07+00:00 (UTC)

search_date = to_kst_date_str(ts_dt)  
# → "2025-10-10" (KST 날짜)

# 결과: timestamp와 searchDate 날짜 일치
```

## 데이터 일관성

### 신규 데이터
- ✅ 이제부터 생성되는 모든 기록은 KST 기준 searchDate를 가짐
- ✅ 프론트엔드와 백엔드 날짜 인식 일치

### 기존 데이터
**영향 범위:**
- 2025년 10월 9일 00:00~08:59 (KST) 사이에 생성된 기록들
- 이 시간대의 기록들은 searchDate가 하루 전으로 저장되어 있음

**마이그레이션 필요 여부:**
- 데이터 양이 적고 기간이 짧으면: **마이그레이션 불필요** (자연스럽게 새 데이터로 대체)
- 프로덕션 데이터가 많으면: 아래 마이그레이션 스크립트 실행 권장

**마이그레이션 스크립트 (필요시):**
```python
# scripts/migrate_pet_care_searchdate.py
from google.cloud import firestore
from app.utils.datetime_utils import DateTimeUtils

def migrate_searchdate():
    """기존 펫케어 기록의 searchDate를 KST 기준으로 재계산"""
    db = firestore.Client()
    logs_ref = db.collection('pet_care_logs')
    
    # 2025-10-01 이후 데이터만 마이그레이션
    query = logs_ref.where('searchDate', '>=', '2025-10-01')
    
    batch = db.batch()
    count = 0
    
    for doc in query.stream():
        data = doc.to_dict()
        timestamp = data.get('timestamp')
        
        if timestamp:
            # KST 기준으로 searchDate 재계산
            ts_dt = timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp
            new_search_date = DateTimeUtils.to_kst_date_str(ts_dt)
            
            if new_search_date != data.get('searchDate'):
                batch.update(doc.reference, {'searchDate': new_search_date})
                count += 1
                print(f"Updated {doc.id}: {data.get('searchDate')} -> {new_search_date}")
        
        # Firestore batch limit: 500
        if count % 500 == 0 and count > 0:
            batch.commit()
            batch = db.batch()
    
    if count % 500 != 0:
        batch.commit()
    
    print(f"Total migrated: {count} records")

if __name__ == '__main__':
    migrate_searchdate()
```

## Firestore 쿼리 영향

**쿼리 방식 변경 없음:**
```python
# 기존과 동일하게 작동
query = logs_ref.where('pet_id', '==', pet_id) \
               .where('searchDate', '==', date) \
               .order_by('timestamp', direction=firestore.Query.DESCENDING)
```

**복합 인덱스:**
- 기존 인덱스 그대로 사용 가능
- `pet_id` + `searchDate` + `timestamp` 인덱스

## 장기 개선 방안

### 현재 해결 (Phase 1) ✅
- 백엔드에서 KST 기준 searchDate 생성
- API 스키마 변경 없음
- 빠른 적용 가능

### 향후 개선 (Phase 2) - 선택사항
프론트엔드에서 명시적으로 날짜 정보를 전송하는 방식:

```python
# 스키마 개선안
class CareRecordCreateSchema(Schema):
    record_type = fields.Str(required=True)
    timestamp = fields.Int(required=True)  # Unix timestamp (ms)
    date = fields.Str(required=True)  # YYYY-MM-DD (클라이언트 로컬 날짜)
    data = fields.Raw(required=True)
    memo = fields.Str(required=False)
```

**장점:**
- 타임존 변환 오류 완전 제거
- 서버에서 타임존 계산 불필요
- 명확한 의도 전달

**단점:**
- API 변경 필요
- 프론트엔드 수정 필요
- 기존 클라이언트 호환성 처리 필요

## 테스트 케이스

```python
# tests/test_pet_care_timezone.py
import pytest
from datetime import datetime, timezone
from app.utils.datetime_utils import DateTimeUtils

def test_kst_date_conversion():
    """KST 날짜 변환이 올바르게 작동하는지 확인"""
    # 10월 9일 15:48 UTC = 10월 10일 00:48 KST
    utc_dt = datetime(2025, 10, 9, 15, 48, 7, tzinfo=timezone.utc)
    
    # UTC 기준 날짜 추출 (기존 방식)
    utc_date_str = DateTimeUtils.to_date_str(utc_dt.date())
    assert utc_date_str == "2025-10-09"
    
    # KST 기준 날짜 추출 (새 방식)
    kst_date_str = DateTimeUtils.to_kst_date_str(utc_dt)
    assert kst_date_str == "2025-10-10"

def test_boundary_cases():
    """경계 케이스 테스트"""
    # 자정 직전 (UTC 기준 전날)
    utc_dt1 = datetime(2025, 10, 9, 14, 59, 59, tzinfo=timezone.utc)
    assert DateTimeUtils.to_kst_date_str(utc_dt1) == "2025-10-09"  # KST 23:59:59
    
    # 자정 (UTC 기준 전날, KST 기준 당일)
    utc_dt2 = datetime(2025, 10, 9, 15, 0, 0, tzinfo=timezone.utc)
    assert DateTimeUtils.to_kst_date_str(utc_dt2) == "2025-10-10"  # KST 00:00:00
    
    # 오전 9시 직전 (UTC와 KST 날짜 다름)
    utc_dt3 = datetime(2025, 10, 10, 14, 59, 59, tzinfo=timezone.utc)
    assert DateTimeUtils.to_kst_date_str(utc_dt3) == "2025-10-10"  # KST 23:59:59
    
    # 오전 9시 (UTC와 KST 날짜 같음)
    utc_dt4 = datetime(2025, 10, 10, 15, 0, 0, tzinfo=timezone.utc)
    assert DateTimeUtils.to_kst_date_str(utc_dt4) == "2025-10-11"  # KST 00:00:00
```

## 영향받는 도메인

### ✅ 직접 영향
- **펫케어 기록 (pet_care_logs)**: searchDate 생성 로직 수정됨

### 🔍 검토 필요
다른 도메인에서도 `to_date_str()` 사용 여부 확인:

```bash
# 전체 프로젝트에서 to_date_str 사용 검색
grep -r "to_date_str\|to_date_string" pet_project_backend/app/
```

**확인 결과:**
- 대부분 API 응답의 기본값(`today_kst_as_date_str()`)으로 사용
- 비즈니스 로직에는 거의 사용되지 않음
- 추가 수정 불필요

## 배포 체크리스트

- [x] `DateTimeUtils`에 KST 변환 함수 추가
- [x] `repository.py`에서 `to_kst_date_str()` 사용
- [x] 단위 테스트 작성 (권장)
- [ ] 기존 데이터 마이그레이션 (선택사항)
- [ ] 프론트엔드 팀에 변경사항 공유
- [ ] 프로덕션 배포 후 신규 데이터 검증

## 참고사항

**타임존 정책:**
- Firestore `timestamp` 필드: **UTC 저장** (변경 없음)
- `searchDate` 필드: **KST 기준 날짜 문자열** (변경됨)
- 프론트엔드 표시: 클라이언트 로컬 타임존 (프론트 책임)

**Firebase Security Rules:**
- searchDate 필터링은 그대로 작동
- 날짜 기반 쿼리 성능 영향 없음

**주의사항:**
- 다른 국가 서비스 확장 시 타임존 정책 재검토 필요
- 현재는 한국 시장 전용으로 KST 하드코딩 허용

---

**문서 작성일:** 2025-10-10  
**작성자:** GitHub Copilot  
**관련 이슈:** 펫케어 기록 searchDate 타임존 불일치
