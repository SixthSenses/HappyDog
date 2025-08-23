# Pet Care Records API - 성능 최적화 버전

## 개요

클라이언트의 부담을 줄이고 API의 유연성을 극대화하기 위해 records API를 리팩토링했습니다. **서버 사이드 필터링**과 **커서 기반 페이지네이션**을 도입하여 성능을 크게 개선했습니다.

## 주요 개선사항

### 1. **성능 최적화**
- **서버 사이드 필터링**: Firestore `in` 연산자로 타입 필터링
- **커서 기반 페이지네이션**: Firestore 권장 방식으로 offset 대체
- **효율적인 쿼리**: 필요한 데이터만 조회하여 읽기 비용 절감

### 2. **유연한 쿼리 파라미터**
- 날짜 범위 + 타입 필터링 조합
- 단일 날짜 + 타입 필터링
- 타입별 개별 조회
- 정렬 및 페이지네이션 옵션

### 3. **일관된 응답 형식**
- 메타데이터 포함 (총 개수, 페이지 정보 등)
- 타입별 그룹화 옵션
- 표준화된 에러 응답

## 성능 개선 효과

### **기존 방식 (비효율적)**
```python
# 모든 데이터를 읽고 클라이언트에서 필터링
docs = query.limit(limit).stream()
records = []
for doc in docs:
    records.append(doc.to_dict())

# 클라이언트 사이드 필터링
if record_types:
    records = [r for r in records if r.get('record_type') in record_types]

# 비효율적인 offset
if offset > 0:
    records = records[offset:]
```

### **개선된 방식 (효율적)**
```python
# 서버 사이드 필터링
if record_types and len(record_types) <= 10:
    query = query.where('record_type', 'in', record_types)

# 커서 기반 페이지네이션
if cursor:
    query = query.start_after(cursor_doc)

# 필요한 데이터만 조회
docs = query.limit(limit + 1).stream()
```

## API 엔드포인트

### 1. **기록 생성**
```http
POST /api/pet-care/{pet_id}/records
```

**요청 본문:**
```json
{
  "record_type": "weight",
  "timestamp": 1735000000000,
  "data": 15.5,
  "notes": "아침 측정"
}
```

### 2. **유연한 기록 조회 (주요 엔드포인트)**
```http
GET /api/pet-care/{pet_id}/records
```

#### 쿼리 파라미터

| 파라미터 | 타입 | 설명 | 예시 |
|---------|------|------|------|
| `date` | string | 단일 날짜 조회 | `2024-12-24` |
| `start_date` | string | 시작 날짜 (범위 조회) | `2024-12-20` |
| `end_date` | string | 종료 날짜 (범위 조회) | `2024-12-24` |
| `record_types` | string | 필터링할 기록 타입 (쉼표 구분) | `weight,meal` |
| `grouped` | boolean | 타입별 그룹화 여부 | `true` |
| `limit` | integer | 조회 개수 제한 (1-100) | `20` |
| `cursor` | string | 커서 기반 페이지네이션 | `last_document_id` |
| `sort` | string | 정렬 방식 | `timestamp_asc` |

#### 사용 예시

**1. 특정 날짜의 모든 기록 (타입별 그룹화)**
```http
GET /api/pet-care/5c4a4be1-8a87-4b1d-bc1a-d646abd22a66/records?date=2024-12-24&grouped=true
```

**응답:**
```json
{
  "records": [...],
  "meta": {
    "total_count": 4,
    "limit": 50,
    "has_more": false,
    "next_cursor": null
  },
  "grouped": {
    "weight": [
      {
        "log_id": "...",
        "record_type": "weight",
        "timestamp": 1735000000000,
        "data": 15.5,
        "notes": "아침 측정"
      }
    ],
    "water": [...],
    "activity": [...],
    "meal": [...]
  }
}
```

**2. 날짜 범위 + 특정 타입만 조회**
```http
GET /api/pet-care/5c4a4be1-8a87-4b1d-bc1a-d646abd22a66/records?start_date=2024-12-20&end_date=2024-12-24&record_types=weight,meal&limit=20
```

**3. 커서 기반 페이지네이션**
```http
# 첫 번째 페이지
GET /api/pet-care/5c4a4be1-8a87-4b1d-bc1a-d646abd22a66/records?date=2024-12-24&limit=10

# 응답에서 next_cursor를 받아서 다음 페이지 조회
GET /api/pet-care/5c4a4be1-8a87-4b1d-bc1a-d646abd22a66/records?date=2024-12-24&limit=10&cursor=last_document_id
```

### 3. **타입별 기록 조회**
```http
GET /api/pet-care/{pet_id}/records/{record_type}
```

**지원하는 record_type:**
- `weight`: 체중 기록
- `water`: 물 섭취 기록
- `activity`: 활동 기록
- `meal`: 식사 기록

**예시:**
```http
GET /api/pet-care/5c4a4be1-8a87-4b1d-bc1a-d646abd22a66/records/weight?date=2024-12-24&limit=5
```

