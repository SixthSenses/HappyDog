# 펫케어 목표 설정 이력 저장 구현 계획

## 📋 문제 정의

### 핵심 이슈
**과거 데이터의 목표값이 현재 설정으로 덮어써지는 문제**

### 증상

#### 1. Daily Summary API 문제
```
시나리오:
1. 2025-10-01: 식사 목표 3회로 설정, 3회 달성 ✅
2. 2025-10-10: 식사 목표를 4회로 변경
3. 2025-10-18: 2025-10-01 데이터 조회 시
   - 기대: 목표 3회, 달성률 100% ✅
   - 실제: 목표 4회, 달성률 75% ❌ (3/4 = 75%)
```

**문제**: 과거 날짜를 조회할 때도 최신 설정(4회)으로 재계산됨

#### 2. Range Summary API 문제
```
시나리오:
1. 2025-10월 전체: 식사 목표 3회, 15일 달성 ✅
2. 2025-10-15: 식사 목표를 4회로 변경
3. 2025-10-18: 월간 분석 조회 시
   - 기대: 10/1~10/14는 3회 기준, 10/15~는 4회 기준
   - 실제: 전체 기간이 4회 기준으로 재계산됨
   - 결과: 달성 날짜가 15일 → 5일로 줄어듦 ❌
```

**문제**: 월간 리포트의 달성률과 달성 날짜가 왜곡됨

### 근본 원인

```python
# record_integration_service.py
def get_daily_summary_with_goals(self, pet_id: str, date: str):
    settings = self.settings.get_settings(pet_id)  # ← 항상 최신 설정만 조회!
    goal_progress = self.goal_analyzer.analyze_daily(records, date, settings)
```

```python
# record_integration_service.py
def get_range_summary_with_trends(self, pet_id: str, start_date: str, end_date: str):
    settings = self.settings.get_settings(pet_id)  # ← 항상 최신 설정만 조회!
    goal_tracking = self.goal_analyzer.analyze_range(records_by_date, settings)
```

**핵심**: `get_settings(pet_id)`는 현재 저장된 최신 목표만 반환하며, 특정 날짜의 목표를 조회하는 기능이 없음.

---

## 🎯 해결 방안: 설정 변경 이력 저장

### Firestore 구조 설계

#### 현재 구조 (유지)
```
pet_settings/{pet_id}  # 현재 활성 설정
{
  "pet_id": "pet123",
  "goalWeight": 15.5,
  "goalMealCount": 3,
  "goalActivitySessions": 4,
  "activitySessionMinutes": 30,
  "goalActivityMinutes": 120,  # 파생 필드
  "activityIncrementMinutes": 10,
  "mealIncrementCount": 1,
  "created_at": Timestamp(2025-10-01 00:00:00),
  "updated_at": Timestamp(2025-10-15 14:30:00)
}
```

#### 신규 구조 (추가)
```
pet_settings_history/{pet_id}/changes/{change_id}  # 변경 이력
{
  "change_id": "uuid-string",
  "pet_id": "pet123",
  "effective_date": "2025-10-15",  # 이 날짜부터 유효
  "goalWeight": 16.0,
  "goalMealCount": 4,  # 3 → 4로 변경
  "goalActivitySessions": 4,
  "activitySessionMinutes": 30,
  "goalActivityMinutes": 120,
  "activityIncrementMinutes": 10,
  "mealIncrementCount": 1,
  "created_at": Timestamp(2025-10-15 14:30:00)
}
```

**설계 원칙**:
1. **Subcollection 사용**: `pet_settings_history/{pet_id}/changes/` - 펫별로 이력 관리
2. **effective_date 기준**: 해당 날짜부터 적용되는 설정
3. **전체 스냅샷 저장**: 변경된 필드만이 아니라 전체 설정 저장 (조회 단순화)
4. **최초 설정도 이력화**: Pet 생성 시 최초 설정을 history에도 저장

### 인덱스 요구사항

```
Collection: pet_settings_history/{pet_id}/changes
Indexes:
- effective_date (ASC)  → 날짜 범위 쿼리
```

---

## 🔍 수정 범위 분석

### 1. 핵심 수정 파일

#### 1.1 `app/api/pet_care/settings/services.py` ⭐ 핵심
**현재 메서드**:
- `__init__()`: Firestore 컬렉션 초기화
- `create_initial_settings_transactional()`: 최초 설정 생성
- `get_settings()`: 현재 설정 조회
- `update_settings()`: 설정 수정

