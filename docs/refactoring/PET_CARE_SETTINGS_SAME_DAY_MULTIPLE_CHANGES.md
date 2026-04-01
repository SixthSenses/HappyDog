# 펫케어 설정 하루 내 여러 번 변경 시나리오 분석 및 수정

**날짜**: 2025-10-18  
**문제**: 하루에 설정 값을 여러 번 변경하는 경우의 동작 분석 및 개선  
**파일**: `pet_project_backend/app/api/pet_care/settings/services.py`

---

## 🔍 문제 상황 분석

### 시나리오: 하루에 여러 번 설정 변경

```
2025-11-15 09:00: 목표 사료 3회로 설정
2025-11-15 12:00: 목표 사료 4회로 변경
2025-11-15 15:00: 목표 사료 5회로 변경
2025-11-15 18:00: 목표 사료 3회로 되돌림
```

### 현재 코드의 문제점

#### 1️⃣ **중복 effective_date 생성**

**현재 코드**:
```python
def update_settings(self, pet_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    effective_date = effective_date_override or DateTimeUtils.today_kst_as_date_str()
    self._save_settings_history(
        pet_id,
        merged_settings,
        effective_date=effective_date,  # ← 항상 오늘 날짜
        transaction=transaction,
    )
```

**문제**:
- 하루에 여러 번 변경 시 모두 `effective_date: "2025-11-15"`로 저장됨
- Firestore subcollection에 같은 날짜의 여러 문서 생성

**결과**:
```
pet_settings_history/{pet_id}/changes/
  ├─ {uuid-1}: effective_date: "2025-11-15", goalMealCount: 3, created_at: 09:00
  ├─ {uuid-2}: effective_date: "2025-11-15", goalMealCount: 4, created_at: 12:00
  ├─ {uuid-3}: effective_date: "2025-11-15", goalMealCount: 5, created_at: 15:00
  └─ {uuid-4}: effective_date: "2025-11-15", goalMealCount: 3, created_at: 18:00
```

#### 2️⃣ **조회 쿼리의 모호성**

**현재 코드**:
```python
def get_settings_at_date(self, pet_id: str, date: str) -> Dict[str, Any]:
    query = (
        history_ref.order_by('effective_date', direction=firestore.Query.DESCENDING)
        .where('effective_date', '<=', date)
        .limit(1)  # ← 가장 최근 것 1개만
    )
```

**문제**:
- `effective_date`만으로 정렬하면 같은 날짜의 여러 문서 중 어느 것이 선택될지 불명확
- Firestore는 같은 정렬 키 내에서 문서 ID 기준으로 정렬하므로 예측 불가능

**예상 결과**:
```
2025-11-15 조회 시:
- 기대: 18:00의 최종 설정 (goalMealCount: 3)
- 실제: 무작위로 09:00, 12:00, 15:00, 18:00 중 하나 반환 ❌
```

#### 3️⃣ **Range 조회의 중복 문제**

**현재 코드**:
```python
def get_settings_for_range(self, pet_id: str, start_date: str, end_date: str):
    for doc in docs:
        effective_date = history.get('effective_date')
        result[effective_date] = history_copy  # ← 같은 키에 덮어씀
```

**문제**:
- 같은 날짜의 여러 변경 중 마지막 것만 남음 (딕셔너리 키 중복)
- 중간 변경 사항이 무시됨

**예상 결과**:
```python
{
  '2025-11-15': {goalMealCount: 3}  # 마지막 것만 남음
}
# 09:00, 12:00, 15:00의 변경은 사라짐
```

---

## 🎯 해결 방안

### 전략 A: 타임스탬프 기반 정렬 (권장 ⭐)

**핵심 아이디어**:
- `effective_date`와 `created_at`를 복합 정렬 키로 사용
- 같은 날짜 내에서는 `created_at` 순서로 정렬하여 최종 변경 결정

**장점**:
- ✅ 시간 순서 보장
- ✅ 최종 설정 명확
- ✅ 중간 변경 이력도 보존

**단점**:
- ⚠️ Firestore 복합 인덱스 필요
- ⚠️ 쿼리 복잡도 증가

