# 펫케어 사료(Meal) 달성률 전수검사 보고서

**날짜**: 2025-10-14  
**목적**: 안드로이드 앱에서 사료 달성률 관련 응답 검증  
**범위**: pet_care 도메인의 사료 목표 계산 및 전달 로직 전체

---

## 🔍 검사 대상 경로

### 1. 핵심 계산 로직
**파일**: `pet_project_backend/app/api/pet_care/records/analyzers.py`

#### `GoalAnalyzer.analyze_daily()` (Line 17-67)
```python
def analyze_daily(self, rows: List[Dict[str, Any]], date: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    # 사료 횟수 추출 (최신 누적값)
    meal_count = self._extract_last(rows, 'meal_count')
    
    # 목표값 가져오기
    meal_goal = settings.get('goalMealCount')
    
    # 달성률 계산
    achievements: Dict[str, Any] = {}
    if isinstance(meal_goal, int) and meal_goal > 0 and isinstance(meal_count, int):
        achievements['meal'] = {
            'actual': meal_count,          # 실제 횟수
            'goal': meal_goal,             # 목표 횟수
            'percentage': round(meal_count / meal_goal * 100, 1),  # 달성률(%)
            'achieved': meal_count >= meal_goal,  # 목표 달성 여부
        }
```

**✅ 검증 결과**:
- `percentage` 계산식: `(actual / goal) * 100` → **정확**
- `achieved` 판단: `actual >= goal` → **정확**
- `round(..., 1)` → 소수점 첫째자리까지 표시 → **정확**
- 타입 검증 포함: `isinstance(meal_goal, int)` 및 `meal_goal > 0` → **안전**

#### `_extract_last()` 메서드 (Line 114-122)
```python
@staticmethod
def _extract_last(rows: List[Dict[str, Any]], rtype: str):
    """Extract the last (most recent) value for a given record type.
    
    Used for cumulative counts (meal_count) and single measurements (weight, bcs).
    """
    filtered = [r for r in rows if r.get('record_type') == rtype]
    return filtered[-1].get('data') if filtered else None
```

**✅ 검증 결과**:
- `meal_count`는 **누적값**이므로 최신 기록만 사용하는 것이 맞음
- 빈 리스트 처리: `if filtered` 체크로 IndexError 방지 → **안전**

---

### 2. API 엔드포인트별 응답

#### 2.1 일별 요약 + 목표 진행률
**엔드포인트**: `GET /api/pet-care/{pet_id}/records/daily/summary`  
**파일**: `pet_project_backend/app/api/pet_care/records/routes.py` (Line 144-183)

**응답 구조**:
```json
{
  "date": "2025-10-14",
  "records": [...],
  "record_counts": {
    "meal_count": 2
  },
  "meta": {
    "meal_count": 3
  },
  "goal_progress": {
    "date": "2025-10-14",
    "achievements": {
      "meal": {
        "actual": 3,
        "goal": 3,
        "percentage": 100.0,
        "achieved": true
      }
    }
  }
}
```

**✅ 검증 결과**:
- `goal_progress.achievements.meal` 객체가 정확히 생성됨
- `DailySummaryWithGoalsResponseSchema` 스키마에 정의됨 (Line 126-133)
- `record_integration_service.py`의 `get_daily_summary_with_goals()` (Line 87-122)에서 처리
- **주의사항**: `meta.meal_count`(최신 누적값)와 `goal_progress.achievements.meal.actual`이 같아야 함

---

#### 2.2 기간 요약 + 트렌드 + 목표 추적
**엔드포인트**: `GET /api/pet-care/{pet_id}/records/summary/range`  
**파일**: `pet_project_backend/app/api/pet_care/records/routes.py` (Line 186-217)

