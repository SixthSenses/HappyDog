# pets API

실제 코드(app/api/pets/routes.py & schemas.py) 기반 재작성. weight 관련 필드는 전부 제거됨. gender 는 입력이 소문자여도 Enum 대문자로 정규화.

## 엔드포인트

| Method | Path | Auth | 설명 | 성공 | 주요 오류 |
|---|---|---|---|---|---|
| POST | /api/pets/ | JWT | 반려동물 최초 등록 (1인 1펫 정책) | 201 | 400 VALIDATION_ERROR, 409 IDEMPOTENCY_CONFLICT(PET_LIMIT), 500 RECORD_CREATION_FAILED |
| GET | /api/pets/{pet_id} | JWT | 소유자 전용 전체 프로필 | 200 | 403 FORBIDDEN, 404 (내부 서비스 가능성), 500 FETCH_FAILED |
| PATCH | /api/pets/{pet_id} | JWT | 부분 수정 | 200 | 400 VALIDATION_ERROR, 403 FORBIDDEN, 500 UPDATE_FAILED |
| POST | /api/pets/{pet_id}/nose-print | JWT | 비문 등록/인증 | 200 | 400 VALIDATION_ERROR, 403 FORBIDDEN, 500 BIO_PROCESSING_FAILED |
| POST | /api/pets/{pet_id}/eye-analysis | JWT | 안구 이미지 분석 | 200 | 400 VALIDATION_ERROR, 403 FORBIDDEN, 500 BIO_PROCESSING_FAILED |
| GET | /api/pets/profile?view={view}&user_id={uid} | 선택 | 뷰 기반 필터링 프로필 (mypage/petcare/social) | 200 | 400 VALIDATION_ERROR(view), 403 FORBIDDEN, 404 NOT_FOUND, 500 FETCH_FAILED |

view 파라미터: mypage(소유자 기본), petcare(케어 화면 최소필드), social(멍스타그램용: age_months, post_count 포함). user_id 생략 시 자기 자신.

## 스키마 (현재 코드)

| 스키마 | 필드 | 타입/제약 | 비고 |
|---|---|---|---|
| PetRegistrationSchema | name | string(1..20) | 필수 |
|  | gender | enum(MALE/FEMALE/UNKNOWN 등) | 입력 소문자 허용 |
|  | breed | string(1..30) & 존재검증 | 필수 |
|  | birthdate | YYYY-MM-DD | 필수 |
|  | fur_color | string|null | 선택 |
|  | health_concerns | string[] | 선택 |
|  | profile_image_url | string|null | 선택 |
| PetUpdateSchema | name | string(1..20) | 부분 |
|  | fur_color | string | 부분 |
|  | health_concerns | string[] | 부분 |
|  | profile_image_url | string|null | 부분 |
| BiometricAnalysisRequestSchema | file_path | string | GCS 경로 (legacy: nose_image_url / eye_image_url 호환) |
| PetProfileResponseSchema | pet_id | string |  |
|  | user_id | string |  |
|  | name / gender / breed / birthdate |  | weight 제거 |
|  | fur_color | string|null |  |
|  | health_concerns | string[] |  |
|  | is_verified | bool | 비문 인증 여부 |
|  | profile_image_url | string|null |  |
|  | nose_print_url | URL|null |  |
|  | faiss_id | int|null | 검색 시스템 ID |
| PetViewBasedResponseSchema | pet_id / name / is_verified |  | 공통 |
|  | profile_image_url | string|null | 공통 |
|  | birthdate / gender / breed | 선택 (view에 따라) | social/mypage |
|  | age_months | int|null | social 전용 |
|  | post_count | int|null | social 전용 |

## 비문 / 안구 분석 흐름
1) 업로드 선행(file_path 확보)
	* 비문 원본: upload_type=pet_nose_print (alias: nose 관련 과거 직접 URL 필드 제거 방향)
	* 안구 분석: upload_type=eye_analysis
	* 프로필 이미지: upload_type=pet_profile (PATCH 시 profile_image_url 로 반영)
2) POST /nose-print → biometric_service.register_nose_print_for_pet → 실패 시 error_code (예: BIO_PROCESSING_FAILED)
3) POST /eye-analysis → biometric_service.analyze_eye_image_for_pet → disease_name, probability 반환
legacy 호환: file_path 누락 시 nose_image_url 또는 eye_image_url 필드를 file_path 로 매핑 (점진 제거 예정).

### 업로드 타입 연계 (pets ↔ uploads)
| 목적 | 사용해야 할 upload_type | 비고 |
|------|-------------------------|------|
| Pet 프로필 이미지 | pet_profile | 이전 profile_image 는 alias 변환 (유예) |
| 비문 분석 | pet_nose_print | 분석 성공 시 promote & is_verified=true |
| 안구 분석 | eye_analysis | 결과 JSON 반환 (질병명 / 확률) |

추가적으로 posts 이미지나 만화 변환은 각각 post_image / cartoon_source_image 를 사용 (pets 도메인 직접 필드 아님).

## 오류 코드 요약
| 시나리오 | error_code |
|---|---|
| 스키마 검증 실패 | VALIDATION_ERROR |
| 1인 1펫 정책 위반 | IDEMPOTENCY_CONFLICT (문구: 이미 등록됨) |
| 권한 없음 (타 사용자 접근) | FORBIDDEN |
| 프로필 조회/목록 내부 오류 | FETCH_FAILED |
| 업데이트 내부 오류 | UPDATE_FAILED |
| 바이오메트릭 실패(일반) | BIO_PROCESSING_FAILED |
| 서비스 미가용(바이오) | SERVICE_UNAVAILABLE |

## 기타
* weight 관련 모든 필드 제거됨 (docs 정합성 확보 완료)
* gender 입력은 소문자여도 Enum 대문자로 변환
* /profile 엔드포인트는 Presenter + Policy 조합으로 최소/확장 필드 결정
* 업로드 타입 표준화(Option A) 적용: pets 관련 클라이언트는 반드시 위 표의 canonical upload_type 사용 권장
* Deprecated alias (profile_image, cartoon_source) 는 uploads 라우트에서 자동 변환되지만 추후 제거 예정 (클라이언트는 즉시 canonical 타입 사용 권장)