**추가 필요 메서드**:
- `get_settings_at_date(pet_id, date)`: 특정 날짜의 설정 조회 (이력 기반)
- `get_settings_for_range(pet_id, start_date, end_date)`: 기간 내 설정 변경 이력 조회
- `_save_settings_history()`: 설정 변경 이력 저장 (private)

**수정 필요 메서드**:
- `create_initial_settings_transactional()`: 최초 설정을 history에도 저장
- `update_settings()`: 설정 수정 시 history 추가

#### 1.2 `app/api/pet_care/records/record_integration_service.py` ⭐ 핵심
**수정 필요 메서드**:
- `get_daily_summary_with_goals()`: 
  - 변경 전: `settings = self.settings.get_settings(pet_id)`
  - 변경 후: `settings = self.settings.get_settings_at_date(pet_id, date)`

- `get_range_summary_with_trends()`:
  - 변경 전: 단일 settings로 전체 기간 분석
  - 변경 후: 날짜별로 해당 시점의 settings 사용

#### 1.3 `app/api/pet_care/records/analyzers.py`
**수정 필요 메서드**:
- `GoalAnalyzer.analyze_range()`:
  - 변경 전: 단일 settings 파라미터
  - 변경 후: `Dict[date, settings]` 맵 지원 (날짜별 다른 설정)

### 2. 재활용 가능한 코드

#### 2.1 DateTimeUtils (완전 재활용 ✅)
```python
from app.utils.datetime_utils import DateTimeUtils

# 날짜 문자열 파싱
date_obj = DateTimeUtils.parse_date('2025-10-15')

# KST 기준 오늘 날짜
today = DateTimeUtils.today_kst_as_date_str()

# Firestore 저장용 변환
firestore_data = DateTimeUtils.for_firestore(data)

# datetime 비교
dt1 = DateTimeUtils.parse_iso_datetime('2025-10-15T14:30:00+09:00')
dt2 = DateTimeUtils.now()
```

#### 2.2 Firestore 쿼리 패턴 (참고 가능 ✅)
```python
# 기존 코드에서 사용 중인 패턴
# pet_care/records/repository.py - list_by_range()
query = (
    self.logs_ref
    .where('pet_id', '==', pet_id)
    .where('searchDate', '>=', start_date)
    .where('searchDate', '<=', end_date)
    .order_by('searchDate')
    .order_by('timestamp')
)
docs = list(query.stream())
```

**적용**: settings_history에서 effective_date 기준 범위 쿼리

#### 2.3 Firestore Transaction 패턴 (참고 가능 ✅)
```python
# 기존 코드: settings/services.py - create_initial_settings_transactional()
def create_initial_settings_transactional(self, transaction: Transaction, ...):
    firestore_data = DateTimeUtils.for_firestore(settings_data)
    settings_doc_ref = self.settings_ref.document(pet_id)
    transaction.set(settings_doc_ref, firestore_data)
```

**적용**: 설정 업데이트 시 메인 문서 + history 동시 저장 (원자성 보장)

#### 2.4 Subcollection 패턴 (참고 가능 ✅)
```python
# Firestore subcollection 접근 패턴
# notifications/{notification_id} 참고
history_ref = self.db.collection('pet_settings_history') \
                     .document(pet_id) \
                     .collection('changes')
```

---

## 🛠️ 상세 구현 계획

### Phase 1: Settings Service 확장

#### Step 1.1: 생성자 수정
```python
class PetCareSettingService:
    def __init__(self, breed_service: BreedService, db_client=None):
        self.breed_service = breed_service
        self.db: Optional[firestore.Client] = db_client
        self.settings_ref = self.db.collection('pet_settings') if self.db else None
        
        # ✨ 신규: 설정 이력 컬렉션 참조 추가
        if self.db:
            self.settings_history_ref = self.db.collection('pet_settings_history')
        else:
            self.settings_history_ref = None
```

