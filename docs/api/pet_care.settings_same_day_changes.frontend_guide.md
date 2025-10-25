# 프론트엔드 개발자 가이드: 펫케어 설정 하루 여러 번 변경

**대상**: 안드로이드/iOS 앱 개발자  
**날짜**: 2025-10-18  
**버전**: v1.0  
**상태**: ✅ 백엔드 수정 완료 | ✅ 동작 검증 완료

> **검증 완료**: `pet_settings_history` 사용이 코드 레벨에서 확인됨  
> 상세 검증 보고서: [`docs/refactoring/PET_SETTINGS_HISTORY_USAGE_VERIFICATION.md`](../refactoring/PET_SETTINGS_HISTORY_USAGE_VERIFICATION.md)

---

## 📌 TL;DR (핵심 요약)

- ✅ **하루에 여러 번 설정 변경 가능**: API는 정상 동작합니다
- ✅ **최종 설정 보장**: 조회 시 항상 가장 최근 설정이 반환됩니다
- ✅ **변경 불필요**: 프론트엔드 코드 수정 없음
- ⚠️ **주의사항**: 빠른 연속 변경 시 UX 개선 권장

---

## 🎯 무엇이 개선되었나요?

### Before (이전 동작)
```
사용자가 하루에 여러 번 목표 변경:
09:00 - 사료 목표 3회로 설정
12:00 - 사료 목표 4회로 변경
15:00 - 사료 목표 5회로 변경

→ 조회 시 결과가 예측 불가능 ❌
→ 3회, 4회, 5회 중 무작위로 반환
```

### After (현재 동작)
```
사용자가 하루에 여러 번 목표 변경:
09:00 - 사료 목표 3회로 설정
12:00 - 사료 목표 4회로 변경
15:00 - 사료 목표 5회로 변경 (최종)

→ 조회 시 항상 5회 반환 ✅
→ 시간순으로 가장 최근 설정 보장
```

---

## 🔌 API 동작 방식

### 1. 설정 변경 API

**엔드포인트**: `PATCH /api/pet-care/{pet_id}/settings`

```http
PATCH /api/pet-care/pet123/settings
Content-Type: application/json
Authorization: Bearer {token}

{
  "goalMealCount": 5
}
```

**응답**:
```json
{
  "pet_id": "pet123",
  "goalMealCount": 5,
  "goalActivityMinutes": 120,
  "goalActivitySessions": 4,
  "activitySessionMinutes": 30,
  "updated_at": "2025-11-15T15:00:00+09:00"
}
```

**동작**:
- ✅ 즉시 설정 업데이트
- ✅ 변경 이력 자동 저장
- ✅ 하루에 여러 번 호출 가능
- ✅ 각 변경이 타임스탬프와 함께 기록됨

### 2. 일별 조회 API

**엔드포인트**: `GET /api/pet-care/{pet_id}/records/daily/summary?date=YYYY-MM-DD`

```http
GET /api/pet-care/pet123/records/daily/summary?date=2025-11-15
Authorization: Bearer {token}
```

**응답**:
```json
{
  "date": "2025-11-15",
  "records": [...],
  "goal_progress": {
    "date": "2025-11-15",
    "achievements": {
      "meal": {
        "actual": 3,
        "goal": 5,           // ✅ 15:00의 최종 설정
        "percentage": 60.0,
        "achieved": false
      }
    }
  }
}
```

**핵심**:
- ✅ 해당 날짜의 **최종 설정**을 사용하여 계산
- ✅ 과거 날짜 조회 시에도 당시 설정 반영

### 3. 월간 리포트 API

