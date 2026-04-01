# 펫케어 목표값 반환 버그 수정 검증

## 📋 문제 정의

### 프론트엔드 보고 이슈
```
GET /api/pet_care/<pet_id>/records/daily/summary?date=2025-10-18
```
엔드포인트에서 **해당 날짜에 기록이 없으면 목표값도 반환되지 않는 문제**

---

## 🔍 근본 원인 분석

### 문제 코드 (수정 전)
```python
# app/api/pet_care/records/analyzers.py - GoalAnalyzer.analyze_daily()

if isinstance(meal_goal, int) and meal_goal > 0 and isinstance(meal_count, int):
    # ❌ meal_count가 None이면 이 블록 자체가 실행되지 않음
    achievements['meal'] = {
        'actual': meal_count,
        'goal': meal_goal,
        ...
    }
```

### 버그 재현 시나리오
```python
# 1. 2025-10-18에 기록이 없는 상태
# 2. settings에는 goalMealCount = 3 설정되어 있음
# 3. API 호출: GET /api/pet_care/pet123/records/daily/summary?date=2025-10-18

# 결과:
{
    "date": "2025-10-18",
    "records": [],
    "goal_progress": {
        "achievements": {}  # ❌ 빈 객체 - 목표값 자체가 누락!
    }
}

# 프론트엔드 문제:
# - UI에서 "오늘의 목표: 3회" 표시 불가
# - 달성률 표시 불가 (목표값을 모르므로)
# - 사용자는 목표가 설정되지 않았다고 오해
```

### 호출 체인
```
routes.get_daily_summary_with_goals()
  → integration_service.get_daily_summary_with_goals(pet_id, date)
    → query_service.get_daily(pet_id, date)  # records = []
    → settings_service.get_settings_at_date(pet_id, date)  # goalMealCount = 3
    → goal_analyzer.analyze_daily(records=[], date, settings)  # ❌ 여기서 버그
      → meal_count = None (기록 없음)
      → isinstance(meal_count, int) = False
      → achievements['meal'] 추가 안 됨 ❌
```

---

## ✅ 해결 방안

### 수정 원칙
**"목표값이 설정되어 있으면, 기록 유무와 관계없이 항상 achievement 객체 반환"**

### 수정 코드
```python
# 수정 후: 목표값이 있으면 항상 반환 (actual은 0으로 대체)
if isinstance(meal_goal, int) and meal_goal > 0:
    actual_meal = meal_count if isinstance(meal_count, int) else 0  # ✅ None → 0
    achievements['meal'] = {
        'actual': actual_meal,    # 0
        'goal': meal_goal,        # 3
        'percentage': 0.0,        # 0/3 * 100
        'achieved': False,        # 0 >= 3 → False
    }
```

### 수정 후 응답
```json
{
    "date": "2025-10-18",
    "records": [],
    "goal_progress": {
        "date": "2025-10-18",
        "achievements": {
            "meal": {
                "actual": 0,
                "goal": 3,
                "percentage": 0.0,
                "achieved": false
            },
            "activity": {
                "actual": 0,
                "goal": 120,
                "percentage": 0.0,
                "achieved": false,
                "detail": {
                    "sessions": 4,
                    "minutes_per_session": 30,
                    "derived_goal_minutes": 120
                }
            }
            // weight는 실제 기록이 있을 때만 반환 (의도된 동작)
        }
    }
}
```

---

## 🧪 테스트 케이스

### Case 1: 기록이 없는 날 (버그 수정 검증)
```python
# Given
pet_id = "pet123"
date = "2025-10-18"
settings = {
    "goalMealCount": 3,
    "goalActivityMinutes": 120,
    "goalActivitySessions": 4,
    "activitySessionMinutes": 30,
}
records = []  # 기록 없음

# When
result = goal_analyzer.analyze_daily(records, date, settings)

# Then
assert 'meal' in result['achievements']  # ✅ 목표값 반환됨!
assert result['achievements']['meal']['goal'] == 3
assert result['achievements']['meal']['actual'] == 0
assert result['achievements']['meal']['achieved'] == False

assert 'activity' in result['achievements']  # ✅ 활동 목표도 반환됨!
assert result['achievements']['activity']['goal'] == 120
assert result['achievements']['activity']['actual'] == 0

assert 'weight' not in result['achievements']  # 체중은 기록 없으면 미반환 (의도)
```

