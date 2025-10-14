# Pet Care Domain - Critical Fixes Verification
# 수정일: 2025-10-14

## 문제 요약

### 1. Daily Records API의 summary 불일치
**문제**: 같은 타입의 기록이 여러 개 있을 때 마지막 값만 표시됨
- **예시**: activity 기록 3개(30분, 30분, 30분)가 있을 때
- **기대값**: `summary.activity_minutes = 90`
- **실제값**: `summary.activity_minutes = 30` (마지막 값만)

### 2. Daily Summary API의 actual 값 0 문제
**문제**: 실제 기록이 있음에도 goal_progress.achievements.activity.actual이 0으로 표시됨

## 근본 원인 분석

### 원인 1: query_service._summarize_daily() 로직 오류
```python
# 기존 코드 (잘못됨)
elif rtype == 'activity':
    summary['activity_minutes'] = val  # 덮어쓰기 - 마지막 값만 남음
```

**activity는 여러 세션의 합계**여야 하는데 단순 할당으로 인해 **마지막 값만 유지**됨

### 원인 2: 집계 방식의 불일치
- **Daily Records**: 마지막 값만 표시 (잘못됨)
- **Goal Analysis**: 합계로 계산 (올바름)
- 결과: 두 API가 서로 다른 값을 반환

## 수정 사항

### 1. query_service.py - _summarize_daily() 수정
```python
# 수정된 로직
activity_total = 0
activity_found = False

for doc in rows:
    if rtype == 'activity':
        if val is not None:
            try:
                activity_total += int(val)
                activity_found = True
            except (ValueError, TypeError):
                pass

if activity_found:
    summary['activity_minutes'] = activity_total
```

**변경점**:
- activity 타입: 단순 할당 → **합계 계산**
- meal_count: 마지막 값 유지 (누적 카운트이므로 올바름)
- weight, bcs, stool, vomit: 마지막 값 유지 (최신 측정값이므로 올바름)

### 2. analyzers.py - _extract_total() 안전성 개선
```python
@staticmethod
def _extract_total(rows: List[Dict[str, Any]], rtype: str):
    total = 0
    found = False
    for r in rows:
        if r.get('record_type') == rtype:
            val = r.get('data')
            if val is not None:
                try:
                    total += int(val)
                    found = True
                except (ValueError, TypeError):
                    continue
    return total if found else None
```

**개선점**:
- None 값 안전 처리
- 유효하지 않은 값 스킵
- 기록이 없을 때 None 반환 (0 대신)

### 3. 로깅 추가
- query_service: 조회된 기록 수와 summary 결과 로깅
- analyzers: 추출된 값과 목표 분석 결과 로깅

## 테스트 시나리오

### 시나리오 1: 3회 활동 기록 (각 30분)
**API 호출**:
```
GET /api/pet-care/{pet_id}/records/daily?date=2025-10-14
```

**기대 결과**:
```json
{
  "date": "2025-10-14",
  "records": [
    {"record_type": "activity", "data": 30, ...},
    {"record_type": "activity", "data": 30, ...},
    {"record_type": "activity", "data": 30, ...}
  ],
  "summary": {
    "activity_minutes": 90,  // ← 수정 전: 30, 수정 후: 90
    "meal_count": null,
    "weight": null,
    "bcs": null,
    "stool": null,
    "vomit": null
  }
}
```

### 시나리오 2: 목표 진행률 조회
**API 호출**:
```
GET /api/pet-care/{pet_id}/records/daily/summary?date=2025-10-14
```

**기대 결과**:
```json
{
  "date": "2025-10-14",
  "records": [...],
  "record_counts": {"activity": 3},
  "meta": {
    "activity_minutes": 90  // ← 수정 전: 30, 수정 후: 90
  },
  "goal_progress": {
    "date": "2025-10-14",
    "achievements": {
      "activity": {
        "actual": 90,  // ← 수정 전: 0 또는 30, 수정 후: 90
        "goal": 120,
        "percentage": 75.0,
        "achieved": false,
        "detail": {
          "sessions": 4,
          "minutes_per_session": 30,
          "derived_goal_minutes": 120
        }
      }
    }
  }
}
```

### 시나리오 3: 혼합 기록 (식사 + 활동 + 체중)
**데이터**:
- 식사: 1회 → 2회 → 3회 (누적)
- 활동: 20분 + 30분 + 25분
- 체중: 5.2kg → 5.3kg (최신)