#### Step 1.2: 설정 이력 저장 메서드 추가 (Private)
```python
def _save_settings_history(
    self, 
    pet_id: str, 
    settings_data: Dict[str, Any], 
    effective_date: Optional[str] = None,
    transaction: Optional[Transaction] = None
) -> None:
    """설정 변경 이력을 저장합니다.
    
    Args:
        pet_id: 펫 ID
        settings_data: 전체 설정 데이터 (스냅샷)
        effective_date: 유효 시작 날짜 (YYYY-MM-DD), None이면 오늘
        transaction: Firestore Transaction (원자성 보장용, 선택)
    """
    if self.settings_history_ref is None:
        logging.info("DOCS_MODE: skip saving settings history")
        return
    
    # effective_date 기본값: 오늘 (KST)
    if effective_date is None:
        effective_date = DateTimeUtils.today_kst_as_date_str()
    
    # 이력 데이터 구성
    history_data = {
        'pet_id': pet_id,
        'effective_date': effective_date,
        'created_at': DateTimeUtils.now(),
        **settings_data  # 전체 설정 스냅샷
    }
    
    # Firestore 변환
    firestore_data = DateTimeUtils.for_firestore(history_data)
    
    # 이력 문서 저장 (pet_settings_history/{pet_id}/changes/{auto_id})
    history_ref = self.settings_history_ref.document(pet_id).collection('changes')
    
    if transaction:
        # 트랜잭션 내에서 저장
        new_doc_ref = history_ref.document()  # auto-generated ID
        transaction.set(new_doc_ref, firestore_data)
    else:
        # 독립 저장
        history_ref.add(firestore_data)
    
    logging.info(f"Settings history saved for pet {pet_id}, effective_date={effective_date}")
```

#### Step 1.3: 최초 생성 시 이력 저장
```python
def create_initial_settings_transactional(
    self, 
    transaction: Transaction, 
    pet_id: str, 
    gender: str, 
    breed: str, 
    current_weight: float
):
    """최초 반려동물 등록 시 초기 설정값을 생성합니다. (트랜잭션)"""
    try:
        if self.settings_ref is None:
            logging.info("PetCareSettingService: DOCS_MODE - skip transactional create")
            return
        
        # 1. 품종별 이상 체중 조회
        ideal_weight = self.breed_service.get_breed_ideal_weight(breed, gender)
        goal_weight = ideal_weight if ideal_weight is not None else current_weight

        settings_data = {
            "pet_id": pet_id,
            "goalWeight": goal_weight,
            "goalActivityMinutes": 120,
            "goalActivitySessions": 4,
            "activitySessionMinutes": 30,
            "activityIncrementMinutes": 10,
            "goalMealCount": 3,
            "mealIncrementCount": 1,
            "created_at": DateTimeUtils.now(),
            "updated_at": DateTimeUtils.now()
        }
        
        firestore_data = DateTimeUtils.for_firestore(settings_data)
        
        # 2. 메인 설정 문서 생성 (트랜잭션)
        settings_doc_ref = self.settings_ref.document(pet_id)
        transaction.set(settings_doc_ref, firestore_data)
        
        # ✨ 3. 설정 이력도 함께 저장 (트랜잭션 내)
        # Pet 생성일 = 최초 설정의 effective_date
        self._save_settings_history(
            pet_id, 
            settings_data, 
            effective_date=DateTimeUtils.today_kst_as_date_str(),
            transaction=transaction
        )
        
        logging.info(f"Transaction: Pet care settings + history created for {pet_id}")

    except Exception as e:
        logging.error(f"Failed to create initial settings for pet {pet_id}: {e}", exc_info=True)
        raise
```

#### Step 1.4: 설정 수정 시 이력 저장
```python
def update_settings(self, pet_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """설정을 수정하고 이력을 저장합니다."""
    if self.settings_ref is None:
        logging.info("PetCareSettingService: DOCS_MODE - update skipped")
        return self.get_settings(pet_id)
    
    doc_ref = self.settings_ref.document(pet_id)
    if not doc_ref.get().exists:
        raise FileNotFoundError("해당 반려동물의 펫케어 설정을 찾을 수 없습니다.")
    
    # goalActivityMinutes 직접 수정 무시 (Method A)
    if 'goalActivityMinutes' in update_data:
        update_data.pop('goalActivityMinutes')

    # 업데이트 시점 기록
    update_data['updated_at'] = DateTimeUtils.now()
    firestore_data = DateTimeUtils.for_firestore(update_data)
    
    # ✨ 트랜잭션으로 메인 설정 + 이력 동시 저장
    transaction = self.db.transaction()
    
    @firestore.transactional
    def update_with_history(transaction):
        # 1. 메인 설정 업데이트
        transaction.update(doc_ref, firestore_data)
        
        # 2. 최신 전체 설정 조회 (메모리 상)
        latest = doc_ref.get(transaction=transaction).to_dict()
        
        # 파생 필드 재계산
        sessions = latest.get("goalActivitySessions") or 0
        per_session = latest.get("activitySessionMinutes") or 0
        if sessions > 0 and per_session > 0:
            latest["goalActivityMinutes"] = sessions * per_session
        
        # 3. 이력 저장 (오늘부터 유효)
        self._save_settings_history(
            pet_id, 
            latest, 
            effective_date=DateTimeUtils.today_kst_as_date_str(),
            transaction=transaction
        )
        
        return latest
    
    result = update_with_history(transaction)
    logging.info(f"Pet care settings updated with history for {pet_id}")
    return result
```

