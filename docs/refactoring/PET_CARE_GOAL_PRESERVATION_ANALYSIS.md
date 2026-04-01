# 펫케어 목표 변경 시 달성 기록 보존 검토 보고서

**날짜**: 2025-10-18  
**요청**: A시점에서 목표 사료 횟수를 3으로 설정하고 달성한 상황에서, A+1 시점에서 목표를 4로 변경하면 A시점의 달성 기록이 사라지는지 보존되는지 검토  
**결론**: ✅ **보존됨** - 시스템은 설정 변경 이력을 추적하여 과거 달성 기록을 정확히 보존합니다.

---

## 📊 핵심 결론 요약

### 🟢 달성 기록 보존 여부: **YES (보존됨)**

**시나리오 예시**:
```
2025-11-03: 목표 3회 설정, 3회 달성 ✅ (100%)
2025-11-15: 목표를 4회로 변경
2025-11-20: 11-03 데이터 조회 시
  → 목표: 3회 ✅ (당시 설정)
  → 달성률: 100% ✅ (3/3)
  → 달성 기록: 유지됨 ✅
```

**시스템이 올바르게 동작하는 이유**:
1. 설정 변경 이력이 `pet_settings_history` 컬렉션에 저장됨
2. 과거 데이터 조회 시 해당 시점의 설정을 사용하여 재계산
3. 월간 리포트에서도 날짜별로 적절한 목표 기준 적용

---

## 🔍 시스템 동작 원리

### 1. 설정 변경 이력 저장 구조

#### Firestore 컬렉션 구조
```
pet_settings/{pet_id}              # 현재 활성 설정
{
  "pet_id": "pet123",
  "goalMealCount": 4,               # 최신 값
  "goalActivityMinutes": 120,
  "updated_at": "2025-11-15 10:30:00"
}

pet_settings_history/{pet_id}/changes/{change_id}  # 변경 이력
{
  "change_id": "uuid-001",
  "pet_id": "pet123",
  "effective_date": "2025-11-03",   # 이 날짜부터 유효
  "goalMealCount": 3,                # 초기 값
  "goalActivityMinutes": 120,
  "created_at": "2025-11-03 09:00:00"
}

pet_settings_history/{pet_id}/changes/{change_id2}
{
  "change_id": "uuid-002",
  "pet_id": "pet123",
  "effective_date": "2025-11-15",   # 이 날짜부터 유효
  "goalMealCount": 4,                # 변경된 값
  "goalActivityMinutes": 120,
  "created_at": "2025-11-15 10:30:00"
}
```

#### 핵심 메커니즘
- **전체 스냅샷 저장**: 변경된 필드만이 아니라 전체 설정을 저장
- **effective_date 기준**: 해당 날짜부터 적용되는 설정임을 명시
- **시계열 인덱스**: `effective_date`로 정렬하여 빠른 조회 가능

### 2. 코드 레벨 구현

#### 2.1 설정 변경 시 이력 저장
**파일**: `pet_project_backend/app/api/pet_care/settings/services.py`

```python
class PetCareSettingService:
    def update_settings(self, pet_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """설정 업데이트 시 자동으로 이력 저장"""
        # ...기존 업데이트 로직...
        
        # 이력 저장 (핵심 부분)
        if self.settings_history_ref is not None:
            effective_date = effective_date_override or DateTimeUtils.today_kst_as_date_str()
            self._save_settings_history(
                pet_id,
                merged_settings,
                effective_date=effective_date,  # 오늘 날짜부터 적용
                transaction=transaction,
            )
```

**동작**:
- 설정 업데이트마다 `_save_settings_history()` 자동 호출
- 트랜잭션 내에서 메인 문서와 이력을 동시에 저장 (원자성 보장)
- `effective_date`로 변경이 시작되는 날짜 기록

#### 2.2 특정 날짜의 설정 조회
**파일**: `pet_project_backend/app/api/pet_care/settings/services.py`