### 전략 B: 하루 1회 변경만 허용 (간단함)

**핵심 아이디어**:
- 같은 날짜의 기존 이력을 업데이트 (덮어쓰기)
- 날짜별로 최종 설정만 유지

**장점**:
- ✅ 구현 간단
- ✅ 데이터 중복 없음
- ✅ 쿼리 단순

**단점**:
- ❌ 중간 변경 이력 손실
- ❌ 감사 추적 불가능

### 전략 C: effective_datetime 사용 (정밀도 향상)

**핵심 아이디어**:
- `effective_date` 대신 `effective_datetime` (KST 타임스탬프) 사용
- 분 단위 정확도로 변경 추적

**장점**:
- ✅ 완벽한 시간 순서
- ✅ 중간 변경 완전 보존
- ✅ 감사 추적 가능

**단점**:
- ⚠️ 쿼리 로직 복잡
- ⚠️ 날짜 비교 로직 수정 필요

---

## ✅ 권장 솔루션: 전략 A (타임스탬프 복합 정렬)

### 설계 원칙

1. **이력 저장**: `effective_date`와 `created_at` 모두 저장
2. **복합 정렬**: 날짜 내에서 시간 순서로 정렬
3. **최종 선택**: 가장 최근 타임스탬프의 설정 사용

### Firestore 인덱스

```
Collection: pet_settings_history/{pet_id}/changes
Composite Index:
- effective_date (ASC)
- created_at (DESC)  ← 같은 날짜 내에서 최신순
```

### 코드 수정 계획

#### 1. `_save_settings_history()` - 변경 없음 ✅
현재 코드가 이미 `effective_date`와 `created_at` 모두 저장하고 있음

```python
history_payload = {
    'effective_date': effective_date,  # 날짜
    'created_at': settings_data.get('updated_at') or DateTimeUtils.now(),  # 타임스탬프
    # ...
}
```

#### 2. `get_settings_at_date()` - 복합 정렬 추가 🔧

**Before**:
```python
query = (
    history_ref.order_by('effective_date', direction=firestore.Query.DESCENDING)
    .where('effective_date', '<=', date)
    .limit(1)
)
```

**After**:
```python
query = (
    history_ref
    .where('effective_date', '<=', date)
    .order_by('effective_date', direction=firestore.Query.DESCENDING)
    .order_by('created_at', direction=firestore.Query.DESCENDING)  # ← 추가
    .limit(1)
)
```

**동작**:
1. `effective_date <= date` 조건으로 필터링
2. `effective_date` 내림차순 정렬 → 가장 최근 날짜
3. `created_at` 내림차순 정렬 → 같은 날짜 내에서 가장 최근 시간
4. 첫 번째 문서 = 최종 설정 ✅

#### 3. `get_settings_for_range()` - 중복 제거 로직 🔧

**Before**:
```python
for doc in docs:
    effective_date = history.get('effective_date')
    result[effective_date] = history_copy  # ❌ 덮어씀
```

**After**:
```python
# 날짜별로 가장 최근 설정만 유지
for doc in docs:
    effective_date = history.get('effective_date')
    created_at = history.get('created_at')
    
    if effective_date not in result:
        result[effective_date] = history_copy
    else:
        # 같은 날짜면 더 최근 것으로 교체
        existing_created_at = result[effective_date].get('created_at')
        if created_at > existing_created_at:
            result[effective_date] = history_copy
```

**개선된 동작**:
- 같은 날짜의 여러 변경 중 `created_at`이 가장 최근인 것만 유지
- 중복 키 문제 해결

#### 4. 쿼리 최적화 - 서버 측 필터링 🔧

**더 나은 방법**: Firestore 쿼리에서 복합 정렬 활용