#### Step 1.5: 특정 날짜의 설정 조회 (신규 메서드)
```python
def get_settings_at_date(self, pet_id: str, date: str) -> Dict[str, Any]:
    """특정 날짜에 유효했던 설정을 조회합니다.
    
    Args:
        pet_id: 펫 ID
        date: 조회할 날짜 (YYYY-MM-DD)
    
    Returns:
        해당 날짜에 유효했던 설정 딕셔너리
    
    Logic:
        1. settings_history에서 effective_date <= date인 모든 이력 조회
        2. 가장 최근(=date에 가장 가까운) 이력 반환
        3. 이력이 없으면 현재 설정 반환 (fallback)
    """
    if self.settings_history_ref is None:
        # DOCS_MODE: 현재 설정 반환
        return self.get_settings(pet_id)
    
    try:
        # 해당 날짜 이전의 모든 설정 이력 조회
        history_ref = self.settings_history_ref.document(pet_id).collection('changes')
        query = (
            history_ref
            .where('effective_date', '<=', date)
            .order_by('effective_date', direction=firestore.Query.DESCENDING)
            .limit(1)  # 가장 최근 이력 1개만
        )
        
        docs = list(query.stream())
        
        if docs:
            # 이력에서 설정 복원
            history_data = docs[0].to_dict()
            
            # 파생 필드 재계산 (혹시 저장 시 누락되었을 경우 대비)
            sessions = history_data.get("goalActivitySessions") or 0
            per_session = history_data.get("activitySessionMinutes") or 0
            if sessions > 0 and per_session > 0:
                history_data["goalActivityMinutes"] = sessions * per_session
            
            return history_data
        else:
            # 이력이 없으면 현재 설정 반환 (Pet 생성 전 날짜 등)
            logging.warning(f"No history found for pet {pet_id} at {date}, using current settings")
            return self.get_settings(pet_id)
    
    except Exception as e:
        logging.error(f"Failed to get settings at date for pet {pet_id}, date {date}: {e}", exc_info=True)
        # 에러 시 현재 설정으로 fallback
        return self.get_settings(pet_id)
```

#### Step 1.6: 기간 내 설정 변경 이력 조회 (신규 메서드)
```python
def get_settings_for_range(
    self, 
    pet_id: str, 
    start_date: str, 
    end_date: str
) -> Dict[str, Dict[str, Any]]:
    """기간 내 설정 변경 이력을 조회합니다.
    
    Args:
        pet_id: 펫 ID
        start_date: 시작 날짜 (YYYY-MM-DD)
        end_date: 종료 날짜 (YYYY-MM-DD)
    
    Returns:
        {
            '2025-10-01': {...settings...},  # 이 날짜부터 유효
            '2025-10-15': {...settings...},  # 이 날짜부터 새 설정
        }
    
    Logic:
        1. start_date 이전의 마지막 설정 조회 (시작점)
        2. start_date ~ end_date 사이의 모든 변경 이력 조회
        3. 날짜별로 매핑하여 반환
    """
    if self.settings_history_ref is None:
        # DOCS_MODE: 현재 설정만 반환
        current = self.get_settings(pet_id)
        return {start_date: current}
    
    try:
        history_ref = self.settings_history_ref.document(pet_id).collection('changes')
        
        # 1. start_date 이전의 마지막 설정 (시작점 기준)
        before_query = (
            history_ref
            .where('effective_date', '<=', start_date)
            .order_by('effective_date', direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        before_docs = list(before_query.stream())
        
        # 2. 기간 내 모든 변경 이력
        range_query = (
            history_ref
            .where('effective_date', '>', start_date)
            .where('effective_date', '<=', end_date)
            .order_by('effective_date')
        )
        range_docs = list(range_query.stream())
        
        # 3. 결과 구성
        result = {}
        
        # 시작점 설정
        if before_docs:
            base_settings = before_docs[0].to_dict()
            result[start_date] = base_settings
        
        # 기간 내 변경사항 추가
        for doc in range_docs:
            settings = doc.to_dict()
            effective_date = settings['effective_date']
            result[effective_date] = settings
        
        # 이력이 아예 없으면 현재 설정 사용
        if not result:
            logging.warning(f"No history found for pet {pet_id} in range {start_date}~{end_date}")
            current = self.get_settings(pet_id)
            result[start_date] = current
        
        return result
    
    except Exception as e:
        logging.error(f"Failed to get settings for range: {e}", exc_info=True)
        # 에러 시 현재 설정으로 fallback
        current = self.get_settings(pet_id)
        return {start_date: current}
```

