# 프론트엔드 개발자 FAQ: 펫케어 설정 기본값 및 홈화면 API

## 질문 1: Pet 등록 시 펫케어 설정 기본값이 자동으로 생성되나요?

### ✅ 답변: **네, 자동으로 생성됩니다**

Pet을 등록하면 **트랜잭션 내에서 펫케어 설정이 함께 생성**됩니다.

### 생성 시점 및 방식

```python
# PetProfileService.register_pet() 내부
def _register_in_transaction(transaction):
    # 1. Pet 문서 생성
    transaction.set(pet_ref, firestore_data)
    
    # 2. User 문서 업데이트
    transaction.update(user_ref, {'has_pet': True, 'pet_id': pet_id})
    
    # 3. 펫케어 설정 자동 생성 ⭐
    self.pet_care_setting_service.create_initial_settings_transactional(
        transaction, 
        pet_id=pet_id, 
        gender=new_pet.gender.value,
        breed=new_pet.breed, 
        current_weight=0.0
    )
```

### 기본값 상세

**API Response 예시** (`GET /api/pet-care/{pet_id}/settings`):
```json
{
  "pet_id": "4159de9b-d746-4d51-83ee-92606552d559",
  
  // 목표 체중 (품종별 이상 체중 or 0.0)
  "goalWeight": 5.2,  // 품종 정보가 있으면 해당 품종의 이상 체중
  
  // 활동 목표 (파생값: sessions × activitySessionMinutes)
  "target_daily_activity_sessions": 4,           // 하루 활동 세션 수
  "activity_session_minutes": 30,                // 1회 세션당 분
  "target_daily_activity_minutes": 120,          // 파생값 (4 × 30 = 120)
  "daily_activity_increment": 10,                // UI 증감 단위
  
  // 식사 목표
  "target_daily_meal_count": 3,                  // 하루 식사 횟수
  
  // 타임스탬프
  "updated_at": "2025-10-14T02:22:43.047303+00:00"
}
```

### 기본값 정책

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `goalWeight` | 품종 이상 체중 or `current_weight` | 품종 정보로 자동 계산 |
| `target_daily_activity_sessions` | `4` | 하루 활동 세션 수 |
| `activity_session_minutes` | `30` | 1회 세션당 분 |
| `target_daily_activity_minutes` | `120` | **파생값** (4 × 30) |
| `daily_activity_increment` | `10` | UI 증감 단위 (분) |
| `target_daily_meal_count` | `3` | 하루 식사 횟수 |

### ⚠️ 중요: `target_daily_activity_minutes`는 읽기 전용

**이 필드는 파생 필드**입니다:
```
target_daily_activity_minutes = target_daily_activity_sessions × activity_session_minutes
```

- ✅ **읽기**: API 응답에 포함됨
- ❌ **쓰기**: PATCH/PUT 요청에 이 필드를 포함하면 **무시됨**

**올바른 수정 방법**:
```javascript
// ❌ 잘못된 예
PATCH /api/pet-care/{pet_id}/settings
{
  "target_daily_activity_minutes": 180  // 무시됨!
}

// ✅ 올바른 예
PATCH /api/pet-care/{pet_id}/settings
{
  "target_daily_activity_sessions": 6,  // 세션 수 변경
  "activity_session_minutes": 30        // 1회 분 유지
  // → target_daily_activity_minutes = 180 자동 계산됨
}
```

---

## 질문 2: 기본값을 0으로 설정해야 하나요?

### ✅ 답변: **아니요, 현재 기본값(활동 120분, 식사 3회)을 유지하세요**

### 이유

1. **합리적인 기본값 제공**
   - 중형견 기준 표준 권장 사항
   - 사용자가 즉시 사용 가능한 목표

2. **UX 개선**
   - 0으로 설정 시 사용자가 모든 값을 수동으로 입력해야 함
   - 기본값이 있으면 필요시 조정만 하면 됨

3. **진행률 표시**
   - 0이면 모든 진행률이 0% 또는 undefined
   - 기본값이 있으면 의미있는 진행률 표시 가능

### 목표가 없는 경우 처리

**서버는 이미 안전하게 처리합니다**:

```javascript
// Goal이 0이거나 null일 때
{
  "goal_progress": {
    "achievements": {
      // goal이 없으면 achievement 자체가 생성되지 않음
    }
  }
}
```

**프론트엔드 권장 처리**:
```typescript
// achievements가 비어있으면 "목표 설정이 필요합니다" 안내
if (Object.keys(goalProgress.achievements).length === 0) {
  return <EmptyGoalState />;
}

// 개별 목표별 체크
const activityGoal = goalProgress.achievements.activity;
if (!activityGoal) {
  return <NoActivityGoalBadge />;
}
```

---

## 질문 3: 홈화면에서도 summary API를 사용해야 하나요?

### ✅ 답변: **네, Daily Summary API를 사용하세요**

### 권장 API 엔드포인트

```http
GET /api/pet-care/{pet_id}/records/daily/summary?date=2025-10-14
Authorization: Bearer {token}
```

### 응답 구조