```python
def get_settings_for_range(self, pet_id: str, start_date: str, end_date: str):
    try:
        # 복합 인덱스로 정렬된 결과 가져오기
        docs = list(
            history_ref
            .where('effective_date', '<=', end_date)
            .order_by('effective_date', direction=firestore.Query.ASCENDING)
            .order_by('created_at', direction=firestore.Query.DESCENDING)
            .stream()
        )
    except Exception as exc:
        logging.error(f"Failed to fetch settings history range: {exc}", exc_info=True)
        # Fallback: 인덱스 없을 경우 기존 쿼리
        docs = list(
            history_ref
            .where('effective_date', '<=', end_date)
            .order_by('effective_date')
            .stream()
        )
    
    # 날짜별로 그룹화하여 가장 최근 것만 선택
    result: Dict[str, Dict[str, Any]] = {}
    for doc in docs:
        history = DateTimeUtils.from_firestore(doc.to_dict())
        effective_date = history.get('effective_date')
        
        # 이미 해당 날짜가 있으면 건너뛰기 (이미 최신순 정렬되어 있음)
        if effective_date in result:
            continue
        
        self._ensure_derived_fields(history)
        result[effective_date] = {**history}
```

---

## 🔨 구현 단계

### Phase 1: Firestore 인덱스 생성 (우선)

**Firebase Console 작업**:
1. Firestore Database → Indexes 탭
2. Composite Index 생성:
   - Collection group: `changes`
   - Fields:
     - `effective_date` (Ascending)
     - `created_at` (Descending)
   - Query scope: Collection

**또는 CLI**:
```bash
# firestore.indexes.json 생성
{
  "indexes": [
    {
      "collectionGroup": "changes",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "effective_date", "order": "ASCENDING"},
        {"fieldPath": "created_at", "order": "DESCENDING"}
      ]
    }
  ]
}

# 배포
firebase deploy --only firestore:indexes
```

### Phase 2: 코드 수정

#### 수정 1: `get_settings_at_date()` - 복합 정렬

#### 수정 2: `get_settings_for_range()` - 중복 제거

#### 수정 3: 에러 처리 - 인덱스 없을 경우 Fallback

### Phase 3: 테스트

#### 단위 테스트
```python
def test_same_day_multiple_changes():
    """하루에 여러 번 변경 시 최종 설정 조회"""
    service = PetCareSettingService(breed_service, db_client)
    
    # 1. 09:00 - 목표 3회
    service.update_settings('pet123', {'goalMealCount': 3})
    
    # 2. 12:00 - 목표 4회
    service.update_settings('pet123', {'goalMealCount': 4})
    
    # 3. 15:00 - 목표 5회
    service.update_settings('pet123', {'goalMealCount': 5})
    
    # 검증: 가장 최근 설정 (5회) 조회
    settings = service.get_settings_at_date('pet123', '2025-11-15')
    assert settings['goalMealCount'] == 5

def test_range_with_same_day_changes():
    """기간 조회 시 날짜별 최종 설정 사용"""
    service = PetCareSettingService(breed_service, db_client)
    
    # 11-15에 여러 번 변경
    # 09:00 - 3회, 12:00 - 4회, 15:00 - 5회
    
    settings_map = service.get_settings_for_range('pet123', '2025-11-01', '2025-11-30')
    
    # 검증: 11-15의 최종 설정 (5회)만 포함
    assert settings_map['2025-11-15']['goalMealCount'] == 5
    # 중복 없음
    assert list(settings_map.keys()).count('2025-11-15') == 1
```

---

## 📊 예상 효과

### Before (현재)

**하루 여러 번 변경 시**:
```
2025-11-15 조회:
- 결과: 무작위로 3회, 4회, 5회 중 하나 ❌
- 원인: 같은 effective_date의 여러 문서 중 선택 기준 불명확
```

**월간 리포트**:
```
11월 조회 시:
- '2025-11-15'에 대해 마지막 문서만 사용
- 중간 변경 무시됨
```

### After (수정 후)

**하루 여러 번 변경 시**:
```
2025-11-15 조회:
- 결과: 5회 ✅ (최종 설정)
- 원인: created_at 복합 정렬로 가장 최근 것 선택
```

**월간 리포트**:
```
11월 조회 시:
- '2025-11-15': goalMealCount: 5 ✅
- 날짜별 최종 설정 명확
```