---

### Phase 2: Integration Service 수정

#### Step 2.1: Daily Summary 수정
```python
def get_daily_summary_with_goals(self, pet_id: str, date: str) -> Dict[str, Any]:
    """특정 날짜 요약 + 목표 진행률 조회 (해당 날짜의 설정 기준)"""
    try:
        # 기록 조회
        records_result = self.query.get_daily(pet_id, date)
        
        # ✨ 변경: 해당 날짜의 설정 조회 (최신 설정이 아님!)
        settings = self.settings.get_settings_at_date(pet_id, date)
        
        # 나머지 로직 동일
        summary = {
            'date': date,
            'records': records_result.get('records', []),
            'record_counts': self._count_by_type(records_result.get('records', [])),
            'meta': records_result.get('summary', {})
        }
        
        if settings:
            goal_progress = self.goal_analyzer.analyze_daily(
                records_result['records'], date, settings
            )
            summary['goal_progress'] = goal_progress
            
        metrics.increment('daily_summary_with_goals_retrieved')
        return summary
        
    except Exception as e:
        logging.error(f"Failed to get daily summary: {e}", exc_info=True)
        raise
```

#### Step 2.2: Range Summary 수정 (복잡)
```python
def get_range_summary_with_trends(
    self, 
    pet_id: str, 
    start_date: str, 
    end_date: str
) -> Dict[str, Any]:
    """기간 요약 + 트렌드 + 목표 추적 조회 (날짜별 설정 기준)"""
    try:
        # 1. 기록 조회
        records_result = self.query.get_range_grouped(pet_id, start_date, end_date)
        
        # ✨ 2. 기간 내 설정 변경 이력 조회
        settings_map = self.settings.get_settings_for_range(pet_id, start_date, end_date)
        # 예: {'2025-10-01': {...}, '2025-10-15': {...}}
        
        # 3. 기본 요약 구성
        summary = {
            'start_date': start_date,
            'end_date': end_date,
            'records_by_date': records_result['records_by_date'],
            'meta': records_result['meta']
        }
        
        # 4. 트렌드 분석 (설정 무관)
        summary['trends'] = self.trend_analyzer.build_trends(records_result['records_by_date'])
        
        # ✨ 5. 목표 분석 (날짜별로 해당 설정 적용)
        if settings_map:
            goal_tracking = self.goal_analyzer.analyze_range_with_history(
                records_result['records_by_date'], 
                settings_map  # 날짜별 설정 맵 전달
            )
            summary['goal_tracking'] = goal_tracking
            
            # 월간 메시지 구성
            days_achieved = goal_tracking.get('days_achieved', {})
            achievement_dates = goal_tracking.get('achievement_dates', {})
            total_hits = sum(days_achieved.values())
            
            summary.setdefault('meta', {})['monthly'] = {
                'encouragement_count': total_hits,
                'message': MonthlyMessageBuilder.build(total_hits),
                'meal': {
                    'achievement_count': days_achieved.get('meal', 0),
                    'achievement_dates': achievement_dates.get('meal', [])
                },
                'activity': {
                    'achievement_count': days_achieved.get('activity', 0),
                    'achievement_dates': achievement_dates.get('activity', [])
                }
            }
            
        metrics.increment('range_summary_with_trends_retrieved')
        return summary
        
    except Exception as e:
        logging.error(f"Failed to get range summary: {e}", exc_info=True)
        raise
```

---

### Phase 3: Analyzer 수정