**기대 결과**:
```json
{
  "summary": {
    "meal_count": 3,          // 마지막 누적 값
    "activity_minutes": 75,   // 합계 (20+30+25)
    "weight": 5.3             // 최신 측정값
  }
}
```

## 검증 방법

### 1. 로그 확인
```bash
# 디버그 로그 활성화
export FLASK_ENV=development

# 앱 실행 후 로그 확인
tail -f app.log | grep -E "PetCareRecordQueryService|GoalAnalyzer"
```

**기대 로그**:
```
DEBUG:PetCareRecordQueryService.get_daily: pet_id=xxx, date=2025-10-14, total_records=3
DEBUG:Daily summary for 2025-10-14: {'activity_minutes': 90, 'meal_count': None, ...}
DEBUG:GoalAnalyzer.analyze_daily for 2025-10-14: activity_minutes=90, total_records=3
```

### 2. API 테스트 (curl 예제)
```bash
# 1. 활동 기록 3회 생성
curl -X POST http://localhost:5000/api/pet-care/{pet_id}/records \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"record_type":"activity","data":30,"timestamp":1728900000000}'

# 2. Daily Records 조회
curl http://localhost:5000/api/pet-care/{pet_id}/records/daily?date=2025-10-14 \
  -H "Authorization: Bearer {token}"

# 3. Daily Summary 조회
curl http://localhost:5000/api/pet-care/{pet_id}/records/daily/summary?date=2025-10-14 \
  -H "Authorization: Bearer {token}"
```

### 3. 단위 테스트 추가 (권장)
```python
# tests/test_pet_care_query_service.py
def test_summarize_daily_activity_total():
    """Activity 기록은 합계로 집계되어야 함"""
    rows = [
        {'record_type': 'activity', 'data': 30},
        {'record_type': 'activity', 'data': 30},
        {'record_type': 'activity', 'data': 30},
    ]
    summary = PetCareRecordQueryService._summarize_daily(rows)
    assert summary['activity_minutes'] == 90

def test_summarize_daily_meal_count_last():
    """Meal count는 마지막 누적 값만 유지"""
    rows = [
        {'record_type': 'meal_count', 'data': 1},
        {'record_type': 'meal_count', 'data': 2},
        {'record_type': 'meal_count', 'data': 3},
    ]
    summary = PetCareRecordQueryService._summarize_daily(rows)
    assert summary['meal_count'] == 3
```

## 영향 범위

### 수정된 파일
1. `pet_project_backend/app/api/pet_care/records/query_service.py`
2. `pet_project_backend/app/api/pet_care/records/analyzers.py`

### 영향받는 API 엔드포인트
1. `GET /api/pet-care/{pet_id}/records/daily`
2. `GET /api/pet-care/{pet_id}/records/daily/summary`
3. `GET /api/pet-care/{pet_id}/records/summary/range` (간접 영향)

### 영향받는 서비스
- PetCareRecordQueryService
- PetCareRecordIntegration
- GoalAnalyzer

## 주의사항

### 1. meal_count는 합계가 아님
- meal_count는 **누적 카운터**이므로 마지막 값이 전체 식사 횟수
- 잘못 합계를 구하면 중복 계산됨

### 2. activity는 반드시 합계
- 여러 세션의 활동 시간을 모두 더해야 함
- 각 기록은 개별 세션을 나타냄

### 3. 다른 필드들은 최신값
- weight, bcs, stool, vomit: 가장 최근 측정/기록만 의미있음

## 향후 개선 사항

### 1. 스키마 명확화
- `record_type`별 집계 방식을 문서화
- API 응답 스키마에 주석 추가

### 2. 검증 강화
- 단위 테스트 작성
- 통합 테스트 추가
- E2E 테스트로 실제 시나리오 검증

### 3. 모니터링
- 집계 결과 이상치 감지
- 0 또는 None 값 발생 빈도 추적
- 성능 모니터링 (많은 기록 시 합계 계산 성능)

## 결론

이번 수정으로 **activity 기록의 집계 불일치 문제가 완전히 해결**되었습니다.

**핵심 변경**:
- ✅ Daily Records API: activity를 합계로 표시
- ✅ Daily Summary API: activity actual 값이 정확히 계산됨
- ✅ 두 API 간 일관성 확보
- ✅ 안전한 예외 처리 추가
- ✅ 디버깅 로그 추가

사용자는 이제 **실제 활동 시간의 정확한 합계**를 볼 수 있습니다.