**응답 구조**:
```json
{
  "start_date": "2025-11-01",
  "end_date": "2025-11-30",
  "goal_tracking": {
    "days_achieved": {
      "meal": 3,
      "activity": 1,
      "weight": 0
    },
    "achievement_dates": {
      "meal": ["2025-11-03", "2025-11-04", "2025-11-07"],
      "activity": ["2025-11-03"],
      "weight": []
    },
    "achievement_rates": {
      "meal": 10.0,
      "activity": 3.3,
      "weight": 0.0
    }
  },
  "meta": {
    "monthly": {
      "encouragement_count": 4,
      "message": "좋은 시작이에요!",
      "meal": {
        "achievement_count": 3,
        "achievement_dates": ["2025-11-03", "2025-11-04", "2025-11-07"]
      },
      "activity": {
        "achievement_count": 1,
        "achievement_dates": ["2025-11-03"]
      }
    }
  },
  "trends": {...}
}
```

**✅ 검증 결과**:
- `GoalAnalyzer.analyze_range()` (Line 70-111)에서 처리
- 각 날짜별로 `analyze_daily()`를 호출하여 `achieved` 체크
- 달성한 날짜를 `achievement_dates['meal']`에 추가
- `achievement_rates`: `(days_achieved / total_days) * 100` → **정확**
- `meta.monthly.meal` 객체에도 중복 제공 (캘린더 UI용)

---

#### 2.3 기록 생성 시 목표 분석
**엔드포인트**: `POST /api/pet-care/{pet_id}/records`  
**파일**: `pet_project_backend/app/api/pet_care/records/record_integration_service.py` (Line 36-81)

**처리 흐름**:
```python
def create_record_with_goals(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
    # 1. 기록 생성
    result = self.crud.create_record(pet_id, record_data)
    
    # 2. 설정 조회
    settings = self.settings.get_settings(pet_id)
    
    # 3. 목표 분석
    if settings and search_date:
        goal_analysis = self.goal_analyzer.analyze_daily(
            self.query.get_daily(pet_id, search_date)['records'],
            search_date,
            settings,
        )
        result['goal_analysis'] = goal_analysis
        
        # 4. 달성 시 알림 전송
        self._send_achievement_notifications(pet_id, goal_analysis, record_data)
```

**알림 로직** (`_send_achievement_notifications`, Line 210-250):
```python
meal = achievements.get('meal')
if meal and meal.get('achieved'):
    self.notifier.notify_goal(pet_id, 'meal', {
        'message': f"{pet_name}의 오늘 식사 목표를 달성했어요! ({meal['actual']}/{meal['goal']}회)",
        'date': date,
        'goal_type': 'meal',
        'actual': meal['actual'],
        'goal': meal['goal'],
    })
```

**✅ 검증 결과**:
- 기록 생성 직후 목표 분석 수행 → **정확**
- 달성 시 즉시 알림 전송 → **정확**
- `result['goal_analysis']`로 응답에 포함 → 클라이언트가 즉시 확인 가능

---

## 🎯 잠재적 이슈 및 검사 포인트

### 1. **meal_count 증분값 전송 지원 (2025-10-14 업데이트)** ✅ 해결됨

**변경 전 동작**:
- `meal_count`는 **당일 누적 횟수** (예: 3회)로 전송해야 함
- `_extract_last()`로 최신 값만 사용
- 클라이언트가 증분값(+1, +1, +1)을 보내면 마지막 값 1만 사용 → 목표 미달

**변경 후 동작** (구현 완료):
- 백엔드가 **자동으로 누적값 계산**
- 클라이언트는 **증분값 전송 권장** (간단함)
- 누적값 전송도 여전히 작동 (하위 호환)

**✅ 권장 방식 (증분값)**:
```json
// 클라이언트는 항상 data: 1 전송
POST /records { "record_type": "meal_count", "data": 1 }  // 첫 식사
POST /records { "record_type": "meal_count", "data": 1 }  // 두번째
POST /records { "record_type": "meal_count", "data": 1 }  // 세번째

// 백엔드 자동 처리: 0+1=1, 1+1=2, 2+1=3
// 결과: 최종 누적값 3 → 목표 3회 달성 ✅
```

**구현 위치**:
- `services.py`: `_convert_meal_increment_to_cumulative()` 메서드 추가
- 기록 생성 시 같은 날짜의 최대값 조회 후 증분값 더하기
- 테스트: `tests/test_pet_care_meal_count.py`

**장점**:
- 프론트엔드 상태 관리 불필요
- 앱 재시작 시 복구 로직 불필요
- 간단한 구현: 항상 `data: 1` 전송