#### Step 3.1: GoalAnalyzer - Range 분석 수정
```python
class GoalAnalyzer:
    """Compute goal progress for day/range."""
    
    # analyze_daily()는 수정 불필요 (단일 settings 사용)
    
    def analyze_range_with_history(
        self, 
        grouped: Dict[str, List[Dict[str, Any]]], 
        settings_map: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """날짜별로 다른 설정을 적용하여 목표 달성 분석.
        
        Args:
            grouped: {date: [records]}
            settings_map: {date: settings} - 해당 날짜부터 유효한 설정
        
        Returns:
            dict: 달성 통계
                - days_achieved: {goal_type: count}
                - achievement_dates: {goal_type: [date1, date2, ...]}
                - achievement_rates: {goal_type: percentage}
        """
        days = sorted(grouped.keys())
        counts = {'meal': 0, 'activity': 0, 'weight': 0}
        achievement_dates = {'meal': [], 'activity': [], 'weight': []}
        
        # 설정 변경 날짜 정렬
        settings_dates = sorted(settings_map.keys())
        
        for d in days:
            rows = grouped[d]
            
            # ✨ 이 날짜에 유효한 설정 찾기
            # settings_dates에서 d 이하인 가장 큰 날짜의 설정 사용
            applicable_settings = None
            for sd in reversed(settings_dates):
                if sd <= d:
                    applicable_settings = settings_map[sd]
                    break
            
            if not applicable_settings:
                # 설정이 없으면 가장 오래된 설정 사용 (fallback)
                applicable_settings = settings_map[settings_dates[0]]
            
            # 해당 날짜의 설정으로 분석
            daily = self.analyze_daily(rows, d, applicable_settings)
            ach = daily.get('achievements', {})
            
            # 달성 여부 체크
            if ach.get('meal', {}).get('achieved'):
                counts['meal'] += 1
                achievement_dates['meal'].append(d)
            
            if ach.get('activity', {}).get('achieved'):
                counts['activity'] += 1
                achievement_dates['activity'].append(d)
            
            if ach.get('weight', {}).get('at_goal'):
                counts['weight'] += 1
                achievement_dates['weight'].append(d)
        
        total = len(days) or 1
        rates = {k: round(v / total * 100, 1) for k, v in counts.items()}
        
        logger.debug(f"Range analysis with history: days_achieved={counts}")
        
        return {
            'days_achieved': counts,
            'achievement_dates': achievement_dates,
            'achievement_rates': rates
        }
    
    # analyze_range() 기존 메서드는 deprecated 되거나 호환성 유지
    def analyze_range(
        self, 
        grouped: Dict[str, List[Dict[str, Any]]], 
        settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """[DEPRECATED] 단일 설정으로 전체 기간 분석 (하위 호환).
        
        새 코드는 analyze_range_with_history() 사용 권장.
        """
        # 모든 날짜에 동일한 설정 적용
        settings_map = {min(grouped.keys()): settings}
        return self.analyze_range_with_history(grouped, settings_map)
```

---

## ✅ 검증 계획

### 1. Unit Tests

#### Test 1.1: 설정 이력 저장
```python
def test_settings_history_saved_on_update():
    """설정 수정 시 이력이 저장되는지 확인"""
    service.update_settings(pet_id, {'goalMealCount': 4})
    
    # 이력 조회
    history = service.get_settings_for_range(pet_id, '2025-10-01', '2025-10-31')
    
    assert '2025-10-18' in history  # 오늘 날짜
    assert history['2025-10-18']['goalMealCount'] == 4
```

#### Test 1.2: 과거 날짜 설정 조회
```python
def test_get_settings_at_past_date():
    """과거 날짜의 설정을 정확히 조회하는지 확인"""
    # 2025-10-01: goalMealCount = 3
    # 2025-10-15: goalMealCount = 4 로 변경
    
    settings_oct1 = service.get_settings_at_date(pet_id, '2025-10-01')
    settings_oct14 = service.get_settings_at_date(pet_id, '2025-10-14')
    settings_oct15 = service.get_settings_at_date(pet_id, '2025-10-15')
    settings_oct20 = service.get_settings_at_date(pet_id, '2025-10-20')
    
    assert settings_oct1['goalMealCount'] == 3
    assert settings_oct14['goalMealCount'] == 3  # 아직 3회
    assert settings_oct15['goalMealCount'] == 4  # 변경 시작일
    assert settings_oct20['goalMealCount'] == 4  # 이후도 4회
```

