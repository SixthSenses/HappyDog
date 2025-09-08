# API Reference — Table Summary

## 공통 규약

| 항목 | 내용 |
|---|---|
| 시간/타임존 | UTC 고정. Firestore Timestamp는 DateTimeUtils.for_firestore로 저장. |
| 에러 포맷 | { error_code, message?, details? } (전역 ValidationError 핸들러 존재) |
| 인증 | flask_jwt_extended 기반. 대부분 엔드포인트에 @jwt_required 적용(명시된 optional 제외). |

### 자료형 표기 규칙

| 표기 | 의미 |
|---|---|
| string | 문자열 (UUID/URL/ISO8601는 별도 표기) |
| int / float | 숫자형 |
| boolean | 불리언 |
| ISO8601 | UTC 날짜/시간 문자열("YYYY-MM-DD" 또는 "YYYY-MM-DDTHH:mm:ssZ") |
| timestamp(ms) | Unix epoch milliseconds (int) |
| UUID | 문자열 UUID |
| URL | 문자열 URL |
| object | JSON 오브젝트 |
| array<T> | T 타입 요소로 구성된 배열 |

---

## 1) auth

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/auth/social | - | 소셜 로그인/회원가입 처리 (Google 코드 교환 → 토큰 발급) | 200, 401, 500 |
| POST | /api/auth/token/refresh | Refresh JWT | Refresh 토큰으로 Access 토큰 재발급 | 200 |
| POST | /api/auth/logout | Access/Refresh JWT | 전달된 access/refresh JWT 블랙리스트 처리(서버 로그아웃) | 200, 400, 422, 500 |

### 요청 스키마

| 스키마 | 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|---|
| SocialLoginSchema | provider | string | ✔ | 'google' 등 |
|  | auth_code | string | ✔ | OAuth 인증 코드 |
| LogoutRequestSchema | access_token | string(JWT) | ✔ |  |
|  | refresh_token | string(JWT) | ✔ |  |

### 응답/데이터 타입 요약

| 엔드포인트 | 2xx 응답 | 타입 | 비고 |
|---|---|---|---|
| POST /social | { access_token, refresh_token, user_id, is_new_user, user_info{ user_id,email,nickname,profile_image_url } } | object | user_id: UUID, profile_image_url: URL|null |
| POST /token/refresh | { access_token } | object |  |
| POST /logout | { message } | object |  |

### 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| /social | 401 INVALID_AUTH_CODE | 코드 교환 실패 |
|  | 500 INTERNAL_SERVER_ERROR | 서버 오류 |
| /token/refresh | - | 데코레이터에서 Refresh 검증 처리 |
| /logout | 400 VALIDATION_ERROR | 스키마 검증 실패 |
|  | 422 INVALID_TOKEN | 디코드 실패 |
|  | 500 LOGOUT_FAILED | 서버 오류 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | INVALID_AUTH_CODE | 유효하지 않은 인증 코드입니다. |
| 400 | VALIDATION_ERROR | 요청 형식이 올바르지 않습니다. |
| 422 | INVALID_TOKEN | 유효하지 않은 토큰입니다. |
| 500 | INTERNAL_SERVER_ERROR/LOGOUT_FAILED | 서버 내부 오류가 발생했습니다. |

### 저장/검증 로직

| 단계 | 내용 |
|---|---|
| 1 | GoogleAuthService로 userinfo 조회 → users upsert |
| 2 | 신규: user_id(UUID), google_id(sub), email, nickname, join_date(UTC) 저장 |
| 3 | 로그아웃: JWT 디코드 → jti/exp 추출 → revoked_tokens {revoked_at, expires_at} 저장 |

---

## 2) breeds

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| GET | /api/breeds/ | optional | 품종 목록/요약 목록 조회 (limit/offset/summary) | 200, 400, 500 |
| GET | /api/breeds/{breed_name} | optional | 특정 품종 단건 조회 | 200, 404, 500 |
| GET | /api/breeds/search | optional | 부분 문자열 검색(클라 필터) | 200, 400, 500 |
| GET | /api/breeds/exists/{breed_name} | optional | 해당 품종 존재 여부 확인 | 200, 500 |
| GET | /api/breeds/statistics | optional | 품종 통계 조회(합/평균/최소/최대) | 200, 500 |

### 스키마/데이터 형식

| 스키마 | 필드 | 타입 | 비고 |
|---|---|---|---|
| Breed | breed_name | string |  |
|  | life_expectancy | float(0~30) |  |
|  | height_cm | object{male: float, female: float} |  |
|  | weight_kg | object{male: float, female: float} |  |
|  | created_at/updated_at | ISO8601 | optional |
| BreedList | breeds | array<Breed> |  |
|  | total_count | int |  |
| SummaryList | breed_name | string |  |
|  | life_expectancy | float |  |

### 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| GET / | 400 INVALID_PARAMETER | 잘못된 쿼리 |
|  | 500 BREED_FETCH_FAILED | 서버 오류 |
| GET /{name} | 404 BREED_NOT_FOUND | 미존재 |
|  | 500 BREED_FETCH_FAILED | 서버 오류 |
| GET /search | 400 MISSING_PARAMETER/INVALID_PARAMETER | 파라미터 오류 |
|  | 500 BREED_SEARCH_FAILED | 서버 오류 |
| GET /exists/{name} | 500 BREED_CHECK_FAILED | 서버 오류 |
| GET /statistics | 500 STATS_FETCH_FAILED | 서버 오류 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 400 | INVALID_PARAMETER | 유효하지 않은 파라미터입니다. |
| 400 | MISSING_PARAMETER | 필수 파라미터가 누락되었습니다. |
| 404 | BREED_NOT_FOUND | 요청한 품종을 찾을 수 없습니다. |
| 500 | BREED_FETCH_FAILED/BREED_SEARCH_FAILED/BREED_CHECK_FAILED/STATS_FETCH_FAILED | 품종 정보를 조회하는 중 오류가 발생했습니다. |

### 저장/조회 로직

| 항목 | 내용 |
|---|---|
| 컬렉션 | breeds (doc ID=breed_name) |
| 목록 | order_by('breed_name'), offset은 start_after |
| 검색 | 전체 로드 후 파이썬 부분 문자열 필터(대소문자 무시) |
| 통계 | life_expectancy 집계로 평균/최소/최대 |

---

## 3) cartoon_jobs

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/cartoon-jobs/ | jwt_required | 그림체 변환 작업 생성(비동기) | 202, 400, 401, 500 |
| GET | /api/cartoon-jobs/{job_id} | jwt_required | 내 작업 상태/결과 조회 | 200, 401, 404, 500 |
| DELETE | /api/cartoon-jobs/{job_id} | jwt_required | 진행 중 작업 취소(cancelling 전이) | 200, 401, 403, 404, 409, 500 |

### 요청/응답 스키마

| 스키마 | 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|---|
| CartoonJobCreateSchema | file_paths | array<URL>[min 1] | ✔ |  |
|  | user_text | string(≤500) |  | optional |
| CartoonJobResponseSchema | job_id | UUID | ✔ |  |
|  | user_id | UUID | ✔ |  |
|  | status | string(enum) | ✔ |  |
|  | original_image_url | URL | ✔ |  |
|  | user_text | string |  | optional |
|  | result_image_url | URL |  | optional |
|  | error_message | string |  | optional |
|  | created_at/updated_at | ISO8601 | ✔ |  |