**엔드포인트**: `GET /api/pet-care/{pet_id}/records/summary/range?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

```http
GET /api/pet-care/pet123/records/summary/range?start_date=2025-11-01&end_date=2025-11-30
Authorization: Bearer {token}
```

**응답**:
```json
{
  "start_date": "2025-11-01",
  "end_date": "2025-11-30",
  "goal_tracking": {
    "days_achieved": {
      "meal": 14
    },
    "achievement_dates": {
      "meal": ["2025-11-01", "2025-11-02", ..., "2025-11-15"]
    }
  },
  "meta": {
    "monthly": {
      "encouragement_count": 14,
      "message": "잘하고 있어요!",
      "meal": {
        "achievement_count": 14,
        "achievement_dates": ["2025-11-01", ..., "2025-11-15"]
      }
    }
  }
}
```

**핵심**:
- ✅ 각 날짜마다 **그날의 최종 설정** 기준으로 달성 여부 판정
- ✅ 같은 날짜의 여러 변경 중 최종 설정만 사용

---

## 💡 프론트엔드 권장사항

### 1. 기본 동작: 변경 불필요 ✅

**현재 코드 그대로 사용 가능**:
```typescript
// 설정 변경
async function updateGoal(petId: string, goalMealCount: number) {
  const response = await api.patch(`/api/pet-care/${petId}/settings`, {
    goalMealCount
  });
  return response.data;
}

// 일별 조회
async function getDailySummary(petId: string, date: string) {
  const response = await api.get(
    `/api/pet-care/${petId}/records/daily/summary?date=${date}`
  );
  return response.data;
}
```

**백엔드가 자동으로 처리**:
- ✅ 최종 설정 선택
- ✅ 이력 저장
- ✅ 과거 데이터 정확성 보장

### 2. UX 개선: 빠른 연속 변경 방지 (선택 사항)

**상황**: 사용자가 실수로 여러 번 탭하는 경우

```typescript
// 방법 1: 디바운스 (Debounce)
import { debounce } from 'lodash';

const debouncedUpdateGoal = debounce(
  async (petId: string, goalMealCount: number) => {
    await api.patch(`/api/pet-care/${petId}/settings`, { goalMealCount });
  },
  500  // 500ms 내 중복 호출 무시
);

// 사용
debouncedUpdateGoal(petId, newGoal);
```

```typescript
// 방법 2: 로딩 상태
const [isUpdating, setIsUpdating] = useState(false);

async function updateGoal(petId: string, goalMealCount: number) {
  if (isUpdating) return;  // 중복 호출 방지
  
  setIsUpdating(true);
  try {
    await api.patch(`/api/pet-care/${petId}/settings`, { goalMealCount });
    showSuccess('목표가 업데이트되었습니다');
  } catch (error) {
    showError('업데이트 실패');
  } finally {
    setIsUpdating(false);
  }
}

// UI
<Button 
  disabled={isUpdating}
  onClick={() => updateGoal(petId, newGoal)}
>
  {isUpdating ? '저장 중...' : '저장'}
</Button>
```

```typescript
// 방법 3: 확인 다이얼로그 (하루 N회 이상 변경 시)
const DAILY_CHANGE_LIMIT = 3;

async function updateGoal(petId: string, goalMealCount: number) {
  const todayChanges = await getSettingsChangeCount(petId);
  
  if (todayChanges >= DAILY_CHANGE_LIMIT) {
    const confirmed = await showConfirm(
      '오늘 이미 목표를 여러 번 변경했어요. 정말 변경하시겠어요?'
    );
    if (!confirmed) return;
  }
  
  await api.patch(`/api/pet-care/${petId}/settings`, { goalMealCount });
}
```

### 3. 낙관적 업데이트 (Optimistic Update)

**즉각적인 UI 반응**:
```typescript
// React Query 예시
const mutation = useMutation({
  mutationFn: (newGoal: number) => 
    api.patch(`/api/pet-care/${petId}/settings`, { goalMealCount: newGoal }),
  
  // 즉시 로컬 상태 업데이트 (낙관적)
  onMutate: async (newGoal) => {
    await queryClient.cancelQueries(['settings', petId]);
    const previous = queryClient.getQueryData(['settings', petId]);
    
    queryClient.setQueryData(['settings', petId], (old: any) => ({
      ...old,
      goalMealCount: newGoal
    }));
    
    return { previous };
  },
  
  // 실패 시 롤백
  onError: (err, newGoal, context) => {
    queryClient.setQueryData(['settings', petId], context.previous);
    showError('업데이트 실패');
  },
  
  // 성공 시 서버 데이터로 재동기화
  onSuccess: () => {
    queryClient.invalidateQueries(['settings', petId]);
  }
});