#### Test 1.3: Daily Summary 목표 고정
```python
def test_daily_summary_uses_historical_goal():
    """과거 날짜 조회 시 그날의 목표 기준으로 계산되는지 확인"""
    # 2025-10-01: 목표 3회, 실제 3회 달성
    # 2025-10-15: 목표를 4회로 변경
    
    # 10/01 데이터를 10/20에 조회
    summary = integration.get_daily_summary_with_goals(pet_id, '2025-10-01')
    
    goal = summary['goal_progress']['achievements']['meal']['goal']
    achieved = summary['goal_progress']['achievements']['meal']['achieved']
    
    assert goal == 3, "10/01의 목표는 3회여야 함"
    assert achieved == True, "10/01에는 3회 달성했으므로 100%"
```

#### Test 1.4: Range Summary 날짜별 설정 적용
```python
def test_range_summary_applies_correct_settings_per_date():
    """월간 분석에서 날짜별로 올바른 설정이 적용되는지 확인"""
    # 2025-10-01 ~ 10-14: 목표 3회
    # 2025-10-15 ~ 10-31: 목표 4회
    
    summary = integration.get_range_summary_with_trends(
        pet_id, '2025-10-01', '2025-10-31'
    )
    
    meal_dates = summary['goal_tracking']['achievement_dates']['meal']
    
    # 10/01~10/14 중 3회 달성 날짜는 포함
    # 10/15 이후 3회만 달성한 날짜는 제외되어야 함
    assert '2025-10-05' in meal_dates  # 3회 달성 (목표 3회)
    assert '2025-10-20' not in meal_dates  # 3회 달성하지만 목표 4회
```

### 2. Integration Tests

#### Test 2.1: 전체 시나리오
```python
def test_full_scenario_goal_history():
    """실제 사용 시나리오 전체 검증"""
    # 1. Pet 생성 (초기 목표: 3회)
    pet_id = create_pet(...)
    
    # 2. 10/01 ~ 10/14: 3회씩 기록 (매일 달성)
    for day in range(1, 15):
        create_record(pet_id, date=f'2025-10-{day:02d}', meal_count=3)
    
    # 3. 10/15: 목표를 4회로 변경
    update_settings(pet_id, {'goalMealCount': 4})
    
    # 4. 10/15 ~ 10/31: 3회씩 기록 (미달성)
    for day in range(15, 32):
        create_record(pet_id, date=f'2025-10-{day:02d}', meal_count=3)
    
    # 5. 검증: 10/01 조회 → 목표 3회, 달성
    summary_oct1 = get_daily_summary(pet_id, '2025-10-01')
    assert summary_oct1['goal_progress']['achievements']['meal']['goal'] == 3
    assert summary_oct1['goal_progress']['achievements']['meal']['achieved'] == True
    
    # 6. 검증: 10/20 조회 → 목표 4회, 미달성
    summary_oct20 = get_daily_summary(pet_id, '2025-10-20')
    assert summary_oct20['goal_progress']['achievements']['meal']['goal'] == 4
    assert summary_oct20['goal_progress']['achievements']['meal']['achieved'] == False
    
    # 7. 검증: 월간 분석 → 달성 날짜 14일
    range_summary = get_range_summary(pet_id, '2025-10-01', '2025-10-31')
    assert range_summary['goal_tracking']['days_achieved']['meal'] == 14
    # 10/01~10/14만 달성 (14일)
```

---

## 📊 배포 및 마이그레이션

### 1. 배포 순서

#### Step 1: 코드 배포 (하위 호환 유지)
```
1. Settings Service 확장 (history 저장 추가)
2. Integration Service 수정 (새 메서드 사용)
3. Analyzer 수정 (history 기반 분석)
```

**특징**: 
- 기존 코드와 호환 (이력이 없으면 현재 설정으로 fallback)
- 배포 즉시 새 설정 변경부터 이력 저장 시작

#### Step 2: 기존 데이터 마이그레이션 (선택)
**문제**: 과거에 변경된 설정 이력이 없음

**옵션 A: 마이그레이션 생략** (권장)
- 배포 이후 설정 변경분만 이력 저장
- 과거 데이터는 현재 설정으로 조회 (기존과 동일)
- **장점**: 간단, 안전
- **단점**: 과거 데이터 왜곡은 해결 안 됨 (하지만 이미 왜곡된 상태)

