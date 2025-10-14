# 펫케어 월간 목표 달성 추적 구현 가이드

## 📅 새로운 기능: 목표 달성 날짜 추적

**2025-10-14 업데이트**: 이제 Range Summary API가 **달성 횟수**와 **달성한 날짜 목록**을 모두 반환합니다!

---

## 🎯 API 응답 구조

### 월간/기간 요약 API
```http
GET /api/pet-care/{pet_id}/records/summary/range?start_date=2025-11-01&end_date=2025-11-30
Authorization: Bearer {token}
```

### 완전한 응답 예시
```json
{
  "start_date": "2025-11-01",
  "end_date": "2025-11-30",
  
  "records_by_date": {
    "2025-11-03": [...],
    "2025-11-04": [...],
    "2025-11-07": [...]
  },
  
  "goal_tracking": {
    "days_achieved": {
      "meal": 3,        // 식사 목표 달성 3일
      "activity": 1,    // 활동 목표 달성 1일
      "weight": 0
    },
    "achievement_dates": {
      "meal": [
        "2025-11-03",   // ✓ 식사 목표 달성한 날짜들
        "2025-11-04",
        "2025-11-07"
      ],
      "activity": [
        "2025-11-03"    // ✓ 활동 목표 달성한 날짜들
      ],
      "weight": []
    },
    "achievement_rates": {
      "meal": 10.0,     // 30일 중 3일 = 10%
      "activity": 3.3,  // 30일 중 1일 = 3.3%
      "weight": 0.0
    }
  },
  
  "meta": {
    "monthly": {
      "encouragement_count": 4,  // 전체 달성 횟수 (3+1)
      "message": "좋은 시작이에요!",
      
      // 🆕 개별 목표별 상세 정보 (캘린더 표시용)
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
  
  "trends": {
    "weight_trend": [...],
    "meal_frequency_trend": [...],
    "activity_trend": [...]
  }
}
```

---

## 📱 UI 구현 예시

### 1. 목표별 달성 횟수 표시
```typescript
interface MonthlyGoalSummary {
  achievement_count: number;
  achievement_dates: string[];
}

const GoalAchievementBadge = ({ goalType, summary }: { 
  goalType: 'meal' | 'activity',
  summary: MonthlyGoalSummary 
}) => {
  const { achievement_count, achievement_dates } = summary;
  
  return (
    <Card>
      <div className="goal-header">
        <Icon type={goalType} />
        <h4>{goalType === 'meal' ? '사료' : '활동'}</h4>
      </div>
      
      {/* 달성 횟수 표시 */}
      <div className="achievement-count">
        <span className="label">1일 목표 달성 횟수</span>
        <span className="count">{achievement_count}회</span>
      </div>
      
      {/* 진행률 */}
      <ProgressBar 
        value={achievement_count} 
        max={30}  // 한 달 기준
      />
    </Card>
  );
};

// 사용
const { meal, activity } = response.meta.monthly;
<GoalAchievementBadge goalType="meal" summary={meal} />
<GoalAchievementBadge goalType="activity" summary={activity} />
```

### 2. 캘린더에 달성 날짜 표시
```typescript
interface CalendarProps {
  month: string;  // "2025-11"
  achievementDates: {
    meal: string[];
    activity: string[];
  };
}

const MonthlyCalendar = ({ month, achievementDates }: CalendarProps) => {
  const renderDay = (date: string) => {
    const mealAchieved = achievementDates.meal.includes(date);
    const activityAchieved = achievementDates.activity.includes(date);
    
    return (
      <div className={`calendar-day ${mealAchieved || activityAchieved ? 'achieved' : ''}`}>
        <span className="date">{getDayOfMonth(date)}</span>
        
        {/* 체크마크 표시 */}
        {(mealAchieved || activityAchieved) && (
          <div className="achievement-badges">
            {mealAchieved && <Badge type="meal">✓</Badge>}
            {activityAchieved && <Badge type="activity">✓</Badge>}
          </div>
        )}
      </div>
    );
  };
  
  return (
    <div className="calendar">
      {getDaysInMonth(month).map(date => renderDay(date))}
    </div>
  );
};

// 사용
const { meal, activity } = response.meta.monthly;
<MonthlyCalendar 
  month="2025-11"
  achievementDates={{
    meal: meal.achievement_dates,
    activity: activity.achievement_dates
  }}
/>
```