---

### 2. **goalMealCount 설정값 확인**
**설정 위치**: `pet_project_backend/app/api/pet_care/settings/`

**⚠️ 체크 포인트**:
1. Pet 생성 시 기본값 설정 여부
   - 기본값: `"target_daily_meal_count": 3`
2. 사용자가 0 또는 null로 설정 가능한지
   - `meal_goal > 0` 조건으로 필터링되므로 0이면 달성률 계산 안 됨
3. 클라이언트에서 설정 변경 후 즉시 반영되는지

**검증 방법**:
```http
GET /api/pet-care/{pet_id}/settings
```
응답에서 `goalMealCount` 또는 `target_daily_meal_count` 확인

---

### 3. **응답 스키마의 일관성**
**다른 필드명 사용**:
- 설정: `goalMealCount` (camelCase)
- 응답: `goal_progress.achievements.meal` (snake_case)

**✅ 현재 상태**:
- `GoalAnalyzer`에서 `settings.get('goalMealCount')` 사용
- 응답 스키마에서 `goal_progress` 키 사용
- 일관성 유지됨

**⚠️ 주의사항**:
- 설정 API와 기록 API가 다른 키 명명 규칙을 사용할 수 있음
- 프론트엔드 개발자에게 명확히 문서화 필요

---

### 4. **빈 기록 처리**
**시나리오**: 특정 날짜에 meal_count 기록이 없는 경우

**현재 동작**:
```python
meal_count = self._extract_last(rows, 'meal_count')
# meal_count = None

if isinstance(meal_goal, int) and meal_goal > 0 and isinstance(meal_count, int):
    # 조건 실패 → achievements['meal'] 생성 안 됨
```

**결과**:
- `goal_progress.achievements` 객체에 `meal` 키 없음
- 클라이언트는 `goal_progress.achievements.meal` 접근 시 `undefined` 또는 null

**권장 클라이언트 처리**:
```typescript
const mealAchievement = response.goal_progress?.achievements?.meal;
if (mealAchievement) {
  // 목표 설정 및 기록 존재
  showProgress(mealAchievement);
} else {
  // 목표 미설정 또는 기록 없음
  showEmptyState();
}
```

---

### 5. **Range API의 날짜 계산**
**`achievement_rates` 계산**:
```python
total = len(days) or 1
rates = {k: round(v / total * 100, 1) for k, v in counts.items()}
```

**⚠️ 주의사항**:
- `len(days)`: 실제 기록이 있는 날짜 수 (예: 30일 중 5일만 기록 → 5)
- OR 기간 전체 일수 (예: start_date ~ end_date = 30일)

**현재 구현**:
```python
days = sorted(grouped.keys())  # grouped = records_by_date
```
→ **기록이 있는 날짜만** 카운트됨

**예시**:
- 11월 1~30일 (30일)
- 실제 기록: 11/3, 11/4, 11/7 (3일)
- meal 달성: 3일
- `achievement_rates.meal = 3 / 3 * 100 = 100%` (❌ 잘못된 계산)
- 올바른 계산: `3 / 30 * 100 = 10%`

**🚨 버그 발견**: 달성률 계산 시 전체 기간 일수가 아닌 기록 일수로 나눔

---

### 6. **타임존 이슈**
**searchDate 생성**: `DateTimeUtils.today_kst_as_date_str()` 사용

**⚠️ 체크 포인트**:
- 클라이언트와 서버의 날짜 기준이 같은지
- 자정(00:00) 전후 기록이 다른 날짜로 분류될 가능성
- `timestamp` (Unix ms)를 KST 날짜로 변환하는 로직 확인

**관련 이슈**: `docs/refactoring/PET_CARE_TIMEZONE_FIX_SUMMARY.md` 참조

---

## 📋 검사 체크리스트

### ✅ 완료된 항목 (2025-10-14)
- [x] **meal_count 증분값 전송 지원 구현**
  - `services.py`에 자동 누적 로직 추가
  - 클라이언트는 항상 `data: 1` 전송 가능
  - 하위 호환성 유지 (누적값 전송도 작동)