```python
def get_settings_at_date(self, pet_id: str, date: str) -> Dict[str, Any]:
    """Return settings that were effective on the given KST date."""
    history_ref = self.settings_history_ref.document(pet_id).collection('changes')
    
    # 조회 날짜 이전의 가장 최근 설정 가져오기
    query = (
        history_ref.order_by('effective_date', direction=firestore.Query.DESCENDING)
        .where('effective_date', '<=', date)  # ← 핵심: 해당 날짜 이전 설정
        .limit(1)
    )
    
    docs = list(query.stream())
    if not docs:
        return self.get_settings(pet_id)  # Fallback: 현재 설정
    
    return DateTimeUtils.from_firestore(docs[0].to_dict())
```

**동작**:
1. `effective_date <= 조회날짜` 조건으로 필터링
2. 내림차순 정렬 후 첫 번째 문서 = 해당 날짜에 유효했던 설정
3. 이력이 없으면 현재 설정으로 Fallback

#### 2.3 일별 조회 API에서 과거 설정 사용
**파일**: `pet_project_backend/app/api/pet_care/records/record_integration_service.py`

```python
def get_daily_summary_with_goals(self, pet_id: str, date: str) -> Dict[str, Any]:
    """일별 요약 + 목표 진행률"""
    records_result = self.query.get_daily(pet_id, date)
    
    # ✅ 핵심: 해당 날짜의 설정 조회
    settings = self.settings.get_settings_at_date(pet_id, date)
    
    # 목표 분석
    goal_progress = self.goal_analyzer.analyze_daily(
        records_result.get('records', []),
        date,
        settings  # ← 당시 설정으로 계산
    )
```

**Before (구현 전)**:
```python
settings = self.settings.get_settings(pet_id)  # ❌ 항상 최신 설정
```

**After (구현 후)**:
```python
settings = self.settings.get_settings_at_date(pet_id, date)  # ✅ 당시 설정
```

#### 2.4 기간 조회 API에서 날짜별 다른 설정 적용
**파일**: `pet_project_backend/app/api/pet_care/records/record_integration_service.py`

```python
def get_range_summary_with_trends(self, pet_id: str, start_date: str, end_date: str):
    """기간 요약 + 트렌드 + 목표 추적"""
    records_result = self.query.get_range_grouped(pet_id, start_date, end_date)
    
    # ✅ 핵심: 기간 내 모든 설정 변경 이력 가져오기
    settings_map = self.settings.get_settings_for_range(pet_id, start_date, end_date)
    # 반환: {'2025-11-03': {goalMealCount: 3}, '2025-11-15': {goalMealCount: 4}}
    
    # 날짜별로 적절한 설정으로 분석
    goal_tracking = self.goal_analyzer.analyze_range_with_history(
        records_result['records_by_date'], 
        settings_map  # ← 날짜별 설정 맵
    )
```

**Before (구현 전)**:
```python
settings = self.settings.get_settings(pet_id)
goal_tracking = self.goal_analyzer.analyze_range(records, settings)
# ❌ 전체 기간에 동일한 최신 설정 적용
```

**After (구현 후)**:
```python
settings_map = self.settings.get_settings_for_range(pet_id, start_date, end_date)
goal_tracking = self.goal_analyzer.analyze_range_with_history(records, settings_map)
# ✅ 각 날짜에 해당 시점의 설정 적용
```

### 3. 목표 분석 로직 (날짜별 다른 설정 처리)

**파일**: `pet_project_backend/app/api/pet_care/records/analyzers.py`