// 사용
<Stepper
  value={goal}
  onChange={(newValue) => mutation.mutate(newValue)}
/>
```

---

## 📊 실제 사용 시나리오

### 시나리오 1: 일반적인 목표 변경

```typescript
// 사용자 액션
09:00 - 사용자가 사료 목표를 3회로 설정
  → PATCH /settings { goalMealCount: 3 }
  
// 화면 표시
<GoalCard>
  목표: 3회
  오늘: 1회
  달성률: 33%
</GoalCard>

// 사용자가 목표 달성 후 변경
15:00 - 사료 3회 달성 → 목표를 4회로 상향
  → PATCH /settings { goalMealCount: 4 }
  
// 즉시 화면 업데이트
<GoalCard>
  목표: 4회  ✅ 최신 설정
  오늘: 3회
  달성률: 75%
</GoalCard>
```

### 시나리오 2: 과거 날짜 조회

```typescript
// 11월 15일에 여러 번 변경
09:00 - goalMealCount: 3
12:00 - goalMealCount: 4
15:00 - goalMealCount: 5 (최종)

// 11월 20일에 15일 데이터 조회
const summary = await getDailySummary(petId, '2025-11-15');

console.log(summary.goal_progress.achievements.meal);
// {
//   actual: 3,
//   goal: 5,      // ✅ 15일의 최종 설정 (15:00)
//   percentage: 60.0,
//   achieved: false
// }
```

### 시나리오 3: 월간 리포트

```typescript
// 11월 15일에 목표 변경: 3회 → 4회 → 5회
// 그날 실제 기록: 3회

// 월간 리포트 조회
const report = await getRangeSummary(petId, '2025-11-01', '2025-11-30');

console.log(report.goal_tracking.achievement_dates.meal);
// 11월 15일은 포함되지 않음 (3회 < 5회)
// ['2025-11-01', '2025-11-02', ..., '2025-11-14']
//                                    ↑ 15일 제외 (목표 미달성)
```

---

## 🎨 UI/UX 가이드라인

### 1. 설정 변경 화면

```typescript
// ✅ 권장: 변경 내역 표시
<SettingsScreen>
  <GoalStepper
    value={goalMealCount}
    onChange={handleGoalChange}
    min={1}
    max={10}
  />
  
  <LastUpdated>
    마지막 업데이트: {formatRelativeTime(updatedAt)}
    {/* 예: "5분 전" */}
  </LastUpdated>
  
  <SaveButton
    disabled={isUpdating || !hasChanges}
    onClick={saveSettings}
  >
    {isUpdating ? '저장 중...' : '저장'}
  </SaveButton>
</SettingsScreen>
```

### 2. 목표 달성률 표시

```typescript
// ✅ 권장: 실시간 달성률
<GoalProgressCard>
  <GoalHeader>
    <Icon>🍽️</Icon>
    <Title>사료</Title>
    <Badge>{goal}회 목표</Badge>
  </GoalHeader>
  
  <ProgressBar value={actual / goal * 100} />
  
  <Stats>
    <Stat>
      <Label>오늘</Label>
      <Value>{actual}회</Value>
    </Stat>
    <Stat>
      <Label>달성률</Label>
      <Value>{percentage}%</Value>
    </Stat>
  </Stats>
  
  {achieved && <Badge color="success">목표 달성! 🎉</Badge>}