### 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| POST / | 400 VALIDATION_ERROR | 스키마 검증 실패 |
|  | 500 JOB_CREATION_FAILED | 서버 오류 |
| GET /{id} | 404 JOB_NOT_FOUND_OR_FORBIDDEN | 미존재/권한 없음 |
|  | 500 INTERNAL_SERVER_ERROR | 서버 오류 |
| DELETE /{id} | 403 FORBIDDEN | 권한 없음 |
|  | 409 INVALID_STATE_FOR_CANCEL | 상태 부적합 |
|  | 404 JOB_NOT_FOUND | 미존재 |
|  | 500 JOB_CANCEL_FAILED | 서버 오류 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 403 | FORBIDDEN | 이 작업을 수행할 권한이 없습니다. |
| 404 | JOB_NOT_FOUND/JOB_NOT_FOUND_OR_FORBIDDEN | 작업을 찾을 수 없거나 권한이 없습니다. |
| 409 | INVALID_STATE_FOR_CANCEL | 현재 상태에서는 취소할 수 없습니다. |
| 500 | INTERNAL_SERVER_ERROR/JOB_CREATION_FAILED/JOB_CANCEL_FAILED | 서버 내부 오류가 발생했습니다. |

### 저장/비즈니스 로직

| 단계 | 내용 |
|---|---|
| 1 | cartoon_jobs에 job 생성(status=processing) |
| 2 | 백그라운드에서 OpenAIService.generate_cartoon 실행 |
| 3 | 성공 시 result_image_url 저장 + PostService.create_post + CARTOON_SUCCESS 알림 |
| 4 | 실패 시 status=failed, error_message 저장 + CARTOON_FAILED 알림 |
| 5 | 취소 요청은 status=canceling 전이(Cloud Function 처리) |

---

## 1) comments

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/posts/{post_id}/comments | jwt_required | 댓글 생성 | 201, 400, 401, 404, 500 |
| GET | /api/posts/{post_id}/comments | optional | 댓글 목록 조회(페이징) | 200, 500 |
| DELETE | /api/comments/{comment_id} | jwt_required | 댓글 삭제(작성자만) | 204, 401, 403, 404 |
| POST | /api/comments/{comment_id}/like | jwt_required | 댓글 좋아요 토글 | 200, 401, 404, 500 |

### 요청/응답 스키마

| 스키마 | 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|---|
| CommentCreateSchema | text | string(1..1000) | ✔ |  |
| CommentResponse | comment_id | UUID | ✔ |  |
|  | post_id | UUID | ✔ |  |
|  | author | object{ user_id:UUID, nickname:string, profile_image_url:URL|null } | ✔ |  |
|  | text | string | ✔ |  |
|  | like_count | int | ✔ |  |
|  | created_at | ISO8601 | ✔ |  |
|  | is_liked | boolean |  | optional |

### 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| POST | 400 VALIDATION_ERROR | 스키마 검증 실패 |
|  | 404 RESOURCE_NOT_FOUND | 작성자/게시글 없음 |
|  | 500 COMMENT_CREATION_FAILED | 서버 오류 |
| GET | 500 INTERNAL_SERVER_ERROR | 서버 오류 |
| DELETE | 403 FORBIDDEN | 권한 없음 |
|  | 404 NOT_FOUND | 미존재 |
| LIKE | 404 COMMENT_NOT_FOUND | 미존재 |
|  | 500 LIKE_TOGGLE_FAILED | 서버 오류 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 403 | FORBIDDEN | 이 리소스를 삭제/변경할 권한이 없습니다. |
| 404 | NOT_FOUND/COMMENT_NOT_FOUND | 요청한 리소스를 찾을 수 없습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 500 | COMMENT_CREATION_FAILED/INTERNAL_SERVER_ERROR/LIKE_TOGGLE_FAILED | 서버 내부 오류가 발생했습니다. |

### 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 컬렉션 | comments, posts, users, likes |
| 키 | comment_id=UUID, like 키: comment_{user_id}_{comment_id} |
| 생성 | 트랜잭션: comments set + posts.comment_count 증가 |
| 멘션 | @nickname → NotificationType.MENTION 알림 |
| 좋아요 | likes upsert/delete + comments.like_count 증감, COMMENT_LIKE 알림 |

---

## 2) notifications

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| GET | /api/notifications | jwt_required | 내 알림 목록 조회(페이징) | 200, 401, 500 |
| POST | /api/notifications/{notification_id}/ack | jwt_required | 알림 읽음 처리 | 200/204, 401, 404, 500 |
| GET | /api/notifications/unread-count | jwt_required | 읽지 않은 알림 개수 조회 | 200, 401, 500 |

### 출력/데이터 타입