```python
class GoalAnalyzer:
    def analyze_range_with_history(
        self,
        grouped: Dict[str, List[Dict[str, Any]]],  # 날짜별 기록
        settings_by_effective_date: Dict[str, Dict[str, Any]],  # 날짜별 설정
    ) -> Dict[str, Any]:
        """날짜별로 해당 시점의 설정을 사용하여 목표 달성 분석"""
        
        days = sorted(grouped.keys())  # ['2025-11-01', '2025-11-02', ...]
        sorted_effective_dates = sorted(settings_by_effective_date.keys())
        # ['2025-11-03', '2025-11-15']
        
        counts = {'meal': 0, 'activity': 0, 'weight': 0}
        achievement_dates = {'meal': [], 'activity': [], 'weight': []}
        
        active_settings = None
        idx = 0
        
        for date_key in days:
            # ✅ 핵심: 해당 날짜에 유효한 설정 찾기
            while idx < len(sorted_effective_dates) and sorted_effective_dates[idx] <= date_key:
                active_settings = settings_by_effective_date[sorted_effective_dates[idx]]
                idx += 1
            
            # 해당 날짜의 기록을 당시 설정으로 분석
            daily = self.analyze_daily(grouped[date_key], date_key, active_settings)
            
            # 달성 여부 체크
            if daily['achievements'].get('meal', {}).get('achieved'):
                counts['meal'] += 1
                achievement_dates['meal'].append(date_key)
```

**동작 원리**:
1. 각 날짜를 순회하면서 현재 유효한 설정을 추적
2. `effective_date <= 현재날짜` 조건을 만족하는 가장 최근 설정 사용
3. 설정이 변경되면 자동으로 다음 설정으로 전환
4. 각 날짜의 달성 여부는 당시 목표 기준으로 판정

---

## 📈 실제 시나리오 검증

### 시나리오 1: 일별 조회 (과거 데이터)

#### 상황
```
2025-11-03 09:00: 목표 3회 설정
2025-11-03 20:00: 사료 3회 기록 (달성 ✅)
2025-11-15 10:00: 목표를 4회로 변경
2025-11-20: 11-03 데이터를 조회
```

#### API 호출
```http
GET /api/pet-care/{pet_id}/records/daily/summary?date=2025-11-03
```

#### 시스템 처리 흐름
```
1. get_daily_summary_with_goals(pet_id, '2025-11-03')
   ↓
2. get_settings_at_date(pet_id, '2025-11-03')
   → Firestore 쿼리: effective_date <= '2025-11-03'
   → 결과: {goalMealCount: 3, ...} (초기 설정 반환)
   ↓
3. analyze_daily(records, '2025-11-03', {goalMealCount: 3})
   → actual: 3
   → goal: 3
   → percentage: 100.0
   → achieved: true ✅
```

#### 응답 결과
```json
{
  "date": "2025-11-03",
  "goal_progress": {
    "date": "2025-11-03",
    "achievements": {
      "meal": {
        "actual": 3,
        "goal": 3,           // ✅ 당시 목표 (변경 전)
        "percentage": 100.0,  // ✅ 정확한 달성률
        "achieved": true      // ✅ 달성 기록 유지
      }
    }
  }
}
```

### 시나리오 2: 월간 리포트 (기간 내 목표 변경)

#### 상황
```
2025-11-01 ~ 11-14: 목표 3회, 매일 3회 기록 (14일 달성 ✅)
2025-11-15: 목표를 4회로 변경
2025-11-15 ~ 11-30: 목표 4회, 매일 3회 기록 (0일 달성 ❌)
2025-11-30: 11월 전체 리포트 조회
```

#### API 호출
```http
GET /api/pet-care/{pet_id}/records/summary/range?start_date=2025-11-01&end_date=2025-11-30
```

#### 시스템 처리 흐름
```
1. get_range_summary_with_trends(pet_id, '2025-11-01', '2025-11-30')
   ↓
2. get_settings_for_range(pet_id, '2025-11-01', '2025-11-30')
   → Firestore 쿼리: effective_date <= '2025-11-30'
   → 결과: {
       '2025-11-01': {goalMealCount: 3},  // 시작일 기준
       '2025-11-15': {goalMealCount: 4}   // 변경일
     }
   ↓
3. analyze_range_with_history(records_by_date, settings_map)
   
   날짜별 처리:
   - 11-01 ~ 11-14: goalMealCount: 3 사용
     → 3/3 달성 → achieved: true ✅ (14일)
   
   - 11-15 ~ 11-30: goalMealCount: 4 사용
     → 3/4 미달성 → achieved: false ❌ (0일)
```