---

## 🎯 대안 전략 B 구현 (간소화)

### 전략: 같은 날짜 덮어쓰기

**아이디어**: 
- 하루에 1개의 설정 이력만 유지
- 같은 날짜의 기존 문서를 업데이트

**수정 코드**:
```python
def _save_settings_history(
    self,
    pet_id: str,
    settings_data: Dict[str, Any],
    *,
    effective_date: Optional[str] = None,
    transaction: Optional[Transaction] = None,
) -> None:
    if self.settings_history_ref is None:
        logging.debug("Settings history skipped")
        return

    if effective_date is None:
        effective_date = DateTimeUtils.today_kst_as_date_str()

    history_collection = self.settings_history_ref.document(pet_id).collection('changes')
    
    # 같은 날짜의 기존 문서 찾기
    existing_docs = list(
        history_collection
        .where('effective_date', '==', effective_date)
        .limit(1)
        .stream()
    )
    
    history_payload = {
        **{k: v for k, v in settings_data.items() if k != 'change_id'},
        'change_id': settings_data.get('change_id') or str(uuid.uuid4()),
        'pet_id': pet_id,
        'effective_date': effective_date,
        'created_at': settings_data.get('updated_at') or DateTimeUtils.now(),
    }
    
    firestore_payload = DateTimeUtils.for_firestore(history_payload)
    
    if transaction is not None:
        if existing_docs:
            # 기존 문서 업데이트 (덮어쓰기)
            transaction.update(existing_docs[0].reference, firestore_payload)
        else:
            # 새 문서 생성
            history_doc = history_collection.document()
            transaction.set(history_doc, firestore_payload)
    else:
        if existing_docs:
            existing_docs[0].reference.update(firestore_payload)
        else:
            history_collection.add(firestore_payload)
```

**장점**:
- ✅ 날짜당 1개 문서 보장
- ✅ 인덱스 불필요
- ✅ 쿼리 단순

**단점**:
- ❌ 중간 변경 이력 손실
- ❌ 감사 추적 불가

---

## 💡 최종 권장사항

### 선택 기준

| 요구사항 | 전략 A (복합 정렬) | 전략 B (덮어쓰기) |
|---------|------------------|----------------|
| 변경 이력 완전 보존 | ✅ 모든 변경 보존 | ❌ 최종만 보존 |
| 감사 추적 | ✅ 가능 | ❌ 불가능 |
| 쿼리 성능 | ⚠️ 인덱스 필요 | ✅ 빠름 |
| 구현 복잡도 | ⚠️ 중간 | ✅ 낮음 |
| 저장 공간 | ⚠️ 많음 | ✅ 적음 |

### 권장: **전략 A (복합 정렬)** ⭐

**이유**:
1. **완전한 감사 추적**: 모든 변경을 시간순으로 추적
2. **데이터 무결성**: 중간 변경도 보존하여 나중에 분석 가능
3. **확장성**: 향후 "변경 이력 보기" 기능 추가 가능
4. **성능**: Firestore 인덱스로 빠른 조회

**다만**:
- 하루에 10회 이상 변경하는 극단적 케이스는 드물 것으로 예상
- 감사 요구사항이 없다면 전략 B도 충분

---

## 📝 체크리스트

### Phase 1: 인덱스
- [ ] Firestore 복합 인덱스 생성
- [ ] 인덱스 활성화 확인 (5-10분 소요)

### Phase 2: 코드 수정
- [ ] `get_settings_at_date()`: 복합 정렬 추가
- [ ] `get_settings_for_range()`: 중복 제거 로직
- [ ] 에러 처리: 인덱스 없을 경우 Fallback

### Phase 3: 테스트
- [ ] 단위 테스트: 하루 여러 번 변경
- [ ] 통합 테스트: 월간 리포트
- [ ] 로그 확인: 복합 쿼리 동작

### Phase 4: 문서화
- [ ] 인덱스 요구사항 문서화
- [ ] API 동작 명세 업데이트

---

**마지막 업데이트**: 2025-10-18  
**상태**: 🔧 수정 준비 완료