```json
{
  "date": "2025-10-14",
  
  // 실제 기록들
  "records": [
    {
      "log_id": "xxx",
      "record_type": "activity",
      "data": 30,
      "timestamp_ms": 1728900000000,
      "memo": "",
      ...
    }
  ],
  
  // 타입별 기록 개수
  "record_counts": {
    "activity": 3,
    "meal_count": 1,
    "weight": 1
  },
  
  // 타입별 집계 요약
  "meta": {
    "activity_minutes": 90,      // 여러 세션 합계
    "meal_count": 3,              // 최신 누적 횟수
    "weight": 5.2,                // 최신 측정값
    "bcs": null,
    "stool": null,
    "vomit": null
  },
  
  // 목표 달성 진행률
  "goal_progress": {
    "date": "2025-10-14",
    "achievements": {
      "meal": {
        "actual": 3,
        "goal": 3,
        "percentage": 100.0,
        "achieved": true
      },
      "activity": {
        "actual": 90,
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

### 홈화면 UI 구성 예시

#### 1. 오늘의 달성률 카드
```typescript
const DailyProgressCard = ({ summary }) => {
  const { goal_progress, meta } = summary;
  
  return (
    <Card>
      <h3>오늘의 건강 관리</h3>
      
      {/* 활동 목표 */}
      {goal_progress.achievements.activity && (
        <ProgressBar 
          label="활동"
          current={goal_progress.achievements.activity.actual}
          goal={goal_progress.achievements.activity.goal}
          percentage={goal_progress.achievements.activity.percentage}
          achieved={goal_progress.achievements.activity.achieved}
        />
      )}
      
      {/* 식사 목표 */}
      {goal_progress.achievements.meal && (
        <ProgressBar 
          label="식사"
          current={goal_progress.achievements.meal.actual}
          goal={goal_progress.achievements.meal.goal}
          percentage={goal_progress.achievements.meal.percentage}
          achieved={goal_progress.achievements.meal.achieved}
        />
      )}
    </Card>
  );
};
```

#### 2. 간단한 요약 배지
```typescript
const QuickSummaryBadges = ({ meta }) => (
  <div className="badges">
    {meta.activity_minutes > 0 && (
      <Badge icon="🏃">
        {meta.activity_minutes}분 활동
      </Badge>
    )}
    {meta.meal_count > 0 && (
      <Badge icon="🍽️">
        {meta.meal_count}회 식사
      </Badge>
    )}
    {meta.weight && (
      <Badge icon="⚖️">
        {meta.weight}kg
      </Badge>
    )}
  </div>
);
```

### 날짜별 조회 (선택 날짜)

```typescript
// 오늘
const today = format(new Date(), 'yyyy-MM-dd');
const todaySummary = await fetch(
  `/api/pet-care/${petId}/records/daily/summary?date=${today}`
);

// 어제
const yesterday = format(subDays(new Date(), 1), 'yyyy-MM-dd');
const yesterdaySummary = await fetch(
  `/api/pet-care/${petId}/records/daily/summary?date=${yesterday}`
);
```

### API 선택 가이드

| 화면 | 사용 API | 이유 |
|------|----------|------|
| **홈화면** | `/records/daily/summary` | 목표 진행률 + 요약이 필요 |
| **상세 기록 목록** | `/records/daily` | 개별 기록 전체 필요 |
| **월간 분석** | `/records/summary/range` | 기간 트렌드 + 목표 추적 |
| **설정 화면** | `/settings` | 목표 설정 조회/수정 |

---

## 요약 및 권장사항

### ✅ DO (권장)
1. **Pet 등록 시 자동 생성되는 기본값 사용**
   - 활동: 4세션 × 30분 = 120분
   - 식사: 3회
   
2. **홈화면에서 Daily Summary API 사용**
   - 목표 진행률과 집계 요약을 한 번에 조회
   
3. **기본값이 있는 상태로 시작**
   - 사용자가 필요시 설정 화면에서 조정
   
4. **목표가 없는 경우 UI 처리**
   - "목표를 설정해주세요" 안내
   - 설정 화면으로 유도

### ❌ DON'T (비권장)
1. **기본값을 0으로 설정하지 마세요**
   - 사용자 경험 저하
   - 진행률 표시 불가
   
2. **`target_daily_activity_minutes`를 직접 수정하지 마세요**
   - 무시됨 (파생 필드)
   - 세션 수와 1회 분을 수정하세요
   
3. **홈화면에서 `/records/daily`만 사용하지 마세요**
   - 목표 진행률이 없어서 추가 계산 필요
   - `/records/daily/summary` 사용 권장

---

## 추가 참고사항

### 관련 문서
- [API 문서](../../openapi_pretty.json) - 전체 API 스펙
- [Activity 집계 수정 내역](./PET_CARE_ACTIVITY_AGGREGATION_FIX.md) - 최근 버그 수정

### 백엔드 변경사항 (2025-10-14)
- ✅ Activity 기록이 **합계로 집계**되도록 수정
- ✅ Daily Records와 Daily Summary API 간 **일관성 확보**
- ✅ 안전한 예외 처리 및 로깅 추가

### 문의사항
추가 질문이 있으면 백엔드 팀에 문의해주세요.