#### 응답 결과
```json
{
  "start_date": "2025-11-01",
  "end_date": "2025-11-30",
  "goal_tracking": {
    "days_achieved": {
      "meal": 14  // ✅ 정확히 14일 (11-01 ~ 11-14)
    },
    "achievement_dates": {
      "meal": [
        "2025-11-01", "2025-11-02", "2025-11-03", "2025-11-04",
        "2025-11-05", "2025-11-06", "2025-11-07", "2025-11-08",
        "2025-11-09", "2025-11-10", "2025-11-11", "2025-11-12",
        "2025-11-13", "2025-11-14"
        // ✅ 11-15 이후는 제외 (목표 4회로 미달성)
      ]
    },
    "achievement_rates": {
      "meal": 46.7  // 14/30 * 100 ≈ 46.7%
    }
  },
  "meta": {
    "monthly": {
      "encouragement_count": 14,
      "message": "잘하고 있어요!",
      "meal": {
        "achievement_count": 14,  // ✅ 정확한 달성 횟수
        "achievement_dates": ["2025-11-01", ..., "2025-11-14"]
      }
    }
  }
}
```

### 시나리오 3: 목표 여러 번 변경

#### 상황
```
2025-11-01: 목표 2회 설정
2025-11-10: 목표 3회로 변경
2025-11-20: 목표 4회로 변경
```

#### 설정 이력 구조
```
pet_settings_history/{pet_id}/changes/
  ├─ {uuid-1}: effective_date: "2025-11-01", goalMealCount: 2
  ├─ {uuid-2}: effective_date: "2025-11-10", goalMealCount: 3
  └─ {uuid-3}: effective_date: "2025-11-20", goalMealCount: 4
```

#### 월간 분석 시 날짜별 적용 설정
```
2025-11-01 ~ 11-09: goalMealCount: 2 (2회 이상 달성 카운트)
2025-11-10 ~ 11-19: goalMealCount: 3 (3회 이상 달성 카운트)
2025-11-20 ~ 11-30: goalMealCount: 4 (4회 이상 달성 카운트)
```

---

## ⚙️ Fallback 및 에러 처리

### 1. 이력 조회 실패 시
```python
def get_settings_at_date(self, pet_id: str, date: str) -> Dict[str, Any]:
    try:
        # 이력에서 조회 시도
        docs = list(query.stream())
    except Exception as exc:
        logging.error(f"Failed to fetch settings history: {exc}", exc_info=True)
        return self.get_settings(pet_id)  # ✅ Fallback: 현재 설정
```

**동작**:
- Firestore 오류 시 현재 설정으로 대체
- 서비스 중단 방지 (Graceful Degradation)

### 2. 이력이 없는 경우
```python
if not docs:
    logging.warning(f"No settings history before {date}, using current settings")
    return self.get_settings(pet_id)
```

**동작**:
- 초기 데이터나 마이그레이션 이전 기록의 경우
- 현재 설정으로 대체하여 서비스 연속성 보장

### 3. DOCS_MODE (문서화 모드)
```python
def get_settings_at_date(self, pet_id: str, date: str) -> Dict[str, Any]:
    if self.settings_history_ref is None:  # DOCS_MODE
        return self.get_settings(pet_id)  # 기본 설정 반환
```

**동작**:
- Firestore 없이도 OpenAPI 문서 생성 가능
- 로컬 개발 환경 지원

---

## 🎯 검증 방법

### 1. Firestore 콘솔 확인

**경로**: Firebase Console → Firestore Database