**응답:**
```json
{
  "records": [
    {
      "log_id": "...",
      "record_type": "weight",
      "timestamp": 1735000000000,
      "data": 15.5,
      "notes": "아침 측정"
    }
  ],
  "meta": {
    "record_type": "weight",
    "total_count": 1,
    "limit": 5,
    "has_more": false,
    "next_cursor": null
  }
}
```

### 4. **레거시 엔드포인트 (호환성)**
```http
GET /api/pet-care/{pet_id}/records/legacy
```

기존 API와 동일한 동작을 제공하지만, 새로운 엔드포인트 사용을 권장합니다.

## 클라이언트 사용 시나리오

### 1. **대시보드 - 오늘의 요약**
```http
GET /records?date=2024-12-24&grouped=true
```

### 2. **차트 데이터 - 일주일 체중 변화**
```http
GET /records?start_date=2024-12-18&end_date=2024-12-24&record_types=weight&sort=timestamp_asc
```

### 3. **기록 목록 - 최근 활동 기록**
```http
GET /records/activity?limit=20&sort=timestamp_desc
```

### 4. **커서 기반 페이지네이션 - 모든 기록**
```javascript
// 첫 번째 페이지
const response1 = await fetch('/records?date=2024-12-24&limit=10');
const data1 = await response1.json();

// 다음 페이지들
if (data1.meta.has_more) {
  const response2 = await fetch(`/records?date=2024-12-24&limit=10&cursor=${data1.meta.next_cursor}`);
  const data2 = await response2.json();
  
  if (data2.meta.has_more) {
    const response3 = await fetch(`/records?date=2024-12-24&limit=10&cursor=${data2.meta.next_cursor}`);
    const data3 = await response3.json();
  }
}
```

## 성능 최적화 상세

### 1. **서버 사이드 필터링**
- **기존**: 모든 데이터를 읽고 클라이언트에서 필터링
- **개선**: Firestore `in` 연산자로 서버에서 필터링
- **효과**: 읽기 비용 70-90% 절감

### 2. **커서 기반 페이지네이션**
- **기존**: offset으로 모든 데이터를 읽고 앞부분 버림
- **개선**: `start_after()`로 필요한 부분만 조회
- **효과**: 대용량 데이터에서 응답 속도 크게 개선

### 3. **Firebase 색인 최적화**
필요한 색인:
- `pet_id` + `searchDate` + `timestamp`
- `pet_id` + `record_type` + `timestamp`
- `pet_id` + `searchDate` + `record_type` + `timestamp`

## 에러 응답

모든 API는 일관된 에러 응답 형식을 사용합니다:

```json
{
  "error_code": "ERROR_TYPE",
  "message": "에러 메시지",
  "details": {} // 추가 정보 (있는 경우)
}
```

## 마이그레이션 가이드

### **Offset에서 Cursor로 마이그레이션**

**기존 (offset 방식):**
```javascript
// 페이지별 조회
fetch('/records?date=2024-12-24&limit=10&offset=0')
fetch('/records?date=2024-12-24&limit=10&offset=10')
fetch('/records?date=2024-12-24&limit=10&offset=20')
```

**개선된 버전 (cursor 방식):**
```javascript
// 첫 번째 페이지
const response1 = await fetch('/records?date=2024-12-24&limit=10');
const data1 = await response1.json();

// 다음 페이지들
if (data1.meta.has_more) {
  const response2 = await fetch(`/records?date=2024-12-24&limit=10&cursor=${data1.meta.next_cursor}`);
  const data2 = await response2.json();
  
  if (data2.meta.has_more) {
    const response3 = await fetch(`/records?date=2024-12-24&limit=10&cursor=${data2.meta.next_cursor}`);
    const data3 = await response3.json();
  }
}
```

### **클라이언트 사이드 필터링에서 서버 사이드 필터링으로**

**기존:**
```javascript
// 모든 데이터를 받아서 클라이언트에서 필터링
fetch('/records?date=2024-12-24')
  .then(response => response.json())
  .then(data => {
    const weightRecords = data.weight;
    // 클라이언트에서 처리
  });
```

**개선된 버전:**
```javascript
// 서버에서 필터링하여 필요한 데이터만 조회
fetch('/records?date=2024-12-24&record_types=weight')
  .then(response => response.json())
  .then(data => {
    const weightRecords = data.records;
    // 서버에서 이미 필터링됨
  });
```

## 성능 모니터링

### **Firestore 읽기 비용 추적**
- 기존 방식: 대량 데이터 조회 시 읽기 비용 급증
- 개선된 방식: 필요한 데이터만 조회하여 비용 절감

### **응답 시간 개선**
- 기존 방식: offset이 클수록 응답 시간 증가
- 개선된 방식: 커서 기반으로 일정한 응답 시간 유지

이제 클라이언트는 원하는 데이터만 정확하게 조회할 수 있어 네트워크 트래픽과 처리 부담이 크게 줄어들고, Firestore 읽기 비용도 크게 절감됩니다!