### 3. 월간 분석 메시지
```typescript
const MonthlyAnalysis = ({ monthly }: { monthly: any }) => {
  const { encouragement_count, message, meal, activity } = monthly;
  
  return (
    <Card className="monthly-analysis">
      <h3>월간 분석</h3>
      
      {/* 격려 메시지 */}
      <p className="encouragement">{message}</p>
      
      {/* 상세 달성 정보 */}
      <div className="details">
        <div className="stat">
          <Icon type="meal" />
          <span>11월에는 목표를 <strong>{meal.achievement_count}번</strong> 채웠네요</span>
        </div>
        <div className="stat">
          <Icon type="activity" />
          <span>11월에는 목표를 <strong>{activity.achievement_count}번</strong> 채웠네요</span>
        </div>
      </div>
      
      {/* 조금만 더 힘내세요 안내 */}
      {encouragement_count < 10 && (
        <p className="motivate">조금만 더 힘내세요!</p>
      )}
      {encouragement_count >= 10 && encouragement_count < 20 && (
        <p className="motivate">이 기세로 계속 이어가요!</p>
      )}
    </Card>
  );
};
```

### 4. 실전 React 컴포넌트 예시
```typescript
import { useQuery } from '@tanstack/react-query';
import { format, startOfMonth, endOfMonth } from 'date-fns';

interface GoalSummaryProps {
  petId: string;
  month: Date;
}

export const MonthlyGoalSummary = ({ petId, month }: GoalSummaryProps) => {
  const startDate = format(startOfMonth(month), 'yyyy-MM-dd');
  const endDate = format(endOfMonth(month), 'yyyy-MM-dd');
  
  const { data, isLoading } = useQuery({
    queryKey: ['petCare', 'rangeSummary', petId, startDate, endDate],
    queryFn: () => 
      fetch(`/api/pet-care/${petId}/records/summary/range?start_date=${startDate}&end_date=${endDate}`)
        .then(res => res.json())
  });
  
  if (isLoading) return <Loading />;
  if (!data?.meta?.monthly) return <EmptyState />;
  
  const { monthly } = data.meta;
  
  return (
    <div className="monthly-goal-summary">
      {/* 목표별 카드 */}
      <div className="goal-cards">
        <GoalCard
          type="meal"
          icon="🍽️"
          title="사료"
          count={monthly.meal.achievement_count}
          dates={monthly.meal.achievement_dates}
          totalDays={30}
        />
        <GoalCard
          type="activity"
          icon="🏃"
          title="활동"
          count={monthly.activity.achievement_count}
          dates={monthly.activity.achievement_dates}
          totalDays={30}
        />
      </div>
      
      {/* 캘린더 */}
      <Calendar
        month={month}
        mealDates={monthly.meal.achievement_dates}
        activityDates={monthly.activity.achievement_dates}
      />
      
      {/* 월간 분석 */}
      <AnalysisCard
        message={monthly.message}
        totalCount={monthly.encouragement_count}
        mealCount={monthly.meal.achievement_count}
        activityCount={monthly.activity.achievement_count}
      />
    </div>
  );
};
```

---

## 🎨 UI 스타일링 예시 (Tailwind CSS)

```tsx
const GoalCard = ({ type, icon, title, count, dates, totalDays }) => (
  <div className="bg-white rounded-lg shadow p-6">
    {/* 헤더 */}
    <div className="flex items-center gap-2 mb-4">
      <span className="text-3xl">{icon}</span>
      <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
    </div>
    
    {/* 달성 횟수 */}
    <div className="mb-4">
      <p className="text-sm text-gray-500 mb-1">1일 목표 달성 횟수</p>
      <p className="text-2xl font-bold text-blue-600">{count}회</p>
    </div>
    
    {/* 진행률 바 */}
    <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
      <div 
        className={`h-2 rounded-full ${
          type === 'meal' ? 'bg-orange-500' : 'bg-blue-500'
        }`}
        style={{ width: `${(count / totalDays) * 100}%` }}
      />
    </div>
    <p className="text-xs text-gray-500 text-right">
      {Math.round((count / totalDays) * 100)}% 달성
    </p>
    
    {/* 달성 날짜 미리보기 */}
    {dates.length > 0 && (
      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500 mb-2">최근 달성 날짜</p>
        <div className="flex gap-2 flex-wrap">
          {dates.slice(-3).map(date => (
            <span key={date} className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
              {format(new Date(date), 'M/d')}
            </span>
          ))}
        </div>
      </div>
    )}
  </div>
);

const Calendar = ({ month, mealDates, activityDates }) => (
  <div className="bg-white rounded-lg shadow p-6">
    <h3 className="text-lg font-semibold mb-4">
      {format(month, 'yyyy년 M월')}
    </h3>
    
    {/* 요일 헤더 */}
    <div className="grid grid-cols-7 gap-2 mb-2">
      {['일', '월', '화', '수', '목', '금', '토'].map(day => (
        <div key={day} className="text-center text-xs text-gray-500 font-medium">
          {day}
        </div>
      ))}
    </div>
    
    {/* 날짜 그리드 */}
    <div className="grid grid-cols-7 gap-2">
      {getDaysInMonth(month).map(date => {
        const dateStr = format(date, 'yyyy-MM-dd');
        const mealAchieved = mealDates.includes(dateStr);
        const activityAchieved = activityDates.includes(dateStr);
        const hasAchievement = mealAchieved || activityAchieved;
        
        return (
          <div
            key={dateStr}
            className={`
              aspect-square flex flex-col items-center justify-center
              rounded-lg relative
              ${hasAchievement ? 'bg-blue-50' : 'bg-gray-50'}
            `}
          >
            <span className={`text-sm ${hasAchievement ? 'font-semibold' : ''}`}>
              {format(date, 'd')}
            </span>
            
            {/* 체크마크 */}
            {hasAchievement && (
              <div className="absolute bottom-1 flex gap-0.5">
                {mealAchieved && (
                  <div className="w-1.5 h-1.5 rounded-full bg-orange-500" />
                )}
                {activityAchieved && (
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
    
    {/* 범례 */}
    <div className="flex gap-4 mt-4 pt-4 border-t border-gray-200">
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-orange-500" />
        <span className="text-xs text-gray-600">사료 달성</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-blue-500" />
        <span className="text-xs text-gray-600">활동 달성</span>
      </div>
    </div>
  </div>
);
```