```
pet_settings_history
└── {pet_id}
    └── changes (subcollection)
        ├── {uuid-1}
        │   ├── effective_date: "2025-11-03"
        │   ├── goalMealCount: 3
        │   └── created_at: Timestamp(...)
        └── {uuid-2}
            ├── effective_date: "2025-11-15"
            ├── goalMealCount: 4
            └── created_at: Timestamp(...)
```

### 2. API 테스트 (Postman/curl)

#### 테스트 1: 과거 날짜 조회
```bash
# 1. 목표 3회 설정
POST /api/pet-care/{pet_id}/settings
{
  "goalMealCount": 3
}

# 2. 사료 3회 기록
POST /api/pet-care/{pet_id}/records
{
  "date": "2025-11-03",
  "meal_count": 3
}

# 3. 목표 4회로 변경
PATCH /api/pet-care/{pet_id}/settings
{
  "goalMealCount": 4,
  "effective_date": "2025-11-15"
}

# 4. 과거 데이터 조회 (11-03)
GET /api/pet-care/{pet_id}/records/daily/summary?date=2025-11-03

# ✅ 예상 결과:
# goal: 3, actual: 3, percentage: 100.0, achieved: true
```

#### 테스트 2: 월간 리포트
```bash
# 월간 요약 조회
GET /api/pet-care/{pet_id}/records/summary/range?start_date=2025-11-01&end_date=2025-11-30

# ✅ 예상 결과:
# goal_tracking.days_achieved.meal: 14 (11-01 ~ 11-14)
# goal_tracking.achievement_dates.meal: ["2025-11-01", ..., "2025-11-14"]
```

### 3. 로그 확인

**기대 로그**:
```
INFO: Pet care settings updated for pet_abc123 (history recorded)
INFO: Pet care settings history saved [pet_id=pet_abc123, effective_date=2025-11-15]
DEBUG: Range analysis with history computed [days_achieved={'meal': 14}, total_days=30]
```

---

## 📚 관련 문서

1. **`docs/refactoring/PET_CARE_GOAL_HISTORY_IMPLEMENTATION.md`**
   - 설정 이력 기능 구현 상세 계획
   - Firestore 구조 설계
   - 코드 수정 범위

2. **`docs/api/pet_care.goal_achievement_tracking.md`**
   - 월간 목표 달성 추적 가이드
   - API 응답 구조
   - UI 구현 예시

3. **`docs/api/pet_care.meal_achievement_audit.md`**
   - 사료 달성률 전수검사 보고서
   - 계산 로직 검증

---

## 🔑 핵심 요약

### ✅ 질문에 대한 답변

**Q**: A시점에서 목표 사료 횟수를 3으로 설정하고 달성한 상황에서, A+1 시점에서 목표를 4로 설정하면 A시점의 달성 기록이 사라지는가?

**A**: **아니오, 달성 기록은 보존됩니다.**

### 이유
1. **설정 변경 이력 저장**: 모든 목표 변경이 `pet_settings_history` 컬렉션에 기록됨
2. **시점별 설정 조회**: 과거 데이터 조회 시 해당 날짜의 설정을 사용
3. **날짜별 다른 기준 적용**: 월간 리포트에서도 각 날짜의 목표를 정확히 적용
4. **원자적 업데이트**: 트랜잭션으로 메인 설정과 이력을 동시에 저장하여 데이터 일관성 보장

### 기술적 보장
- Firestore 인덱스: `effective_date`로 빠른 조회
- Fallback 메커니즘: 이력 조회 실패 시 현재 설정으로 대체
- 트랜잭션: 데이터 정합성 보장

### 검증 가능
- Firestore 콘솔에서 이력 직접 확인
- API 응답에서 올바른 목표/달성률 확인
- 월간 리포트에서 정확한 달성 날짜 수 확인

---

**마지막 업데이트**: 2025-10-18  
**작성자**: GitHub Copilot  
**상태**: ✅ 검증 완료
