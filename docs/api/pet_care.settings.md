# pet_care/settings API

펫 케어 설정(pet_care/settings) 도메인 API 요약입니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| GET | /api/pet-care/{pet_id}/settings | jwt_required | 지정 펫의 케어 설정 조회 | 200, 401, 404, 500 |
| PUT | /api/pet-care/{pet_id}/settings | jwt_required | 지정 펫의 케어 설정 갱신 | 200, 400, 401, 404, 500 |

## 스키마/데이터 타입

| 필드 | 타입 | 제약/범위 | 비고 |
|---|---|---|---|
| goalWeight | float | 0.1..200.0 |  |
| goalActivityMinutes | int | 0..1440 |  |
| activityIncrementMinutes | int | 1..180 |  |
| goalMealCount | int | 1..10 |  |
| mealIncrementCount | int | 1..5 |  |
| updated_at | ISO8601 | dump_only |  |
| pet_id | string | dump_only |  |

## 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| GET | 404 SETTINGS_NOT_FOUND | 미존재 |
|  | 500 FETCH_FAILED | 서버 오류 |
| PUT | 400 VALIDATION_ERROR/NO_DATA | 검증 실패/본문 없음 |
|  | 404 SETTINGS_NOT_FOUND | 미존재 |
|  | 500 UPDATE_FAILED | 서버 오류 |

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 400 | NO_DATA | 변경할 데이터가 없습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 404 | SETTINGS_NOT_FOUND | 설정을 찾을 수 없습니다. |
| 500 | FETCH_FAILED/UPDATE_FAILED | 서버 내부 오류가 발생했습니다. |

## 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 컬렉션 | pet_settings (doc ID=pet_id; pets와 1:1) |
| 초기 생성 | create_initial_settings_transactional (품종/성별 기반 목표치 산정) |
| 타임스탬프 | DateTimeUtils.now → for_firestore 저장 |
| 조회/수정 | 존재 확인 + updated_at 갱신 |
