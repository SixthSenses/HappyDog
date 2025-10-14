# 프론트엔드 개발자 빠른 참조: 펫케어 API

## 🎯 핵심 답변

### Q1. Pet 등록하면 펫케어 설정 기본값으로 생김?
**A:** ✅ **네, 자동 생성됩니다**

```json
{
  "target_daily_activity_sessions": 4,
  "activity_session_minutes": 30,
  "target_daily_activity_minutes": 120,    // 파생값 (4×30)
  "target_daily_meal_count": 3
}
```

### Q2. 기본값을 0으로?
**A:** ❌ **아니요, 현재 기본값 유지**
- 0으로 하면 사용자가 모든 값을 수동 설정해야 함
- 기본값(120분, 3회)이 있으면 바로 사용 가능

### Q3. 홈화면에서도 summary API 사용?
**A:** ✅ **네, `/records/daily/summary` 사용 권장**

---

## 📱 홈화면 API

### 오늘의 요약 + 목표 진행률
```http
GET /api/pet-care/{pet_id}/records/daily/summary?date=2025-10-14
```

**응답 구조**:
```typescript
interface DailySummaryResponse {
  date: string;
  records: Record[];              // 실제 기록들
  record_counts: {                // 타입별 개수
    activity?: number;
    meal_count?: number;
  };
  meta: {                         // 집계 요약
    activity_minutes: number | null;  // 여러 세션 합계
    meal_count: number | null;        // 최신 누적값
    weight: number | null;            // 최신 측정값
  };
  goal_progress: {                // 목표 달성률
    achievements: {
      activity?: {
        actual: number;
        goal: number;
        percentage: number;
        achieved: boolean;
      };
      meal?: { ... };
    };
  };
}
```

---

## 🎨 UI 구현 예시

### 1. 진행률 표시
```typescript
const ActivityProgress = ({ summary }) => {
  const activity = summary.goal_progress.achievements.activity;
  
  if (!activity) {
    return <EmptyState>활동 목표를 설정해주세요</EmptyState>;
  }
  
  return (
    <ProgressBar
      current={activity.actual}
      goal={activity.goal}
      percentage={activity.percentage}
    >
      {activity.actual}분 / {activity.goal}분
    </ProgressBar>
  );
};
```

### 2. 간단한 배지
```typescript
const { meta } = summary;

<Badges>
  {meta.activity_minutes > 0 && (
    <Badge>🏃 {meta.activity_minutes}분</Badge>
  )}
  {meta.meal_count > 0 && (
    <Badge>🍽️ {meta.meal_count}회</Badge>
  )}
</Badges>
```

---

## ⚠️ 주의사항

### `target_daily_activity_minutes`는 읽기 전용!
```javascript
// ❌ 이렇게 수정하지 마세요
PATCH /settings
{
  "target_daily_activity_minutes": 180  // 무시됨!
}

// ✅ 이렇게 수정하세요
PATCH /settings
{
  "target_daily_activity_sessions": 6,  // 세션 수
  "activity_session_minutes": 30        // 1회 분
  // → 자동 계산: 6 × 30 = 180분
}
```

### Activity는 합계로 집계됨
```javascript
// 기록: 30분 + 30분 + 30분
meta.activity_minutes = 90  // ✅ 합계

// 기록: 식사 1회 → 2회 → 3회
meta.meal_count = 3         // ✅ 최신 누적값
```

---

## 📊 화면별 API 선택

| 화면 | API | 데이터 |
|------|-----|--------|
| 홈화면 | `/records/daily/summary` | 요약 + 진행률 |
| 기록 목록 | `/records/daily` | 전체 기록 |
| 월간 분석 | `/records/summary/range` | 기간 트렌드 + **달성 날짜** |
| 설정 | `/settings` | 목표 설정 |

---

## 🆕 월간 목표 달성 추적 (2025-10-14)

### 달성 횟수 + 날짜 조회
```http
GET /api/pet-care/{pet_id}/records/summary/range?start_date=2025-11-01&end_date=2025-11-30
```

```typescript
{
  meta: {
    monthly: {
      meal: {
        achievement_count: 3,                           // 달성 횟수
        achievement_dates: ["2025-11-03", "2025-11-04", "2025-11-07"]  // 달성 날짜
      },
      activity: {
        achievement_count: 1,
        achievement_dates: ["2025-11-03"]
      }
    }
  }
}
```

### 캘린더 구현 예시
```typescript
const { meal, activity } = response.meta.monthly;

// 날짜별로 체크마크 표시
<Calendar>
  {dates.map(date => (
    <Day
      date={date}
      mealAchieved={meal.achievement_dates.includes(date)}
      activityAchieved={activity.achievement_dates.includes(date)}
    />
  ))}
</Calendar>
```

---

## 🔗 상세 문서

- [펫케어 FAQ](./pet_care.frontend_faq.md) - 기본 사용법
- [목표 달성 추적 가이드](./pet_care.goal_achievement_tracking.md) - 캘린더 구현 예시
