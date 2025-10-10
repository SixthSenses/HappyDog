# 펫케어 기록 타임존 문제 해결 - 요약

## 🎯 핵심 변경사항

**문제:** 프론트엔드에서 10월 10일 00:48 (KST)에 기록 생성 → Firestore에 searchDate "2025-10-09" 저장 (하루 전)

**원인:** 백엔드가 UTC 기준으로 날짜를 추출했기 때문

**해결:** KST 기준으로 searchDate 생성

## 📝 수정된 파일

### 1. `app/utils/datetime_utils.py`
```python
# 추가된 상수
KST = timezone(timedelta(hours=9), name='KST')

# 추가된 함수
def today_kst() -> date
def today_kst_as_date_str() -> str
def to_kst_date(dt: datetime) -> date
def to_kst_date_str(dt: datetime) -> str
```

### 2. `app/api/pet_care/records/repository.py`
```python
# 변경 전
search_date = DateTimeUtils.to_date_str(ts_dt)

# 변경 후
search_date = DateTimeUtils.to_kst_date_str(ts_dt)  # KST 기준
```

## 🚀 배포 가이드

### 1. 코드 배포
```bash
# Git pull 또는 새 버전 배포
git pull origin feature/pet-care-timezone-fix

# 서버 재시작
# (환경에 따라 다름)
```

### 2. 기존 데이터 마이그레이션 (선택사항)

**언제 필요한가?**
- 2025-10-01 이후 많은 데이터가 있는 경우
- 정확한 날짜별 통계가 중요한 경우

**실행 방법:**
```bash
# Dry-run으로 먼저 확인
python pet_project_backend/scripts/migrate_pet_care_searchdate.py --dry-run

# 실제 마이그레이션 실행
python pet_project_backend/scripts/migrate_pet_care_searchdate.py
```

### 3. 검증
```bash
# 새 기록 생성 후 확인
# Firestore에서 최신 기록 확인:
# - timestamp와 searchDate의 날짜가 일치하는지 확인
```

## ✅ 테스트

```bash
# 유닛 테스트 실행
pytest pet_project_backend/tests/test_pet_care_timezone.py -v
```

## 📊 영향 범위

### ✅ 영향받는 기능
- 펫케어 기록 생성 (POST `/api/pet_care/<pet_id>/records`)
- 일별 기록 조회 (GET `/api/pet_care/<pet_id>/records/daily?date=YYYY-MM-DD`)

### ✅ 영향 없는 기능
- 펫케어 기록 수정 (timestamp 변경 불가)
- 펫케어 기록 삭제
- 기타 모든 API

### ✅ 쿼리 성능
- 변경 없음 (동일한 Firestore 복합 인덱스 사용)

## 🔍 주의사항

1. **타임존 정책**
   - Firestore `timestamp`: UTC 저장 (변경 없음)
   - `searchDate`: KST 기준 문자열 (변경됨)

2. **프론트엔드 호환성**
   - API 스키마 변경 없음
   - 기존 클라이언트 코드 수정 불필요

3. **향후 확장성**
   - 다른 국가 서비스 시 타임존 정책 재검토 필요
   - 현재는 한국 시장 전용 (KST 하드코딩)

## 📚 상세 문서

- **전체 분석:** `docs/refactoring/PET_CARE_TIMEZONE_FIX.md`
- **테스트 코드:** `tests/test_pet_care_timezone.py`
- **마이그레이션 스크립트:** `scripts/migrate_pet_care_searchdate.py`

## 💬 문의

타임존 관련 추가 문의사항은 백엔드 팀에 문의해주세요.

---
**최종 업데이트:** 2025-10-10