---

## 📊 데이터 구조 상세

### TypeScript 인터페이스
```typescript
interface RangeSummaryResponse {
  start_date: string;
  end_date: string;
  records_by_date: Record<string, PetCareRecord[]>;
  
  goal_tracking: {
    days_achieved: {
      meal: number;
      activity: number;
      weight: number;
    };
    achievement_dates: {
      meal: string[];      // ["2025-11-03", "2025-11-04", ...]
      activity: string[];
      weight: string[];
    };
    achievement_rates: {
      meal: number;        // 10.0 (백분율)
      activity: number;
      weight: number;
    };
  };
  
  meta: {
    monthly: {
      encouragement_count: number;
      message: string;
      meal: {
        achievement_count: number;
        achievement_dates: string[];
      };
      activity: {
        achievement_count: number;
        achievement_dates: string[];
      };
    };
  };
  
  trends: {
    weight_trend: Array<{ date: string; weight: number }>;
    meal_frequency_trend: Array<{ date: string; meal_count: number }>;
    activity_trend: Array<{ date: string; activity_minutes: number }>;
  };
}
```

---

## 🔧 실무 팁

### 1. 날짜 필터링
```typescript
// 특정 날짜가 달성 날짜인지 확인
const isAchieved = (date: string, dates: string[]) => dates.includes(date);

// 현재 주의 달성 날짜만 가져오기
const thisWeekAchievements = achievement_dates.filter(date => 
  isThisWeek(new Date(date))
);
```

### 2. 빈 데이터 처리
```typescript
// 목표가 설정되지 않은 경우
if (!response.goal_tracking) {
  return <EmptyGoalState message="목표를 설정해주세요" />;
}

// 달성 기록이 없는 경우
if (monthly.meal.achievement_count === 0) {
  return <EmptyAchievementState message="첫 목표를 달성해보세요!" />;
}
```

### 3. 성능 최적화
```typescript
// 날짜 Set으로 변환하여 빠른 조회
const mealDateSet = new Set(monthly.meal.achievement_dates);
const activityDateSet = new Set(monthly.activity.achievement_dates);

const isDateAchieved = (date: string) => ({
  meal: mealDateSet.has(date),
  activity: activityDateSet.has(date)
});
```

### 4. 애니메이션
```typescript
// Framer Motion 사용 예시
<motion.div
  initial={{ scale: 0 }}
  animate={{ scale: 1 }}
  className="achievement-badge"
>
  ✓
</motion.div>
```

---

## ⚠️ 주의사항

1. **날짜 형식**: 항상 `YYYY-MM-DD` 형식
2. **타임존**: 서버는 KST 기준으로 날짜 생성
3. **빈 배열**: 달성 기록이 없으면 `[]` 반환
4. **목표 미설정**: `goal_tracking`이 `null`일 수 있음

---

## 🎯 요약

| 데이터 | 위치 | 용도 |
|--------|------|------|
| 달성 횟수 | `meta.monthly.meal.achievement_count` | "1일 목표 달성 횟수: 3회" |
| 달성 날짜 | `meta.monthly.meal.achievement_dates` | 캘린더 체크마크 표시 |
| 격려 메시지 | `meta.monthly.message` | "좋은 시작이에요!" |
| 진행률 | `goal_tracking.achievement_rates` | 전체 기간 대비 비율 |

---

더 자세한 API 문서는 [OpenAPI 스펙](../../openapi_pretty.json)을 참조하세요.