- [x] **API 문서 업데이트**
  - `pet_care.quick_reference.md`에 증분값 전송 방식 추가
  - 예제 코드 및 장단점 명시

### 즉시 확인 필요 항목
- [ ] **안드로이드 앱을 증분값 전송으로 변경**
  - 기존: 누적값 관리 (복잡)
  - 신규: 항상 `data: 1` 전송 (간단)
  - 백엔드 먼저 배포되었으므로 안전하게 변경 가능
- [ ] **goalMealCount 설정값 확인**
  - 기본값이 올바른지
  - 0 또는 null로 설정된 반려동물 있는지
- [ ] **Range API의 achievement_rates 버그 수정**
  - 전체 기간 일수로 나눠야 함 (현재는 기록 일수로 나눔)
  - 별도 이슈로 추적 필요
- [ ] **빈 기록 처리 확인**
  - meal_count 기록 없는 날짜의 응답 확인
  - 클라이언트가 undefined/null 처리하는지

### 중요도 낮음 (문서화 권장)
- [x] meal_count 의미 명확화 문서 작성 (완료)
- [ ] 설정 키 네이밍 규칙 문서화 (`goalMealCount` vs `meal`)
- [ ] 타임존 처리 로직 점검

---

## 🔧 수정 권장 사항

### 1. Range API의 달성률 버그 수정
**파일**: `pet_project_backend/app/api/pet_care/records/analyzers.py`

**현재 코드** (Line 102-104):
```python
total = len(days) or 1
rates = {k: round(v / total * 100, 1) for k, v in counts.items()}
```

**수정 제안**:
```python
# 전체 기간 일수 계산 (start_date ~ end_date)
from datetime import datetime, timedelta

def analyze_range(self, grouped: Dict[str, List[Dict[str, Any]]], 
                  settings: Dict[str, Any],
                  start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Args에 start_date, end_date 추가 필요
    """
    days = sorted(grouped.keys())
    # ... 기존 로직 ...
    
    # 전체 기간 일수로 달성률 계산
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    total_days = (end - start).days + 1
    
    rates = {k: round(v / total_days * 100, 1) for k, v in counts.items()}
```

**호출부 수정** (`record_integration_service.py` Line 143-146):
```python
goal_tracking = self.goal_analyzer.analyze_range(
    records_result['records_by_date'], 
    settings,
    start_date,  # 추가
    end_date     # 추가
)
```

---

### 2. 빈 기록 시 기본 응답 제공 (선택사항)
**현재**: `achievements` 객체에 `meal` 키 없음  
**개선안**: 기록 없어도 0% 응답 제공

```python
if isinstance(meal_goal, int) and meal_goal > 0:
    achievements['meal'] = {
        'actual': meal_count if isinstance(meal_count, int) else 0,
        'goal': meal_goal,
        'percentage': round((meal_count or 0) / meal_goal * 100, 1),
        'achieved': isinstance(meal_count, int) and meal_count >= meal_goal,
    }
```

**장점**: 클라이언트가 항상 일관된 구조 받음  
**단점**: 목표 설정 여부와 기록 유무 구분 어려움

---

## 📊 요약

### ✅ 정확히 작동하는 부분
1. **일별 달성률 계산**: `(actual / goal) * 100` → 정확
2. **달성 여부 판단**: `actual >= goal` → 정확
3. **기록 생성 시 알림**: 목표 달성 즉시 알림 → 정확
4. **타입 안전성**: isinstance 체크로 안전

### 🚨 발견된 이슈
1. **Range API 달성률 버그**: 기록 일수로 나눔 (전체 일수여야 함)
2. **meal_count 의미 혼동 가능성**: 누적값 vs 증분값

### 🔍 확인 필요 항목
1. 안드로이드 앱의 meal_count 전송 방식
2. goalMealCount 설정 기본값 및 현황
3. 빈 기록 시 클라이언트 처리 방식

---

**다음 단계**: 
1. 안드로이드 앱 로그로 meal_count 전송 방식 확인
2. Range API 달성률 버그 수정 PR 작성
3. 클라이언트 팀에 빈 기록 처리 가이드 전달
