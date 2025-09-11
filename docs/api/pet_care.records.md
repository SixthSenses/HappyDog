# pet_care/records API

펫 케어 기록(pet_care/records) 도메인 API 요약입니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/pet-care/{pet_id}/records | jwt_required | 케어 기록 생성(멱등, request_id) | 201, 400, 401, 500 |
| GET | /api/pet-care/{pet_id}/records | jwt_required | 케어 기록 유연 조회(기간/타입/페이징) | 200, 400, 401, 500 |
| GET | /api/pet-care/{pet_id}/records/{record_type} | jwt_required | 특정 타입 기록 조회(페이징) | 200, 400, 401, 500 |
| GET | /api/pet-care/{pet_id}/records/daily | jwt_required | 특정 날짜의 기록을 타입별 배열로 반환 | 200, 400, 401, 500 |
| GET | /api/pet-care/{pet_id}/records/range | jwt_required | 기간 내 기록을 날짜별로 그룹화하여 반환 | 200, 400, 401, 500 |
| PATCH | /api/pet-care/{pet_id}/records/{log_id} | jwt_required | 케어 기록 일부 수정 | 200, 400, 401, 403, 404, 500 |
| DELETE | /api/pet-care/{pet_id}/records/{log_id} | jwt_required | 케어 기록 삭제 | 200, 401, 403, 404, 500 |

## 요청/쿼리/응답 스키마

| 스키마 | 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|---|
| CareRecordCreate | record_type | string(enum: weight|activity|meal|bcs|stool|vomit) | ✔ |  |
|  | timestamp | timestamp(ms) | ✔ | UTC로 변환 저장 |
|  | data | number|object | ✔ | 타입별: weight/activity/meal/bcs=number, stool/vomit=object |
|  | notes | string |  | optional |
|  | request_id | string |  | optional(멱등키) |
| RecordsQuery | date | string(YYYY-MM-DD) |  | date 또는 기간 쿼리 |
|  | start_date/end_date | string(YYYY-MM-DD) |  |  |
|  | record_types | array<string> 또는 string(csv) |  | 최대 10 |
|  | grouped | boolean |  |  |
|  | limit | int(1..100) |  | 기본 50 |
|  | cursor | string |  |  |
|  | include_total | boolean |  | optional |
|  | sort | string(timestamp_asc|timestamp_desc) |  |  |
| Records Response | records[].log_id | UUID | ✔ |  |
|  | records[].pet_id | UUID | ✔ |  |
|  | records[].record_type | string | ✔ |  |
|  | records[].timestamp | timestamp(ms) | ✔ |  |
|  | records[].data | number|object | ✔ |  |
|  | records[].notes | string |  | optional |
|  | records[].searchDate | string(YYYY-MM-DD) | ✔ |  |
|  | meta.limit | int | ✔ |  |
|  | meta.has_more | boolean | ✔ |  |
|  | meta.next_cursor | string |  | optional |
|  | meta.total_count | int |  | optional |
|  | grouped | object |  | optional |

값 제약 및 data 스키마
- 공통: 모든 수치형 입력 값은 음수일 수 없습니다. timestamp는 ms 단위이며, 서버 저장 시 UTC로 변환됩니다.
- record_type별 data 형식: weight/activity/meal/bcs → number, stool/vomit → object

## 오류/예외

| 구분 | 4xx/5xx | 조건 |
|---|---|---|
| POST | 400 VALIDATION_ERROR | 스키마 검증 실패 |
|  | 500 RECORD_CREATION_FAILED | 서버 오류 |
| GET(records) | 400 VALIDATION_ERROR | 스키마 검증 실패 |
|  | 500 FETCH_FAILED | 서버 오류 |
| GET(by type) | 400 INVALID_RECORD_TYPE/VALIDATION_ERROR | 타입 오류/검증 실패 |
|  | 500 FETCH_FAILED | 서버 오류 |
| PATCH | 400 VALIDATION_ERROR | 검증 실패 |
|  | 404 NOT_FOUND | 미존재 |
|  | 403 FORBIDDEN | 권한 없음 |
|  | 500 UPDATE_FAILED | 서버 오류 |
| DELETE | 404 NOT_FOUND | 미존재 |
|  | 403 FORBIDDEN | 권한 없음 |
|  | 500 DELETE_FAILED | 서버 오류 |

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 400 | INVALID_RECORD_TYPE | 지원하지 않는 기록 타입입니다. |
| 400 | MISSING_PARAMETERS/INVALID_DATE_FORMAT | 필수 파라미터 누락 또는 날짜 형식이 올바르지 않습니다. |
| 403 | FORBIDDEN | 이 리소스를 변경할 권한이 없습니다. |
| 404 | NOT_FOUND | 요청한 기록을 찾을 수 없습니다. |
| 500 | FETCH_FAILED/RECORD_CREATION_FAILED/UPDATE_FAILED/DELETE_FAILED | 서버 내부 오류가 발생했습니다. |

## 저장/조회 및 인덱스

| 항목 | 내용 |
|---|---|
| 컬렉션 | pet_care_logs |
| 키 | log_id(request_id 또는 UUID) |
| 필드 | { log_id, pet_id, record_type, timestamp(UTC datetime), searchDate('YYYY-MM-DD'), data, notes } |
| 생성 | DateTimeUtils.from_timestamp_ms → searchDate 생성 → set(merge=True) 멱등 |
| 조회 | pet_id + searchDate eq/range + record_type in(≤10), 정렬/커서 페이징 |
| 인덱스 | (pet_id, searchDate, timestamp) 복합 색인 권장 |

## 목표 달성 알림 (Goal Reached Notification)

| 항목 | 내용 |
|---|---|
| 대상 타입 | activity (분), meal (회) |
| 목표 필드 출처 | `pet_settings.goalActivityMinutes`, `goalMealCount` |
| 달성 조건 | 직전 합계 < 목표 ≤ 신규 합계 (해당 날짜+타입) |
| 중복 방지 | 컬렉션 `pet_care_daily_goal_status` 문서 (ID: `{pet_id}_{YYYY-MM-DD}`) 에 `activity_reached` / `meal_reached` 플래그 트랜잭션 업데이트 |
| 알림 타입 | `PET_CARE_GOAL_REACHED` |
| target_id | `{pet_id}:{YYYY-MM-DD}:{record_type}` |
| target_summary 예 | `활동 목표 30분 달성`, `식사 목표 3회 달성` |
| 메트릭 | `pet_care.goal.reached` (type=activity|meal) |
| 예외 처리 | 설정 없음/목표값 비정상 → 알림 생략 (로그 warning) |

주의: 목표 달성 로직은 현재 V1 create 경로에만 존재하며 업데이트/삭제로 달성 상태가 역전되어도 알림은 회수되지 않습니다(단순 1회 트리거 정책).

### ETag/캐싱
- /daily, /range 엔드포인트는 If-None-Match 헤더를 지원하며 변경이 없으면 304를 반환합니다.
- 커서/타입 필터 없이 조회 시 서버가 ETag 헤더를 설정합니다.