**옵션 B: 초기 이력 생성**
- 모든 Pet의 현재 설정을 `effective_date = created_at` 으로 이력 저장
- **장점**: 이후 조회 시 일관성
- **단점**: 실제 변경 이력이 아님

```python
def migrate_initial_settings_history():
    """모든 Pet의 현재 설정을 초기 이력으로 저장"""
    pets = db.collection('pets').stream()
    
    for pet_doc in pets:
        pet_id = pet_doc.id
        pet_data = pet_doc.to_dict()
        
        # 현재 설정 조회
        settings = settings_service.get_settings(pet_id)
        
        # Pet 생성일을 effective_date로 사용
        created_at = pet_data.get('created_at')
        effective_date = created_at.date().strftime('%Y-%m-%d') if created_at else '2025-01-01'
        
        # 초기 이력 저장
        settings_service._save_settings_history(pet_id, settings, effective_date)
        
        logging.info(f"Migrated initial history for pet {pet_id}")
```

### 2. 모니터링

#### 배포 후 확인 사항
```
1. 설정 변경 시 이력 저장 확인
   - Firestore Console: pet_settings_history/{pet_id}/changes 문서 생성 확인

2. API 응답 변화 확인
   - Daily Summary: 과거 날짜 조회 시 목표값 고정 확인
   - Range Summary: 달성 날짜 수 변화 확인

3. 에러 로그 모니터링
   - settings_history 조회 실패 시 fallback 동작 확인
```

---

## 🎯 예상 효과

### Before (현재)
```
시나리오: 10/01 목표 3회 달성 → 10/15 목표 4회로 변경
10/20에 10/01 데이터 조회 시:
- 목표: 4회 ❌ (잘못된 값)
- 달성률: 75% ❌ (3/4)
```

### After (구현 후)
```
시나리오: 동일
10/20에 10/01 데이터 조회 시:
- 목표: 3회 ✅ (당시 설정)
- 달성률: 100% ✅ (3/3)
```

### 월간 리포트 정확도
```
Before:
- 10월 식사 목표 달성: 5일 ❌ (10/15 이후 목표 4회 기준)

After:
- 10월 식사 목표 달성: 14일 ✅ (10/01~10/14는 3회 기준)
```

---

## 📝 To-Do Summary

### Phase 1: Settings Service (우선순위 1)
- [ ] `__init__()`: settings_history_ref 추가
- [ ] `_save_settings_history()`: 이력 저장 private 메서드
- [ ] `create_initial_settings_transactional()`: 최초 생성 시 이력 저장
- [ ] `update_settings()`: 설정 수정 시 이력 저장 (트랜잭션)
- [ ] `get_settings_at_date()`: 특정 날짜 설정 조회
- [ ] `get_settings_for_range()`: 기간 내 설정 맵 조회

### Phase 2: Integration Service (우선순위 2)
- [ ] `get_daily_summary_with_goals()`: get_settings_at_date() 사용
- [ ] `get_range_summary_with_trends()`: get_settings_for_range() 사용

### Phase 3: Analyzer (우선순위 3)
- [ ] `GoalAnalyzer.analyze_range_with_history()`: 날짜별 설정 적용
- [ ] `GoalAnalyzer.analyze_range()`: deprecated 또는 wrapper

### Phase 4: Testing (우선순위 4)
- [ ] Unit tests: 설정 이력 저장/조회
- [ ] Integration tests: 전체 시나리오
- [ ] Manual tests: Firestore Console 확인

### Phase 5: Deployment (우선순위 5)
- [ ] 코드 배포
- [ ] 모니터링
- [ ] (선택) 기존 데이터 마이그레이션

---

## 📚 참고 자료

### 재활용 코드 위치
- DateTimeUtils: `app/utils/datetime_utils.py`
- Firestore Transaction 예제: `app/api/pet_care/settings/services.py:create_initial_settings_transactional()`
- Firestore Range Query 예제: `app/api/pet_care/records/repository.py:list_by_range()`
- Subcollection 패턴: `app/services/notification_service.py`

### 관련 문서
- Pet Care Timezone Fix: `docs/refactoring/PET_CARE_TIMEZONE_FIX_SUMMARY.md`
- Meal Count Increment: `docs/refactoring/MEAL_COUNT_INCREMENT_IMPLEMENTATION.md`

---

**문서 작성일**: 2025-10-18  
**작성자**: GitHub Copilot  
**검토 필요**: Phase 1 구현 전 팀 리뷰