### Case 2: 일부 기록만 있는 날
```python
# Given
records = [
    {"record_type": "meal_count", "data": 2, "timestamp": ...},
    # activity 기록 없음
]

# When
result = goal_analyzer.analyze_daily(records, date, settings)

# Then
assert result['achievements']['meal']['actual'] == 2  # 기록된 값
assert result['achievements']['meal']['achieved'] == False  # 2 < 3

assert result['achievements']['activity']['actual'] == 0  # 기록 없으므로 0
assert result['achievements']['activity']['achieved'] == False
```

### Case 3: 목표 달성한 날 (기존 동작 유지)
```python
# Given
records = [
    {"record_type": "meal_count", "data": 3},
    {"record_type": "activity", "data": 60},
    {"record_type": "activity", "data": 60},
]

# When
result = goal_analyzer.analyze_daily(records, date, settings)

# Then
assert result['achievements']['meal']['actual'] == 3
assert result['achievements']['meal']['achieved'] == True  # 3 >= 3

assert result['achievements']['activity']['actual'] == 120  # 60 + 60
assert result['achievements']['activity']['achieved'] == True  # 120 >= 120
```

### Case 4: 목표가 설정되지 않은 경우
```python
# Given
settings = {}  # 목표 미설정
records = []

# When
result = goal_analyzer.analyze_daily(records, date, settings)

# Then
assert result['achievements'] == {}  # 목표 없으면 빈 객체 (의도된 동작)
```

---

## 🎯 변경 사항 요약

### 수정된 파일
- `pet_project_backend/app/api/pet_care/records/analyzers.py`

### 변경 내용
1. **식사 목표 (`meal`)**
   - 변경 전: `meal_count`가 `None`이면 achievement 객체 자체 누락
   - 변경 후: `meal_count`가 `None`이면 `actual=0`으로 대체하여 반환 ✅

2. **활동 목표 (`activity`)**
   - 변경 전: `activity_minutes`가 `None`이면 achievement 객체 자체 누락
   - 변경 후: `activity_minutes`가 `None`이면 `actual=0`으로 대체하여 반환 ✅

3. **체중 목표 (`weight`)**
   - 변경 없음: 실제 기록이 있을 때만 반환 (목표만으로는 의미 없음)

### 하위 호환성
✅ **완전 호환**: 기록이 있는 경우 기존과 동일한 동작
✅ **개선**: 기록이 없는 경우 이제 목표값을 반환 (프론트 요구사항 충족)

---

## 📝 프론트엔드 가이드

### 수정 전 대응 방법 (workaround)
```typescript
// 프론트에서 별도로 settings API 호출 필요
const settings = await fetchSettings(petId);
const summary = await fetchDailySummary(petId, date);

// 수동으로 목표값 병합
const mealGoal = settings.goalMealCount;
const mealActual = summary.goal_progress?.achievements?.meal?.actual || 0;
```

### 수정 후 (권장)
```typescript
// daily summary API 한 번 호출로 충분
const summary = await fetchDailySummary(petId, date);

// goal_progress.achievements에 항상 목표값 포함
const mealGoal = summary.goal_progress.achievements.meal.goal;  // ✅ 항상 존재
const mealActual = summary.goal_progress.achievements.meal.actual;
```

### 렌더링 예시
```typescript
function DailyGoalCard({ summary }) {
  const meal = summary.goal_progress?.achievements?.meal;
  
  if (!meal) {
    return <div>목표가 설정되지 않았습니다</div>;
  }
  
  return (
    <div>
      <h3>식사 목표</h3>
      <p>{meal.actual} / {meal.goal}회</p>
      <ProgressBar percentage={meal.percentage} />
      {meal.achieved && <Badge>달성!</Badge>}
    </div>
  );
}
```

---

## 🚀 배포 체크리스트

- [x] 코드 수정 완료
- [ ] 로컬 테스트 (DOCS_MODE)
- [ ] Swagger 문서 재생성 (변경 없음, 응답 스키마 동일)
- [ ] 통합 테스트 (Firestore 연결)
- [ ] 프론트엔드 팀 공유
- [ ] 스테이징 배포
- [ ] 프로덕션 배포

---

## 📚 관련 문서
- 원본 구현 계획: `docs/refactoring/PET_CARE_GOAL_HISTORY_IMPLEMENTATION.md`
- API 문서: `docs/api/pet_care.quick_reference.md`