| 객체 | 필드 | 타입 | 비고 |
|---|---|---|---|
| Notification item | id | UUID |  |
|  | type | string(enum) |  |
|  | title | string |  |
|  | message | string |  |
|  | created_at | ISO8601 |  |
|  | deeplink | string(app://...) |  |
|  | read | boolean |  |
| List Response | notifications | array<item> |  |
|  | next_cursor | string | optional |
|  | has_more | boolean | optional |
| Ack Response | message | string |  |

### 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| 목록 | 500 FETCH_FAILED | 서버 오류 |
| ack | 404 NOT_FOUND_OR_FORBIDDEN | 미존재/권한 없음 |
|  | 500 ACK_FAILED | 서버 오류 |
| unread-count | 500 FETCH_FAILED | 서버 오류 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 404 | NOT_FOUND_OR_FORBIDDEN | 알림을 찾을 수 없거나 권한이 없습니다. |
| 500 | FETCH_FAILED/ACK_FAILED | 알림 데이터를 처리하는 중 오류가 발생했습니다. |

### 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 생성 | recipient 검증 + preferences(types, mode) 반영, in-app 저장, 필요 시 FCM 발송 |
| 목록 | recipient_id 기준 내림차순, limit+1로 has_more 판단, created_at ISO 보정 |
| ack | 소유자 일치 시 is_read=true 업데이트 |
| unread | count() 또는 stream 합산 |

---

## 3) pet_care/records

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/pet-care/{pet_id}/records | jwt_required | 케어 기록 생성(멱등, request_id) | 200, 400, 401, 500 |
| GET | /api/pet-care/{pet_id}/records | jwt_required | 케어 기록 유연 조회(기간/타입/페이징) | 200, 400, 401, 500 |
| GET | /api/pet-care/{pet_id}/records/{record_type} | jwt_required | 특정 타입 기록 조회(페이징) | 200, 400, 401, 500 |
| GET | /api/pet-care/{pet_id}/records/legacy | jwt_required | 구버전 호환 조회(Deprecated) | 200, 400, 401, 500 |
| PATCH | /api/pet-care/{pet_id}/records/{log_id} | jwt_required | 케어 기록 일부 수정 | 200, 400, 401, 403, 404, 500 |
| DELETE | /api/pet-care/{pet_id}/records/{log_id} | jwt_required | 케어 기록 삭제 | 204, 401, 403, 404, 500 |

### 요청/쿼리/응답 스키마

| 스키마 | 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|---|
| CareRecordCreate | record_type | string(enum: weight|water|activity|meal|bcs) | ✔ |  |
|  | timestamp | timestamp(ms) | ✔ | UTC로 변환 저장 |
|  | data | object | ✔ | 타입별 구조 |
|  | notes | string |  | optional |
|  | request_id | string |  | optional(멱등키) |
| RecordsQuery | date | string(YYYY-MM-DD) |  | date 또는 기간 쿼리 |
|  | start_date/end_date | string(YYYY-MM-DD) |  |  |
|  | record_types | array<string> 또는 string(csv) |  | 최대 10 |
|  | grouped | boolean |  |  |
|  | limit | int(1..100) |  | 기본 50 |
|  | cursor | string |  |  |
|  | sort | string(timestamp_asc|timestamp_desc) |  |  |
| Records Response | records[].log_id | UUID | ✔ |  |
|  | records[].pet_id | UUID | ✔ |  |
|  | records[].record_type | string | ✔ |  |
|  | records[].timestamp | timestamp(ms) | ✔ |  |
|  | records[].data | object | ✔ |  |
|  | records[].notes | string |  | optional |
|  | records[].searchDate | string(YYYY-MM-DD) | ✔ |  |
|  | meta.limit | int | ✔ |  |
|  | meta.has_more | boolean | ✔ |  |
|  | meta.next_cursor | string |  | optional |
|  | meta.total_count | int |  | optional |
|  | grouped | object |  | optional |

### 오류/예외

| 구분 | 4xx/5xx | 조건 |
|---|---|---|
| POST | 400 VALIDATION_ERROR | 스키마 검증 실패 |
|  | 500 RECORD_CREATION_FAILED | 서버 오류 |
| GET(records) | 400 VALIDATION_ERROR | 스키마 검증 실패 |
|  | 500 FETCH_FAILED | 서버 오류 |
| GET(by type) | 400 INVALID_RECORD_TYPE/VALIDATION_ERROR | 타입 오류/검증 실패 |
|  | 500 FETCH_FAILED | 서버 오류 |
| legacy | 400 MISSING_PARAMETERS/INVALID_DATE_FORMAT | 파라미터/형식 오류 |
|  | 500 FETCH_FAILED | 서버 오류 |
| PATCH | 400 VALIDATION_ERROR | 검증 실패 |
|  | 404 NOT_FOUND | 미존재 |
|  | 403 FORBIDDEN | 권한 없음 |
|  | 500 UPDATE_FAILED | 서버 오류 |
| DELETE | 404 NOT_FOUND | 미존재 |
|  | 403 FORBIDDEN | 권한 없음 |
|  | 500 DELETE_FAILED | 서버 오류 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 400 | INVALID_RECORD_TYPE | 지원하지 않는 기록 타입입니다. |
| 400 | MISSING_PARAMETERS/INVALID_DATE_FORMAT | 필수 파라미터 누락 또는 날짜 형식이 올바르지 않습니다. |
| 403 | FORBIDDEN | 이 리소스를 변경할 권한이 없습니다. |
| 404 | NOT_FOUND | 요청한 기록을 찾을 수 없습니다. |
| 500 | FETCH_FAILED/RECORD_CREATION_FAILED/UPDATE_FAILED/DELETE_FAILED | 서버 내부 오류가 발생했습니다. |

### 저장/조회 및 인덱스

| 항목 | 내용 |
|---|---|
| 컬렉션 | pet_care_logs |
| 키 | log_id(request_id 또는 UUID) |
| 필드 | { log_id, pet_id, record_type, timestamp(UTC datetime), searchDate('YYYY-MM-DD'), data, notes } |
| 생성 | DateTimeUtils.from_timestamp_ms → searchDate 생성 → set(merge=True) 멱등 |
| 조회 | pet_id + searchDate eq/range + record_type in(≤10), 정렬/커서 페이징 |
| 인덱스 | (pet_id, searchDate, timestamp) 복합 색인 권장 |

---

## pet_care/settings

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| GET | /api/pet-care/{pet_id}/settings | jwt_required | 지정 펫의 케어 설정 조회 | 200, 401, 404, 500 |
| PUT | /api/pet-care/{pet_id}/settings | jwt_required | 지정 펫의 케어 설정 갱신 | 200, 400, 401, 404, 500 |

### 스키마/데이터 타입

| 필드 | 타입 | 제약/범위 | 비고 |
|---|---|---|---|
| goalWeight | float | 0.1..200.0 |  |
| waterBowlCapacity | int | 1..5000 |  |
| waterIncrementAmount | int | 1..1000 |  |
| goalActivityMinutes | int | 0..1440 |  |
| activityIncrementMinutes | int | 1..180 |  |
| goalMealCount | int | 1..10 |  |
| mealIncrementCount | int | 1..5 |  |
| updated_at | ISO8601 | dump_only |  |
| pet_id | string | dump_only |  |

### 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| GET | 404 SETTINGS_NOT_FOUND | 미존재 |
|  | 500 FETCH_FAILED | 서버 오류 |
| PUT | 400 VALIDATION_ERROR/NO_DATA | 검증 실패/본문 없음 |
|  | 404 SETTINGS_NOT_FOUND | 미존재 |
|  | 500 UPDATE_FAILED | 서버 오류 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 400 | NO_DATA | 변경할 데이터가 없습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 404 | SETTINGS_NOT_FOUND | 설정을 찾을 수 없습니다. |
| 500 | FETCH_FAILED/UPDATE_FAILED | 서버 내부 오류가 발생했습니다. |

### 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 컬렉션 | pet_settings (doc ID=pet_id; pets와 1:1) |
| 초기 생성 | create_initial_settings_transactional (품종/성별 기반 목표치 산정) |
| 타임스탬프 | DateTimeUtils.now → for_firestore 저장 |
| 조회/수정 | 존재 확인 + updated_at 갱신 |

---

## pets

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/pets/ | jwt_required | 최초 반려동물 등록 | 201, 400, 401, 500 |
| GET | /api/pets/{pet_id} | jwt_required | 소유자 전용 Full Profile 조회 | 200, 401, 403, 500 |
| PATCH | /api/pets/{pet_id} | jwt_required | 펫 프로필 부분 수정 | 200, 400, 401, 403, 500 |
| GET | /api/pets/public-profile/{pet_id} | optional | 공개 프로필 조회 | 200, 404, 500 |
| POST | /api/pets/{pet_id}/nose-print | jwt_required | 비문 등록/인증 | 200, 400, 403, 500 |
| POST | /api/pets/{pet_id}/eye-analysis | jwt_required | 안구 이미지 분석 | 200, 400, 403, 500 |

### 스키마/데이터 타입

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

### 오류/예외 (요약)

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| POST /api/pets/ | 400 VALIDATION_ERROR | 스키마 실패 |
|  | 500 PET_REGISTRATION_FAILED | 등록 실패 |
| GET /api/pets/{pet_id} | 403 FORBIDDEN_OR_NOT_FOUND | 소유권 없음/미존재 |
|  | 500 FETCH_FAILED | 서버 오류 |
| PATCH /api/pets/{pet_id} | 400 VALIDATION_ERROR | 검증 실패 |
|  | 403 UPDATE_FAILED_FORBIDDEN | 권한 없음 |
|  | 500 INTERNAL_SERVER_ERROR | 서버 오류 |
| GET /api/pets/public-profile/{pet_id} | 404 PET_NOT_FOUND | 미존재 |
|  | 500 FETCH_FAILED | 서버 오류 |
| /nose-print, /eye-analysis | 400/403/500 | 각 시나리오 참고 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 403 | FORBIDDEN_OR_NOT_FOUND/UPDATE_FAILED_FORBIDDEN | 접근 권한이 없거나 리소스를 변경할 수 없습니다. |
| 404 | PET_NOT_FOUND | 반려동물을 찾을 수 없습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 500 | FETCH_FAILED/PET_REGISTRATION_FAILED/INTERNAL_SERVER_ERROR | 서버 내부 오류가 발생했습니다. |

### 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 등록 | 트랜잭션: pets 생성(asdict→for_firestore) + pet_settings 초기화 |
| Nose | 권한 확인 → pipeline 처리 → SUCCESS 시 pets 업데이트 + 인덱스 반영 |
| Eye | 스토리지 다운로드 → 예측 → public url 시도 → analysis_history 저장 |

---

## posts

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/posts/ | jwt_required | 게시글 생성 | 201, 400, 401, 404, 500 |
| GET | /api/posts/ | optional | 피드 조회(페이징) | 200 |
| GET | /api/posts/{post_id} | optional | 게시글 상세(+is_liked) | 200, 404 |
| PATCH | /api/posts/{post_id} | jwt_required | 게시글 수정 | 200, 400, 401, 403, 404 |
| DELETE | /api/posts/{post_id} | jwt_required | 게시글 삭제(스토리지/문서) | 204, 401, 403, 404 |
| POST | /api/posts/{post_id}/like | jwt_required | 좋아요 토글(트랜잭션) | 200, 401, 404, 500 |
| GET | /api/posts/users/{author_id}/posts | optional | 특정 사용자 게시글 목록 | 200 |

### 스키마/데이터 타입

| 스키마 | 필드 | 타입 | 비고 |
|---|---|---|---|
| Author | user_id | UUID |  |
|  | nickname | string |  |
|  | profile_image_url | URL|null |  |
| PetInfo | pet_id | UUID |  |
|  | name | string |  |
|  | breed | string |  |
|  | birthdate | string(YYYY-MM-DD) |  |
| PostCreateSchema | text | string(1..2000) |  |
|  | file_paths | array<URL>[min 1] |  |
| PostUpdateSchema | text | string(1..2000) |  |
| PostResponseSchema | post_id | UUID |  |
|  | author | Author |  |
|  | pet | PetInfo |  |
|  | image_urls | array<URL> |  |
|  | text | string |  |
|  | like_count/comment_count | int |  |
|  | created_at/updated_at | ISO8601 |  |
|  | is_liked | boolean | optional |

### 오류/예외 (요약)

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| POST /api/posts/ | 400 VALIDATION_ERROR | 검증 실패 |
|  | 404 RESOURCE_NOT_FOUND | 작성자/반려동물 없음 |
|  | 500 POST_CREATION_FAILED | 서버 오류 |
| GET /api/posts/{post_id} | 404 POST_NOT_FOUND | 미존재 |
| PATCH /api/posts/{post_id} | 400/403/404 | 검증 실패/권한 없음/미존재 |
| DELETE /api/posts/{post_id} | 403/404 | 권한 없음/미존재 |
| LIKE | 404 POST_NOT_FOUND | 미존재 |
|  | 500 LIKE_TOGGLE_FAILED | 서버 오류 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 403 | FORBIDDEN | 이 게시글을 수정/삭제할 권한이 없습니다. |
| 404 | POST_NOT_FOUND/RESOURCE_NOT_FOUND | 요청한 게시글/리소스를 찾을 수 없습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 500 | POST_CREATION_FAILED/LIKE_TOGGLE_FAILED | 서버 내부 오류가 발생했습니다. |

### 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 컬렉션 | posts, users, pets, likes |
| 생성 | Author/PetInfo 구성 → DateTimeUtils.for_firestore 저장 |
| 피드 | created_at desc 정렬, cursor 페이징, is_liked 추론(batched) |
| 수정 | 소유자 확인 후 text/updated_at |
| 삭제 | 스토리지 파일 삭제 후 문서 삭제 |
| 인덱스 | (created_at desc), (author.user_id, created_at desc) |

---

## uploads

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/uploads/url | jwt_required | 업로드용 Pre-signed URL 발급 | 200, 400, 401, 500 |
| POST | /api/uploads/finalize-cartoon | jwt_required | 업로드된 파일 공개 전환 및 URL 반환 | 200, 400, 401, 404, 500 |

### 요청/응답 타입

| 엔드포인트 | Request | Response |
|---|---|---|
| /url | { upload_type:string(enum), filename:string, content_type:string } | { upload_url:URL, file_path:string } |
| /finalize-cartoon | { file_path:string } | { public_url:URL } |

### 오류/검증

| 코드 | 조건 |
|---|---|
| 400 INVALID_PARAMETERS | upload_type/filename/content_type 누락/형식 오류 |
| 400 VALIDATION_ERROR | file_path 스키마 검증 실패 |
| 400 INVALID_UPLOAD_TYPE | 미지원 upload_type |
| 404 FILE_NOT_FOUND | Storage에 파일 없음 |
| 500 URL_GENERATION_FAILED/INTERNAL_SERVER_ERROR | 서버 오류 |

#### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 400 | INVALID_PARAMETERS | 필수 파라미터가 누락되었거나 형식이 올바르지 않습니다. |
| 400 | INVALID_UPLOAD_TYPE | 지원하지 않는 업로드 타입입니다. |
| 404 | FILE_NOT_FOUND | 업로드된 파일을 찾을 수 없습니다. |
| 500 | URL_GENERATION_FAILED/INTERNAL_SERVER_ERROR | 업로드 URL 생성/처리 중 오류가 발생했습니다. |

### Persistence & Services

| 항목 | 내용 |
|---|---|
| 업로드 URL | StorageService.generate_upload_url(user_id, upload_type, filename, content_type) |
| 공개 전환 | StorageService.make_public_and_get_url(file_path) |
| 저장 | Firestore 저장 없음(경로/URL 발급/전환) |

---

## users

### 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| GET | /api/users/{user_id} | optional | 공개 프로필 + post_count | 200 |
| PATCH | /api/users/me/profile-image | jwt_required | file_path 기반 프로필 이미지 갱신 | 200, 401 |
| DELETE | /api/users/me | jwt_required | 계정 삭제(Firebase Auth) | 200, 401, 500 |
| GET | /api/users/me/notification-preferences | jwt_required | 알림 개인 설정 조회 | 200, 401 |
| PATCH | /api/users/me/notification-preferences | jwt_required | 알림 개인 설정 업데이트 | 200, 400, 401, 500 |
| POST | /api/users/me/fcm-token | jwt_required | FCM 토큰 등록/업데이트 | 200, 401 |
| GET | /api/users/{user_id}/summary | optional | 공개 사용자 요약 + (pet_id) 반려견 요약 | 200, 500 |
| GET | /api/users/me/summary | optional | 현재 사용자/선택 반려견/해당 설정 요약 | 200, 500 |
| GET | /api/users/me/selected-pet | jwt_required | 현재 선택된 펫 조회 | 200/204, 401, 403, 404 |
| PATCH | /api/users/me/selected-pet | jwt_required | 현재 선택된 펫 설정(멱등) | 200, 400, 401, 403, 404 |

### 스키마/데이터 타입

| 스키마 | 필드 | 타입 | 비고 |
|---|---|---|---|
| UserPublicResponseSchema | user_id | UUID |  |
|  | nickname | string |  |
|  | profile_image_url | URL|null |  |
|  | post_count | int |  |
| FCMTokenSchema | fcm_token | string |  |
| NotificationPreferencesSchema | mode | string|null | optional |
|  | types | object{ [type:string]: boolean } | optional |
| SelectedPetUpdateSchema | pet_id | UUID |  |

### selected-pet 응답/오류 타입

| 엔드포인트 | 2xx 응답 | 타입/설명 |
|---|---|---|
| GET /me/selected-pet | 200 { pet_id:UUID, name?:string, profile_image_url?:URL|null, updated_at?:ISO8601 } | 선택 펫 존재 |
|  | 204 No Content | 선택 펫 없음 |
| PATCH /me/selected-pet | 200 { pet_id:UUID } | 설정 성공 |

| 엔드포인트 | 4xx | 조건/메시지 |
|---|---|---|
| GET /me/selected-pet | 403 | 기록은 있으나 소유권 상실 → { message } |
|  | 404 | 기록은 있으나 펫 삭제/부재 → { message } |
| PATCH /me/selected-pet | 400 | UUID 형식 오류 → { message, errors } |
|  | 403 | 존재하지만 타 사용자 소유 → { message } |
|  | 404 | pet_id 미존재 → { message } |

#### selected-pet 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 400 | VALIDATION_ERROR | 유효하지 않은 요청 본문입니다. |
| 403 | FORBIDDEN | 선택된 반려동물에 대한 소유 권한이 없습니다. |
| 404 | PET_NOT_FOUND | 선택된 반려동물을 찾을 수 없습니다. |

### Persistence & Services

| 항목 | 내용 |
|---|---|
| users | 프로필, fcm_token, notification_preferences 저장 |
| selected-pet | 컬렉션: user_selected_pet (doc id=user_id) |
|  | 필드: { user_id:string, pet_id:string|null, updated_at:Timestamp(UTC) } |
|  | GET: 문서 없음 또는 pet_id=null → 204 |
|  | PATCH: set(upsert) 멱등, Last-Write-Wins, 응답 시 updated_at은 ISO8601 변환 |

---



---

## 예시 응답 페이로드 모음

다음은 각 엔드포인트의 대표 성공/오류 응답 예시입니다. 실제 값은 상황에 따라 달라질 수 있습니다.

### auth

- POST /api/auth/social (200)

```
{
	"access_token": "eyJhbGciOi...",
	"refresh_token": "eyJhbGciOi...",
	"user_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
	"is_new_user": false,
	"user_info": {
		"user_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
		"email": "user@example.com",
		"nickname": "해피도그",
		"profile_image_url": "https://storage.googleapis.com/bucket/users/u1.png"
	}
}
```

- POST /api/auth/token/refresh (200)

```
{ "access_token": "eyJhbGciOi..." }
```

- POST /api/auth/logout (200)

```
{ "message": "Logged out" }
```

- 공통 오류 예시 (401/400/422/500)

```
{ "error_code": "INVALID_AUTH_CODE", "message": "유효하지 않은 인증 코드입니다." }
```

### breeds

- GET /api/breeds/ (200)

```
{
	"breeds": [
		{
			"breed_name": "Shiba Inu",
			"life_expectancy": 12.5,
			"height_cm": { "male": 39.5, "female": 36.8 },
			"weight_kg": { "male": 10.5, "female": 8.8 },
			"created_at": "2024-10-01T00:00:00Z",
			"updated_at": "2025-01-15T00:00:00Z"
		}
	],
	"total_count": 120
}
```

- GET /api/breeds/{breed_name} (200)

```
{
	"breed_name": "Shiba Inu",
	"life_expectancy": 12.5,
	"height_cm": { "male": 39.5, "female": 36.8 },
	"weight_kg": { "male": 10.5, "female": 8.8 },
	"created_at": "2024-10-01T00:00:00Z",
	"updated_at": "2025-01-15T00:00:00Z"
}
```

- 오류 예시 (404)

```
{ "error_code": "BREED_NOT_FOUND", "message": "요청한 품종을 찾을 수 없습니다." }
```

### cartoon_jobs

- POST /api/cartoon-jobs/ (202)

```
{
	"job_id": "5f6e7d8c-9b0a-4c3d-8e2f-112233445566",
	"user_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
	"status": "processing",
	"original_image_url": "gs://bucket/cartoon/u1/img_001.png",
	"user_text": "우리 강아지 카툰화",
	"created_at": "2025-09-08T00:00:00Z",
	"updated_at": "2025-09-08T00:00:00Z"
}
```

- GET /api/cartoon-jobs/{job_id} (200)

```
{
	"job_id": "5f6e7d8c-9b0a-4c3d-8e2f-112233445566",
	"user_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
	"status": "succeeded",
	"original_image_url": "gs://bucket/cartoon/u1/img_001.png",
	"result_image_url": "https://storage.googleapis.com/bucket/public/cartoon/u1/img_001.png",
	"created_at": "2025-09-08T00:00:00Z",
	"updated_at": "2025-09-08T00:03:12Z"
}
```

- DELETE /api/cartoon-jobs/{job_id} (200)

```
{ "message": "Cancel requested" }
```

- 오류 예시 (409)

```
{ "error_code": "INVALID_STATE_FOR_CANCEL", "message": "현재 상태에서는 취소할 수 없습니다." }
```

### comments

- POST /api/posts/{post_id}/comments (201)

```
{
	"comment_id": "c0011223-4455-6677-8899-aabbccddeeff",
	"post_id": "p0011223-4455-6677-8899-aabbccddeeff",
	"author": {
		"user_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
		"nickname": "해피도그",
		"profile_image_url": "https://.../users/u1.png"
	},
	"text": "너무 귀여워요!",
	"like_count": 0,
	"created_at": "2025-09-08T00:00:00Z"
}
```

- GET /api/posts/{post_id}/comments (200)

```
{
	"comments": [ { "comment_id": "...", "post_id": "...", "author": { "user_id": "...", "nickname": "...", "profile_image_url": null }, "text": "...", "like_count": 3, "created_at": "2025-09-08T00:00:00Z", "is_liked": true } ],
	"next_cursor": "last_comment_id"
}
```

- DELETE /api/comments/{comment_id} (204)

No Content

- POST /api/comments/{comment_id}/like (200)

```
{ "is_liked": true, "like_count": 4 }
```

- 오류 예시 (404)

```
{ "error_code": "COMMENT_NOT_FOUND", "message": "요청한 댓글을 찾을 수 없습니다." }
```

### notifications

- GET /api/notifications (200)

```
{
	"notifications": [
		{
			"id": "n0011223-4455-6677-8899-aabbccddeeff",
			"type": "COMMENT",
			"title": "새 댓글",
			"message": "회원님 게시글에 새로운 댓글이 달렸습니다.",
			"created_at": "2025-09-08T00:00:00Z",
			"deeplink": "app://posts/p0011223-4455-6677-8899-aabbccddeeff",
			"read": false
		}
	],
	"next_cursor": "n0011223-...",
	"has_more": true
}
```

- POST /api/notifications/{notification_id}/ack (200)

```
{ "message": "ACK" }
```

- GET /api/notifications/unread-count (200)

```
{ "unread_count": 5 }
```

- 오류 예시 (404)

```
{ "error_code": "NOT_FOUND_OR_FORBIDDEN", "message": "알림을 찾을 수 없거나 권한이 없습니다." }
```

### pet_care/records

- POST /api/pet-care/{pet_id}/records (200)

```
{
	"log_id": "l0011223-4455-6677-8899-aabbccddeeff",
	"pet_id": "pet-uuid",
	"record_type": "meal",
	"timestamp": 1736361600000,
	"searchDate": "2025-01-09",
	"data": { "kcal": 120, "brand": "Acme" },
	"notes": "아침 식사"
}
```

- GET /api/pet-care/{pet_id}/records (200)

```
{
	"records": [
		{ "log_id": "...", "pet_id": "...", "record_type": "weight", "timestamp": 1736361600000, "data": { "kg": 7.8 }, "searchDate": "2025-01-09" }
	],
	"meta": { "limit": 50, "has_more": false, "next_cursor": null, "total_count": 1 }
}
```

- GET /api/pet-care/{pet_id}/records/{record_type} (200)

```
{
	"records": [ { "log_id": "...", "timestamp": 1736361600000, "data": { "ml": 200 } } ],
	"meta": { "record_type": "water", "limit": 50, "has_more": false, "next_cursor": null }
}
```

- GET /api/pet-care/{pet_id}/records/legacy (200)

```
{
	"weight": [],
	"water": [ { "log_id": "...", "timestamp": 1736361600000, "data": { "ml": 200 } } ],
	"activity": [],
	"meal": [],
	"bcs": []
}
```

- PATCH /api/pet-care/{pet_id}/records/{log_id} (200)

```
{ "log_id": "...", "notes": "메모 수정", "timestamp": 1736365200000 }
```

- DELETE /api/pet-care/{pet_id}/records/{log_id} (204)

No Content

- 오류 예시 (400)

```
{ "error_code": "VALIDATION_ERROR", "message": "요청 데이터 검증에 실패했습니다.", "details": { "record_type": ["필수 값입니다."] } }
```

### pet_care/settings

- GET /api/pet-care/{pet_id}/settings (200)

```
{
	"pet_id": "pet-uuid",
	"goalWeight": 8.2,
	"waterBowlCapacity": 450,
	"waterIncrementAmount": 90,
	"goalActivityMinutes": 60,
	"activityIncrementMinutes": 15,
	"goalMealCount": 2,
	"mealIncrementCount": 1,
	"updated_at": "2025-09-08T00:00:00Z"
}
```

- PUT /api/pet-care/{pet_id}/settings (200)

```
{
	"pet_id": "pet-uuid",
	"goalWeight": 8.5,
	"waterBowlCapacity": 500,
	"waterIncrementAmount": 100,
	"goalActivityMinutes": 90,
	"activityIncrementMinutes": 15,
	"goalMealCount": 3,
	"mealIncrementCount": 1,
	"updated_at": "2025-09-08T00:00:05Z"
}
```

- 오류 예시 (404)

```
{ "error_code": "SETTINGS_NOT_FOUND", "message": "설정을 찾을 수 없습니다." }
```

### pets

- POST /api/pets/ (201)

```
{
	"pet_id": "pet-uuid",
	"user_id": "user-uuid",
	"name": "콩이",
	"gender": "FEMALE",
	"breed": "Shiba Inu",
	"birthdate": "2022-03-01",
	"initial_weight": 7.2,
	"fur_color": "brown",
	"health_concerns": [],
	"is_verified": false,
	"nose_print_url": null,
	"faiss_id": null
}
```

- GET /api/pets/{pet_id} (200)

```
{
	"pet_id": "pet-uuid",
	"user_id": "user-uuid",
	"name": "콩이",
	"gender": "FEMALE",
	"breed": "Shiba Inu",
	"birthdate": "2022-03-01",
	"initial_weight": 7.2,
	"fur_color": "brown",
	"health_concerns": ["allergy"],
	"is_verified": true,
	"nose_print_url": "https://.../pets/pet-uuid/nose.png",
	"faiss_id": 1234
}
```

- PATCH /api/pets/{pet_id} (200)

```
{ "pet_id": "pet-uuid", "name": "콩이", "fur_color": "white" }
```

- GET /api/pets/public-profile/{pet_id} (200)

```
{
	"pet_id": "pet-uuid",
	"name": "콩이",
	"gender": "FEMALE",
	"breed": "Shiba Inu",
	"birthdate": "2022-03-01",
	"initial_weight": 7.2,
	"fur_color": "brown",
	"is_verified": true
}
```

- POST /api/pets/{pet_id}/nose-print (200)

```
{ "status": "SUCCESS", "nose_print_url": "https://.../public/pets/pet-uuid/nose.png", "faiss_id": 1234 }
```

- POST /api/pets/{pet_id}/eye-analysis (200)

```
{ "analysis_id": "ea-uuid", "disease_name": "conjunctivitis", "probability": 0.87 }
```

- 오류 예시 (403)

```
{ "error_code": "UPDATE_FAILED_FORBIDDEN", "message": "이 리소스를 변경할 권한이 없습니다." }
```

### posts

- POST /api/posts/ (201)

```
{
	"post_id": "post-uuid",
	"author": { "user_id": "user-uuid", "nickname": "해피도그", "profile_image_url": null },
	"pet": { "pet_id": "pet-uuid", "name": "콩이", "breed": "Shiba Inu", "birthdate": "2022-03-01" },
	"image_urls": ["https://.../public/posts/p1.png"],
	"text": "첫 산책!",
	"like_count": 0,
	"comment_count": 0,
	"created_at": "2025-09-08T00:00:00Z",
	"updated_at": "2025-09-08T00:00:00Z"
}
```

- GET /api/posts/ (200)

```
{
	"posts": [ { "post_id": "post-uuid", "author": { "user_id": "user-uuid", "nickname": "해피도그", "profile_image_url": null }, "pet": { "pet_id": "pet-uuid", "name": "콩이", "breed": "Shiba Inu", "birthdate": "2022-03-01" }, "image_urls": ["https://..."], "text": "첫 산책!", "like_count": 1, "comment_count": 2, "created_at": "2025-09-08T00:00:00Z", "updated_at": "2025-09-08T00:00:00Z", "is_liked": true } ],
	"next_cursor": "post-uuid"
}
```

- GET /api/posts/{post_id} (200)

```
{
	"post_id": "post-uuid",
	"author": { "user_id": "user-uuid", "nickname": "해피도그", "profile_image_url": null },
	"pet": { "pet_id": "pet-uuid", "name": "콩이", "breed": "Shiba Inu", "birthdate": "2022-03-01" },
	"image_urls": ["https://..."],
	"text": "첫 산책!",
	"like_count": 2,
	"comment_count": 3,
	"created_at": "2025-09-08T00:00:00Z",
	"updated_at": "2025-09-08T00:10:00Z",
	"is_liked": false
}
```

- PATCH /api/posts/{post_id} (200)

```
{ "post_id": "post-uuid", "text": "수정된 텍스트" }
```

- DELETE /api/posts/{post_id} (204)

No Content

- POST /api/posts/{post_id}/like (200)

```
{ "is_liked": true, "like_count": 3 }
```

- GET /api/posts/users/{author_id}/posts (200)

```
{ "posts": [ { "post_id": "post-uuid", "author": { "user_id": "user-uuid", "nickname": "해피도그", "profile_image_url": null }, "pet": { "pet_id": "pet-uuid", "name": "콩이", "breed": "Shiba Inu", "birthdate": "2022-03-01" }, "image_urls": ["https://..."], "text": "첫 산책!", "like_count": 1, "comment_count": 2, "created_at": "2025-09-08T00:00:00Z", "updated_at": "2025-09-08T00:00:00Z" } ], "next_cursor": null }
```

### uploads

- POST /api/uploads/url (200)

```
{ "upload_url": "https://storage.googleapis.com/...:sign", "file_path": "uploads/users/u1/2025/09/08/img.png" }
```

- POST /api/uploads/finalize-cartoon (200)

```
{ "public_url": "https://storage.googleapis.com/public/cartoon/u1/img.png" }
```

- 오류 예시 (404)

```
{ "error_code": "FILE_NOT_FOUND", "message": "업로드된 파일을 찾을 수 없습니다." }
```

### users

- GET /api/users/{user_id} (200)

```
{ "user_id": "user-uuid", "nickname": "해피도그", "profile_image_url": null, "post_count": 12 }
```

- PATCH /api/users/me/profile-image (200)

```
{ "profile_image_url": "https://storage.googleapis.com/.../users/u1.png" }
```

- DELETE /api/users/me (200)

```
{ "message": "Account deleted" }
```

- GET /api/users/me/notification-preferences (200)

```
{ "mode": "ALL", "types": { "COMMENT": true, "POST_LIKE": true, "MENTION": true } }
```

- PATCH /api/users/me/notification-preferences (200)

```
{ "mode": "IN_APP_ONLY", "types": { "COMMENT": true, "POST_LIKE": false, "MENTION": true } }
```

- POST /api/users/me/fcm-token (200)

```
{ "message": "FCM token registered" }
```

- GET /api/users/{user_id}/summary (200)

```
{
	"user": { "user_id": "user-uuid", "nickname": "해피도그", "profile_image_url": null, "post_count": 12 },
	"pet": { "pet_id": "pet-uuid", "name": "콩이", "age_months": 30 }
}
```

- GET /api/users/me/summary (200)

```
{
	"user": { "user_id": "user-uuid", "nickname": "해피도그", "profile_image_url": null },
	"selected_pet": { "pet_id": "pet-uuid", "name": "콩이" },
	"settings": { "goalWeight": 8.2, "goalMealCount": 2 }
}
```

- GET /api/users/me/selected-pet (200)

```
{ "pet_id": "pet-uuid", "name": "콩이", "profile_image_url": null, "updated_at": "2025-09-08T00:00:00Z" }
```

- GET /api/users/me/selected-pet (204)

No Content

- PATCH /api/users/me/selected-pet (200)

```
{ "pet_id": "pet-uuid" }
```

- 오류 예시 (403/404)

```
{ "message": "선택된 반려동물에 대한 소유 권한이 없습니다." }
```

---

## 요청/응답 예시 — 한 화면 블록



### 1) auth

#### POST /api/auth/social
Request
```
{ "provider": "google", "auth_code": "4/0AX4X..." }
```
Response (200)
```
{ "access_token": "...", "refresh_token": "...", "user_id": "...", "is_new_user": false, "user_info": { "user_id": "...", "email": "user@example.com", "nickname": "해피도그", "profile_image_url": null } }
```

#### POST /api/auth/token/refresh
Request (헤더의 Refresh JWT 사용)
```
{}
```
Response (200)
```
{ "access_token": "..." }
```

#### POST /api/auth/logout
Request
```
{ "access_token": "...", "refresh_token": "..." }
```
Response (200)
```
{ "message": "Logged out" }
```

### 2) breeds

#### GET /api/breeds/
Request (Query)
```
?limit=20&offset=breed_name%3APoodle&summary=false
```
Response (200)
```
{ "breeds": [ { "breed_name": "Shiba Inu", "life_expectancy": 12.5, "height_cm": {"male": 39.5, "female": 36.8}, "weight_kg": {"male": 10.5, "female": 8.8} } ], "total_count": 120 }
```

#### GET /api/breeds/{breed_name}
Request (Path)
```
/api/breeds/Shiba%20Inu
```
Response (200)
```
{ "breed_name": "Shiba Inu", "life_expectancy": 12.5, "height_cm": {"male": 39.5, "female": 36.8}, "weight_kg": {"male": 10.5, "female": 8.8} }
```

#### GET /api/breeds/search
Request (Query)
```
?q=shi&limit=10
```
Response (200)
```
{ "breeds": [ { "breed_name": "Shiba Inu", "life_expectancy": 12.5 } ], "total_count": 1 }
```

#### GET /api/breeds/exists/{breed_name}
Request (Path)
```
/api/breeds/exists/Shiba%20Inu
```
Response (200)
```
{ "breed_name": "Shiba Inu", "exists": true }
```

#### GET /api/breeds/statistics
Request
```
{}
```
Response (200)
```
{ "stats": { "count": 120, "avg": 12.3, "min": 8.0, "max": 20.0 } }
```

### 3) cartoon_jobs

#### POST /api/cartoon-jobs/
Request
```
{ "file_paths": ["gs://bucket/u1/img.png"], "user_text": "강아지 카툰" }
```
Response (202)
```
{ "job_id": "...", "user_id": "...", "status": "processing", "original_image_url": "gs://bucket/u1/img.png", "created_at": "...", "updated_at": "..." }
```

#### GET /api/cartoon-jobs/{job_id}
Request (Path)
```
/api/cartoon-jobs/{job_id}
```
Response (200)
```
{ "job_id": "...", "user_id": "...", "status": "succeeded", "original_image_url": "gs://...", "result_image_url": "https://...", "created_at": "...", "updated_at": "..." }
```

#### DELETE /api/cartoon-jobs/{job_id}
Request (Path)
```
/api/cartoon-jobs/{job_id}
```
Response (200)
```
{ "message": "Cancel requested" }
```

### 1) comments

#### POST /api/posts/{post_id}/comments
Request
```
{ "text": "너무 귀여워요!" }
```
Response (201)
```
{ "comment_id": "...", "post_id": "...", "author": { "user_id": "...", "nickname": "...", "profile_image_url": null }, "text": "너무 귀여워요!", "like_count": 0, "created_at": "..." }
```

#### GET /api/posts/{post_id}/comments
Request (Query)
```
?limit=20&cursor=
```
Response (200)
```
{ "comments": [ { "comment_id": "...", "post_id": "...", "author": { "user_id": "...", "nickname": "...", "profile_image_url": null }, "text": "...", "like_count": 3, "created_at": "...", "is_liked": true } ], "next_cursor": "..." }
```

#### DELETE /api/comments/{comment_id}
Request (Path)
```
/api/comments/{comment_id}
```
Response (204)
```
No Content
```

#### POST /api/comments/{comment_id}/like
Request
```
{}
```
Response (200)
```
{ "is_liked": true, "like_count": 4 }
```

### 2) notifications

#### GET /api/notifications
Request (Query)
```
?limit=20&cursor=
```
Response (200)
```
{ "notifications": [ { "id": "...", "type": "COMMENT", "title": "새 댓글", "message": "...", "created_at": "...", "deeplink": "app://posts/...", "read": false } ], "next_cursor": "...", "has_more": true }
```

#### POST /api/notifications/{notification_id}/ack
Request (Path)
```
/api/notifications/{notification_id}/ack
```
Response (200)
```
{ "message": "ACK" }
```

#### GET /api/notifications/unread-count
Request
```
{}
```
Response (200)
```
{ "unread_count": 5 }
```

### 3) pet_care/records

#### POST /api/pet-care/{pet_id}/records
Request
```
{ "record_type": "meal", "timestamp": 1736361600000, "data": { "kcal": 120 }, "notes": "아침 식사", "request_id": "uuid-req-1" }
```
Response (200)
```
{ "log_id": "...", "pet_id": "...", "record_type": "meal", "timestamp": 1736361600000, "searchDate": "2025-01-09", "data": { "kcal": 120 }, "notes": "아침 식사" }
```

#### GET /api/pet-care/{pet_id}/records
Request (Query)
```
?date=2025-01-09&record_types=weight,meal&limit=20&cursor=
```
Response (200)
```
{ "records": [ { "log_id": "...", "pet_id": "...", "record_type": "weight", "timestamp": 1736361600000, "data": { "kg": 7.8 }, "searchDate": "2025-01-09" } ], "meta": { "limit": 20, "has_more": false } }
```

#### GET /api/pet-care/{pet_id}/records/{record_type}
Request (Path+Query)
```
/api/pet-care/{pet_id}/records/water?start_date=2025-01-01&end_date=2025-01-09
```
Response (200)
```
{ "records": [ { "log_id": "...", "timestamp": 1736361600000, "data": { "ml": 200 } } ], "meta": { "record_type": "water", "limit": 50, "has_more": false } }
```

#### GET /api/pet-care/{pet_id}/records/legacy
Request (Query)
```
?date=2025-01-09
```
Response (200)
```
{ "weight": [], "water": [ { "log_id": "...", "timestamp": 1736361600000, "data": { "ml": 200 } } ], "activity": [], "meal": [], "bcs": [] }
```

#### PATCH /api/pet-care/{pet_id}/records/{log_id}
Request
```
{ "notes": "메모 수정" }
```
Response (200)
```
{ "log_id": "...", "notes": "메모 수정" }
```

#### DELETE /api/pet-care/{pet_id}/records/{log_id}
Request (Path)
```
/api/pet-care/{pet_id}/records/{log_id}
```
Response (204)
```
No Content
```

### pet_care/settings

#### GET /api/pet-care/{pet_id}/settings
Request
```
{}
```
Response (200)
```
{ "pet_id": "pet-uuid", "goalWeight": 8.2, "waterBowlCapacity": 450, "waterIncrementAmount": 90, "goalActivityMinutes": 60, "activityIncrementMinutes": 15, "goalMealCount": 2, "mealIncrementCount": 1, "updated_at": "..." }
```

#### PUT /api/pet-care/{pet_id}/settings
Request
```
{ "goalWeight": 8.5, "goalMealCount": 3 }
```
Response (200)
```
{ "pet_id": "pet-uuid", "goalWeight": 8.5, "goalMealCount": 3, "updated_at": "..." }
```

### pets

#### POST /api/pets/
Request
```
{ "name": "콩이", "gender": "FEMALE", "breed": "Shiba Inu", "birthdate": "2022-03-01", "current_weight": 7.2, "fur_color": "brown", "health_concerns": [] }
```
Response (201)
```
{ "pet_id": "...", "user_id": "...", "name": "콩이", "gender": "FEMALE", "breed": "Shiba Inu", "birthdate": "2022-03-01", "initial_weight": 7.2, "fur_color": "brown", "health_concerns": [], "is_verified": false, "nose_print_url": null, "faiss_id": null }
```

#### GET /api/pets/{pet_id}
Request (Path)
```
/api/pets/{pet_id}
```
Response (200)
```
{ "pet_id": "...", "user_id": "...", "name": "콩이", "gender": "FEMALE", "breed": "Shiba Inu", "birthdate": "2022-03-01", "initial_weight": 7.2, "is_verified": true }
```

#### PATCH /api/pets/{pet_id}
Request
```
{ "name": "콩이", "fur_color": "white" }
```
Response (200)
```
{ "pet_id": "...", "name": "콩이", "fur_color": "white" }
```

#### GET /api/pets/public-profile/{pet_id}
Request (Path)
```
/api/pets/public-profile/{pet_id}
```
Response (200)
```
{ "pet_id": "...", "name": "콩이", "gender": "FEMALE", "breed": "Shiba Inu", "birthdate": "2022-03-01", "initial_weight": 7.2, "is_verified": true }
```

#### POST /api/pets/{pet_id}/nose-print
Request
```
{ "file_path": "gs://bucket/pets/pet-uuid/nose.png" }
```
Response (200)
```
{ "status": "SUCCESS", "nose_print_url": "https://.../nose.png", "faiss_id": 1234 }
```

#### POST /api/pets/{pet_id}/eye-analysis
Request
```
{ "file_path": "gs://bucket/pets/pet-uuid/eye.png" }
```
Response (200)
```
{ "analysis_id": "ea-uuid", "disease_name": "conjunctivitis", "probability": 0.87 }
```

### posts

#### POST /api/posts/
Request
```
{ "text": "첫 산책!", "file_paths": ["gs://bucket/posts/p1.png"] }
```
Response (201)
```
{ "post_id": "...", "author": { "user_id": "...", "nickname": "해피도그", "profile_image_url": null }, "pet": { "pet_id": "...", "name": "콩이", "breed": "Shiba Inu", "birthdate": "2022-03-01" }, "image_urls": ["https://..."], "text": "첫 산책!", "like_count": 0, "comment_count": 0, "created_at": "...", "updated_at": "..." }
```

#### GET /api/posts/
Request (Query)
```
?limit=20&cursor=
```
Response (200)
```
{ "posts": [ { "post_id": "...", "author": { "user_id": "...", "nickname": "해피도그", "profile_image_url": null }, "pet": { "pet_id": "...", "name": "콩이", "breed": "Shiba Inu", "birthdate": "2022-03-01" }, "image_urls": ["https://..."], "text": "첫 산책!", "like_count": 1, "comment_count": 2, "created_at": "...", "updated_at": "...", "is_liked": true } ], "next_cursor": "..." }
```

#### GET /api/posts/{post_id}
Request (Path)
```
/api/posts/{post_id}
```
Response (200)
```
{ "post_id": "...", "author": { "user_id": "...", "nickname": "해피도그", "profile_image_url": null }, "pet": { "pet_id": "...", "name": "콩이", "breed": "Shiba Inu", "birthdate": "2022-03-01" }, "image_urls": ["https://..."], "text": "첫 산책!", "like_count": 2, "comment_count": 3, "created_at": "...", "updated_at": "...", "is_liked": false }
```

#### PATCH /api/posts/{post_id}
Request
```
{ "text": "수정된 텍스트" }
```
Response (200)
```
{ "post_id": "...", "text": "수정된 텍스트" }
```

#### DELETE /api/posts/{post_id}
Request (Path)
```
/api/posts/{post_id}
```
Response (204)
```
No Content
```

#### POST /api/posts/{post_id}/like
Request
```
{}
```
Response (200)
```
{ "is_liked": true, "like_count": 3 }
```

#### GET /api/posts/users/{author_id}/posts
Request (Query)
```
?limit=20&cursor=
```
Response (200)
```
{ "posts": [ { "post_id": "...", "author": { "user_id": "...", "nickname": "해피도그", "profile_image_url": null }, "pet": { "pet_id": "...", "name": "콩이", "breed": "Shiba Inu", "birthdate": "2022-03-01" }, "image_urls": ["https://..."], "text": "첫 산책!", "like_count": 1, "comment_count": 2, "created_at": "...", "updated_at": "..." } ], "next_cursor": null }
```

### uploads

#### POST /api/uploads/url
Request
```
{ "upload_type": "post_image", "filename": "p1.png", "content_type": "image/png" }
```
Response (200)
```
{ "upload_url": "https://storage.googleapis.com/...:sign", "file_path": "uploads/users/u1/2025/09/08/p1.png" }
```

#### POST /api/uploads/finalize-cartoon
Request
```
{ "file_path": "uploads/cartoon/u1/img.png" }
```
Response (200)
```
{ "public_url": "https://storage.googleapis.com/public/cartoon/u1/img.png" }
```

### users

#### GET /api/users/{user_id}
Request (Path)
```
/api/users/{user_id}
```
Response (200)
```
{ "user_id": "...", "nickname": "해피도그", "profile_image_url": null, "post_count": 12 }
```

#### PATCH /api/users/me/profile-image
Request
```
{ "file_path": "uploads/users/u1/profile.png" }
```
Response (200)
```
{ "profile_image_url": "https://storage.googleapis.com/.../users/u1/profile.png" }
```

#### DELETE /api/users/me
Request
```
{}
```
Response (200)
```
{ "message": "Account deleted" }
```

#### GET /api/users/me/notification-preferences
Request
```
{}
```
Response (200)
```
{ "mode": "ALL", "types": { "COMMENT": true, "POST_LIKE": true, "MENTION": true } }
```

#### PATCH /api/users/me/notification-preferences
Request
```
{ "mode": "IN_APP_ONLY", "types": { "COMMENT": true, "POST_LIKE": false, "MENTION": true } }
```
Response (200)
```
{ "mode": "IN_APP_ONLY", "types": { "COMMENT": true, "POST_LIKE": false, "MENTION": true } }
```

#### POST /api/users/me/fcm-token
Request
```
{ "fcm_token": "d7x...:APA91b..." }
```
Response (200)
```
{ "message": "FCM token registered" }
```

#### GET /api/users/{user_id}/summary
Request (Query)
```
?pet_id=pet-uuid
```
Response (200)
```
{ "user": { "user_id": "...", "nickname": "해피도그", "profile_image_url": null, "post_count": 12 }, "pet": { "pet_id": "pet-uuid", "name": "콩이", "age_months": 30 } }
```

#### GET /api/users/me/summary
Request
```
{}
```
Response (200)
```
{ "user": { "user_id": "...", "nickname": "해피도그", "profile_image_url": null }, "selected_pet": { "pet_id": "pet-uuid", "name": "콩이" }, "settings": { "goalWeight": 8.2, "goalMealCount": 2 } }
```

#### GET /api/users/me/selected-pet
Request
```
{}
```
Response (200)
```
{ "pet_id": "pet-uuid", "name": "콩이", "profile_image_url": null, "updated_at": "..." }
```

#### PATCH /api/users/me/selected-pet
Request
```
{ "pet_id": "pet-uuid" }
```
Response (200)
```
{ "pet_id": "pet-uuid" }
```
