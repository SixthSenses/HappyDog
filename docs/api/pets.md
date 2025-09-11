# pets API

반려동물(pets) 도메인 API 요약입니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/pets/ | jwt_required | 최초 반려동물 등록 | 201, 400, 401, 409, 500 |
| GET | /api/pets/{pet_id} | jwt_required | 소유자 전용 Full Profile 조회 | 200, 401, 403, 500 |
| PATCH | /api/pets/{pet_id} | jwt_required | 펫 프로필 부분 수정 | 200, 400, 401, 403, 500 |
| GET | /api/pets/public-profile/{pet_id} | optional | 공개 프로필 조회 | 200, 404, 500 |
| POST | /api/pets/{pet_id}/nose-print | jwt_required | 비문 등록/인증 | 200, 400, 403, 500 |
| POST | /api/pets/{pet_id}/eye-analysis | jwt_required | 안구 이미지 분석 | 200, 400, 403, 500 |

## 스키마/데이터 타입

| 스키마 | 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|---|
| PetRegistrationSchema | name | string(1..20) | ✔ |  |
|  | gender | string(enum) | ✔ | PetGender |
|  | breed | string | ✔ | 존재 검사 |
|  | birthdate | string(YYYY-MM-DD) | ✔ |  |
|  | current_weight | float(0.1..200.0) | ✔ |  |
|  | fur_color | string |  | optional |
|  | health_concerns | array<string> |  | optional |
| PetUpdateSchema | name | string |  | optional |
|  | fur_color | string |  | optional |
|  | health_concerns | array<string> |  | optional |
| BiometricAnalysisRequestSchema | file_path | string | ✔ | GCS 경로 |
| PetProfileResponseSchema | pet_id | UUID | ✔ |  |
|  | user_id | UUID | ✔ |  |
|  | name/gender/breed | string | ✔ |  |
|  | birthdate | string(YYYY-MM-DD) | ✔ |  |
|  | initial_weight | float | ✔ |  |
|  | fur_color | string |  | optional |
|  | health_concerns | array<string> |  |  |
|  | is_verified | boolean | ✔ |  |
|  | nose_print_url | URL |  | optional |
|  | faiss_id | int |  | optional |
| PetPublicProfileResponseSchema | pet_id | UUID | ✔ |  |
|  | name/gender/breed | string | ✔ |  |
|  | birthdate | string(YYYY-MM-DD) | ✔ |  |
|  | initial_weight | float | ✔ |  |
|  | fur_color | string |  | optional |
|  | is_verified | boolean | ✔ |  |
| EyeAnalysisResponseSchema | analysis_id | UUID|null | ✔ |  |
|  | disease_name | string | ✔ |  |
|  | probability | float | ✔ |  |

## 오류/예외 (요약)

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| POST /api/pets/ | 400 VALIDATION_ERROR | 스키마 실패 |
|  | 409 PET_LIMIT_REACHED | 1명=1펫 정책 위반 |
|  | 500 PET_REGISTRATION_FAILED | 등록 실패 |
| GET /api/pets/{pet_id} | 403 FORBIDDEN_OR_NOT_FOUND | 소유권 없음/미존재 |
|  | 500 FETCH_FAILED | 서버 오류 |
| PATCH /api/pets/{pet_id} | 400 VALIDATION_ERROR | 검증 실패 |
|  | 403 UPDATE_FAILED_FORBIDDEN | 권한 없음 |
|  | 500 INTERNAL_SERVER_ERROR | 서버 오류 |
| GET /api/pets/public-profile/{pet_id} | 404 PET_NOT_FOUND | 미존재 |
|  | 500 FETCH_FAILED | 서버 오류 |
| /nose-print, /eye-analysis | 400/403/409/500 | 각 시나리오 참고 |

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 403 | FORBIDDEN_OR_NOT_FOUND/UPDATE_FAILED_FORBIDDEN | 접근 권한이 없거나 리소스를 변경할 수 없습니다. |
| 404 | PET_NOT_FOUND | 반려동물을 찾을 수 없습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 409 | PET_LIMIT_REACHED | 이미 반려동물이 등록되어 있습니다. |
| 500 | FETCH_FAILED/PET_REGISTRATION_FAILED/INTERNAL_SERVER_ERROR | 서버 내부 오류가 발생했습니다. |

## 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 등록 | 트랜잭션: pets 생성(asdict→for_firestore) + pet_settings 초기화 |
| Nose | 권한 확인 → pipeline 처리 → SUCCESS 시 pets 업데이트 + 인덱스 반영 |
| Eye | 스토리지 다운로드 → 예측 → public url 시도 → analysis_history 저장 |