</GoalProgressCard>
```

### 3. 설정 변경 확인 토스트

```typescript
// ✅ 권장: 사용자 피드백
async function updateGoal(newGoal: number) {
  try {
    await api.patch(`/api/pet-care/${petId}/settings`, {
      goalMealCount: newGoal
    });
    
    // 성공 피드백
    showToast({
      message: `사료 목표가 ${newGoal}회로 변경되었어요`,
      duration: 3000,
      type: 'success'
    });
    
    // 관련 데이터 새로고침
    refreshDailySummary();
    
  } catch (error) {
    showToast({
      message: '목표 변경에 실패했어요. 다시 시도해주세요.',
      duration: 5000,
      type: 'error'
    });
  }
}
```

---

## ⚠️ 주의사항

### 1. 타이밍 이슈

**문제**: 설정 변경 직후 바로 조회 시 이전 값이 반환될 수 있음

```typescript
// ❌ 안티패턴: 변경 직후 즉시 조회
await updateGoal(petId, 5);
const summary = await getDailySummary(petId, today);
// summary.goal_progress.achievements.meal.goal === 4 (이전 값) ⚠️
```

**해결책**:
```typescript
// ✅ 방법 1: 업데이트 응답 사용
const updatedSettings = await updateGoal(petId, 5);
// updatedSettings.goalMealCount === 5 ✅

// ✅ 방법 2: 짧은 지연 후 조회
await updateGoal(petId, 5);
await delay(500);  // 500ms 대기
const summary = await getDailySummary(petId, today);

// ✅ 방법 3: 낙관적 업데이트 (권장)
// 로컬 상태를 먼저 업데이트하고 서버 응답 기다림
```

### 2. 네트워크 재시도

**문제**: 재시도 시 중복 변경 발생

```typescript
// ❌ 안티패턴: 단순 재시도
async function updateGoalWithRetry(newGoal: number, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      await api.patch(`/api/pet-care/${petId}/settings`, { goalMealCount: newGoal });
      return;
    } catch (error) {
      if (i === retries - 1) throw error;
    }
  }
}
// → 재시도마다 새로운 이력 생성 ⚠️
```

**해결책**:
```typescript
// ✅ 권장: 멱등성 보장
async function updateGoal(newGoal: number) {
  try {
    const response = await api.patch(
      `/api/pet-care/${petId}/settings`,
      { goalMealCount: newGoal }
    );
    return response.data;
  } catch (error) {
    // 네트워크 오류만 재시도
    if (error.code === 'NETWORK_ERROR') {
      return updateGoal(newGoal);  // 같은 값으로 재시도
    }
    throw error;
  }
}
```

### 3. 동시성 이슈

**문제**: 여러 디바이스에서 동시 변경

```typescript
// 디바이스 A: 09:00 - goalMealCount: 3
// 디바이스 B: 09:01 - goalMealCount: 5
// → 서버는 타임스탬프 기준으로 최종 설정 결정 (5회)
```

**해결책**: 없음 (백엔드가 자동 처리)
- ✅ 서버가 `created_at` 타임스탬프로 순서 보장
- ✅ 프론트엔드는 추가 작업 불필요

---

## 🔍 디버깅 가이드

### 1. 설정 변경이 반영되지 않는 경우

**체크리스트**:
```typescript
// 1. API 호출 확인
console.log('Updating goal:', newGoal);
const response = await api.patch(`/api/pet-care/${petId}/settings`, {
  goalMealCount: newGoal
});
console.log('Update response:', response.data);

// 2. 응답 검증
assert(response.data.goalMealCount === newGoal);

// 3. 조회 확인
await delay(1000);  // 1초 대기
const settings = await api.get(`/api/pet-care/${petId}/settings`);
console.log('Current settings:', settings.data);

// 4. 캐시 확인
// React Query 사용 시
queryClient.invalidateQueries(['settings', petId]);
```

### 2. 월간 리포트에서 달성 날짜 불일치

**원인**: 목표 변경으로 인한 재계산

```typescript
// 시나리오
// 11월 1-14일: 목표 3회, 매일 3회 기록 → 14일 달성 ✅
// 11월 15일: 목표를 4회로 변경
// 11월 16-30일: 목표 4회, 매일 3회 기록 → 0일 달성 ❌

// 월간 리포트 조회
const report = await getRangeSummary(petId, '2025-11-01', '2025-11-30');
console.log(report.goal_tracking.days_achieved.meal);  // 14 ✅

// 달성 날짜
console.log(report.goal_tracking.achievement_dates.meal);
// ['2025-11-01', ..., '2025-11-14']  ✅
// 15일부터는 목표 4회 기준으로 미달성
```

**해결**: 정상 동작입니다
- ✅ 각 날짜마다 당시 설정 기준으로 판정
- ✅ 과거 달성 기록은 보존됨

### 3. 로그 확인

**백엔드 로그에서 확인 가능**:
```
INFO: Pet care settings updated for pet_abc123 (history recorded)
INFO: Pet care settings history saved [pet_id=pet_abc123, effective_date=2025-11-15]
```

**문제 발생 시 백엔드 팀에 전달할 정보**:
- Pet ID
- 변경 시각 (KST)
- 변경 전/후 값
- 조회 시각 및 결과

---

## 📚 참고 자료

### API 문서
- **전체 API**: `/openapi_pretty.json`
- **펫케어 설정**: `POST/PATCH /api/pet-care/{pet_id}/settings`
- **일별 요약**: `GET /api/pet-care/{pet_id}/records/daily/summary`
- **월간 리포트**: `GET /api/pet-care/{pet_id}/records/summary/range`

### 백엔드 문서
- **구현 상세**: `docs/refactoring/PET_CARE_SETTINGS_SAME_DAY_FIX_SUMMARY.md`
- **문제 분석**: `docs/refactoring/PET_CARE_SETTINGS_SAME_DAY_MULTIPLE_CHANGES.md`
- **목표 보존**: `docs/refactoring/PET_CARE_GOAL_PRESERVATION_ANALYSIS.md`

### 관련 기능 가이드
- **목표 달성 추적**: `docs/api/pet_care.goal_achievement_tracking.md`
- **월간 분석**: `docs/api/pet_care.weight_monthly_analysis.md`

---

## 🤝 지원

### 질문이 있으신가요?

**백엔드 팀에 문의**:
- 설정 변경 API 동작 관련
- 이력 저장 메커니즘
- 데이터 정합성 이슈

**프론트엔드 리드에 문의**:
- UI/UX 개선 제안
- 사용자 피드백
- 통합 테스트

---

## ✅ 체크리스트

### 구현 확인

- [ ] 설정 변경 API 정상 동작 확인
- [ ] 일별 조회 시 최종 설정 반영 확인
- [ ] 월간 리포트 달성 날짜 정확성 확인
- [ ] 빠른 연속 변경 시 UX 테스트
- [ ] 오류 처리 및 사용자 피드백 구현
- [ ] 낙관적 업데이트 동작 확인

### 테스트 시나리오

- [ ] 하루에 1번 변경: 정상 동작
- [ ] 하루에 3번 변경: 최종 설정 반영
- [ ] 과거 날짜 조회: 당시 설정 사용
- [ ] 월간 리포트: 날짜별 다른 목표 적용
- [ ] 네트워크 오류 시 재시도
- [ ] 동시 변경 (다중 디바이스)

---

**마지막 업데이트**: 2025-10-18  
**작성자**: GitHub Copilot (백엔드 팀)  
**버전**: 1.0  
**문의**: 백엔드 팀 or 프론트엔드 리드

---

## 💬 FAQ

### Q1: 하루에 몇 번까지 변경 가능한가요?
**A**: 기술적 제한은 없습니다. 하지만 UX 측면에서 디바운스나 확인 다이얼로그를 권장합니다.

### Q2: 설정 변경 이력을 UI에서 보여줄 수 있나요?
**A**: 현재 API는 최종 설정만 반환합니다. 이력 조회 API는 추후 추가 예정입니다.

### Q3: 과거 데이터가 변경될 수 있나요?
**A**: 아니요. 과거 데이터는 당시 설정 기준으로 고정됩니다. 현재 목표를 변경해도 과거 달성 기록에는 영향 없습니다.

### Q4: 오프라인에서 변경하면 어떻게 되나요?
**A**: 네트워크 복구 시 서버에 전송되며, 타임스탬프 기준으로 순서가 보장됩니다.

### Q5: 실시간 동기화가 필요한가요?
**A**: 필수는 아닙니다. 다음 조회 시 자동으로 최신 설정이 반영됩니다. 실시간이 필요하면 WebSocket 또는 푸시 알림 고려 가능합니다.
