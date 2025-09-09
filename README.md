# HappyDog Backend 통합 사양 문서 (Pet Care Records & 플랫폼 공통 정책)

본 문서는 Pet Care Records 도메인을 중심으로, 이전 논의에서 합의된 **플랫폼 전반 개선 사양**을 모두 통합/정리한 최종 명세입니다. 구현/리뷰/테스트/클라이언트 연동/운영 관점에서 필요한 세부 사항(헤더, 포맷, 상태, 수식, 마이그레이션 절차, 위험 완화, 버전 정책, 캐시/ETag, 멱등성, 레이트리밋, 에러 카탈로그, 부분 실패, 관찰성, Deprecation 등)을 빠짐없이 포함합니다.

## 목차
1. [용어 및 표기 규칙](#1-용어-및-표기-규칙)
2. [Pet Care Records 도메인 핵심 구조](#2-pet-care-records-도메인-핵심-구조)
3. [신규/분리 API 설계](#3-신규분리-api-설계-레거시-records-복잡성-분해)
4. [Timestamp 정책](#4-timestamp-정책-전역)
5. [Canonical JSON](#5-canonical-json-멱등성-해시)
6. [Idempotency 정책](#6-idempotency-정책)
7. [Rate Limit](#7-rate-limit)
8. [Pagination 계약](#8-pagination-계약-전역)
9. [Partial Failure & 207](#9-partial-failure--207-multi-status)
10. [Error Catalog 정책](#10-error-catalog-정책)
11. [Jobs 상태 머신](#11-jobs-analysis--cartoon-상태-머신)
12. [Dual-write Migration](#12-dual-write-migration-selected_pet-임베드)
13. [Bootstrap API](#13-bootstrap-api-사양)
14. [OpenAPI & Deprecation](#14-openapi-버전--deprecation)
15. [캐시 & ETag 정책](#15-캐시--etag-정책-최종-확정)
16. [Feature Flags](#16-feature-flags)
17. [Observability](#17-observability--모니터링)
18. [Security / Privacy](#18-security--privacy)
19. [헤더 목록](#19-request--response-헤더-목록)
20. [Deprecation 운영 플로우](#20-deprecation-운영-플로우)
21. [테스트 & 품질 게이트](#21-테스트--품질-게이트)
22. [위험 & 상태](#22-위험risk--상태)
23. [실행 순서](#23-실행-순서-phase-1)
24. [예시 응답 & 스니펫](#24-예시-응답--스니펫)
25. [유지 & 거버넌스](#25-유지--거버넌스)
26. [변경 이력](#26-변경-이력-change-log)
27. [요약](#27-요약-executive-summary)
28. [클라이언트 통합 가이드](#28-클라이언트-통합-가이드-android-중심)
29. [클라이언트 타입 매핑](#29-클라이언트-타입-매핑-kotlin-data-classes)
30. [Error → UX 매핑](#30-error-category--ux-매핑-세부)
31. [Idempotent 플로우 예시](#31-idempotent-업로드--job-플로우-예시)
32. [Bootstrap 소비 전략](#32-bootstrap-소비--캐시-전략-앱)
33. [Feature Flags & RC 병행](#33-feature-flags--remote-config-클라이언트-병행)
34. [Observability 상관관계](#34-observability-상관관계)
35. [OpenAPI 스니펫](#35-openapi-스니펫-예시)
36. [마이그레이션 타임라인](#36-마이그레이션-타임라인-텍스트-간트)
37. [품질 점검 Quick Commands](#37-품질-점검-quick-commands-참고)
38. [변경 관리](#38-변경-관리-change-governance)
39. [Frontend TL;DR](#39-한눈-요약-frontend-onboarding-tldr)
40. [추가 명세 & UX 보강](#40-추가-명세--ux-보강)

---
## 1. 용어 및 표기 규칙

| 구분 | 설명 |
|------|------|
| UTC | 모든 서버 저장/출력 시간 기준 (tz-aware). |
| ISO8601 | `YYYY-MM-DDTHH:mm:ss.SSSZ` (밀리초 3자리 고정) |
| epoch_ms | Unix epoch milliseconds (정수). High-frequency 타임라인 전용 필드. |
| searchDate | `YYYY-MM-DD` (UTC 파생 날짜 키) |
| record_type | `weight|water|activity|meal|bcs` |
| Bootstrap | 앱 초기 구동 시 단일 호출로 핵심 상태를 제공하는 API 응답 구조. |
| Canonical JSON | 멱등성 해시 계산용 정규화 직렬화 규칙. |

---
## 2. Pet Care Records 도메인 핵심 구조

### 2.1 컬렉션 & 문서 구조
- 컬렉션: `pet_care_logs`
- 문서 ID: `log_id` (UUID 혹은 request_id 기반 멱등 upsert)
- 필드:
    - `log_id` (string, UUID)
    - `pet_id` (string, UUID)
    - `record_type` (enum)
    - `timestamp` (Firestore Timestamp, UTC)
    - `timestamp_ms` (선택 저장/응답 시 변환 가능)
    - `searchDate` (YYYY-MM-DD)
    - `data` (object) – 타입별 스키마
    - `notes` (string?)
    - (미래 확장) `goal_snapshot` (weight 등 목표 계산 시 사용 가능한 선택적 필드)

### 2.2 타입별 `data` 예시(간략)
| record_type | data 예시 |
|-------------|-----------|
| weight | `{ "value": 7.8 }` |
| water | `{ "amount_ml": 250 }` |
| activity | `{ "minutes": 25 }` |
| meal | `{}` *(현재 추가 속성 비활성)* |
| bcs | `{ "score": 5 }` |

### 2.3 인덱스 권장
1. `(pet_id, searchDate, timestamp)` – 날짜 범위 + 정렬
2. `(pet_id, record_type, searchDate, timestamp)` (선택) – 타입 필터 빈도 높을 시

### 2.4 레코드 생성/수정/삭제 공통 처리
- 입력 timestamp(ms) → UTC datetime → Firestore Timestamp 저장 + `searchDate` 파생.
- 수정 시 timestamp 변경 → 날짜 경계 변경 가능 → 응답에 `affected_dates` 배열 반환 (이전/이후 날짜 모두 포함).
- 삭제 시 동일하게 `affected_dates=[searchDate]`.

---
## 3. 신규/분리 API 설계 (레거시 `/records` 복잡성 분해)

| Endpoint | 설명 | 비고 |
|----------|------|------|
| `POST /api/pet-care/{pet_id}/records` | 기록 생성(멱등: request_id) | 201 / 200 (upsert) |
| `PATCH /api/pet-care/{pet_id}/records/{log_id}` | 부분 수정 | `affected_dates` 포함 |
| `DELETE /api/pet-care/{pet_id}/records/{log_id}` | 삭제 | idempotent 허용 |
| `GET /api/pet-care/{pet_id}/records/daily?date=YYYY-MM-DD` | 하루 묶음 조회(그룹: weight, water, activity, meal, bcs) | 그룹별 배열 |
| `GET /api/pet-care/{pet_id}/records/range?start=...&end=...&types=meal,water` | 기간 + 타입 필터 | 최대 31일 제한 |
| `GET /api/pet-care/{pet_id}/summary?date=YYYY-MM-DD` | 진행도 요약 | 캐시 30s |
| `GET /api/pet-care/{pet_id}/records/legacy` | Deprecated (Announce 단계) | Deprecation 헤더 |

### 3.1 공통 Pagination 메타 (range)
```
{
    "data": [ { ...record... } ],
    "meta": {
        "limit": 50,
        "next_cursor": "<doc_id>" | null,
        "has_more": true|false,
        "total": 123   // 조건부
    }
}
```
**규칙**: `total` 은 (a) `include_total=true` & `limit ≤ 200` & 예상 총량 threshold 미초과 시 계산. 조건 미충족 시 필드 자체 **생략**(null 금지).

### 3.2 daily 응답 예시
```
{
    "data": {
        "pet_id": "...",
        "date": "2025-09-09",
        "weight": [ { log_id, timestamp_ms, data } ],
        "water": [ ... ],
        "activity": [ ... ],
        "meal": [ ... ],
        "bcs": [ ... ]
    },
    "meta": { "limit": 100 }
}
```

### 3.3 summary 수식 & 응답
```
GET /api/pet-care/{pet_id}/summary?date=YYYY-MM-DD
{
    "data": {
        "pet_id": "...",
        "date": "2025-09-09",
        "weight_latest": { "value": 7.8, "timestamp": "2025-09-09T04:10:00.123Z" } | null,
        "water_intake_total": 520,
        "meal_count": 3,
        "activity_minutes": 54,
        "goals": {
            "water_ml": 600,
            "meal_count": 3,
            "activity_minutes": 60,
            "weight_goal": 8.2
        },
        "progress_percent": {
            "water_ml": 86.7,
            "meal_count": 100.0,
            "activity_minutes": 90.0
        },
        "updated_at": "2025-09-09T05:00:10.000Z"
    }
}
```
> Meal 관련 size / calories 필드가 비활성 상태이므로 `meal_count` 는 **해당 날짜의 meal 타입 레코드 개수**만을 의미합니다 (데이터 오브젝트 내용과 무관).

#### 3.3.1 Progress 계산 수식
| 항목 | 분자 | 분모(goal) | 수식 | 0 분모 처리 | Cap | 반올림 |
|------|------|-----------|------|------------|-----|--------|
| water_ml | water 합 | goal.water_ml | `(sum/goal)*100` | 0.0 | 100 | 소수 1자리 |
| meal_count | meal 개수 | goal.meal_count | `(count/goal)*100` | 0.0 | 100 | 1자리 |
| activity_minutes | 합 | goal.activity_minutes | `(sum/goal)*100` | 0.0 | 100 | 1자리 |
| weight_delta_pct (선택) | latest - goal | goal | `((latest/goal)-1)*100` | goal=0 → null | X | 1자리 |

**분모=0** → progress=0.0. Cap=100.0(초과 시). Rounding: Python round(value,1).

### 3.4 변경/삭제 응답 (affected_dates)
```
{
    "data": { ...updated_record... },
    "affected_dates": ["2025-09-09", "2025-09-10"]
}
```

### 3.5 단위 & 검증 규칙 (Units & Validation)
| 필드 경로 | 단위 / 범위 | 검증 실패 error_code |
|-----------|-------------|----------------------|
| weight.value | kg ( >0 ) | VALIDATION_ERROR (details.weight) |
| water.amount_ml | ml ( >0 ) | VALIDATION_ERROR (details.water_amount_ml) |
| activity.minutes | 분 (0..1440) | VALIDATION_ERROR (details.activity_minutes) |
<!-- 비활성 필드는 별도 3.5.3 참조 -->
| bcs.score | 정수 1..5 (프로젝트 규약) | VALIDATION_ERROR (details.bcs_score) |
| goals.water_ml | ml ( ≥0 ) | VALIDATION_ERROR |
| goals.activity_minutes | 분 ( ≥0 ) | VALIDATION_ERROR |
| goals.meal_count | 회 ( ≥0 ) | VALIDATION_ERROR |
| goals.weight_goal | kg (>0) or null | VALIDATION_ERROR |
| weight_delta_pct | % (부호 있음) | 계산 파생(입력 아님) |

weight_delta_pct 부호 규칙: +값 = 현재 체중이 목표보다 무거움(과체중 경고 색상), -값 = 목표보다 가벼움.

정밀도 & 반올림:
- weight.value, goals.weight_goal: 최대 소수 2자리 저장 (입력 더 길면 HALF_EVEN(은행가 반올림)으로 2자리).
- progress_percent 계산: Python round(value,1) (HALF_EVEN) → UI 표시 그대로 사용.
- meal.calories 정수, water.amount_ml 정수, activity.minutes 정수.

### 3.5.1 BCS Score 의미
| 점수 | 상태 | 설명(요약) |
|------|------|-----------|
| 1 | 매우 마름 | 늑골/골격 과도 노출 |
| 2 | 마름 | 늑골 쉽게 만져짐, 피하지방 적음 |
| 3 | 이상적 | 늑골 촉지 가능, 허리 라인 명확 |
| 4 | 과체중 | 허리 덜 뚜렷, 지방 축적 시작 |
| 5 | 비만 | 허리 없음, 지방 두껍게 축적 |

### 3.5.2 Meal Size / kcal 비활성화 (요약)
Meal 관련 size, calories 필드는 현재 버전에서 비활성화되었습니다. 기존 저장 데이터는 응답에서 제거(또는 무시)되며 재도입 시 본 섹션 & Validation & Change Log 동시 갱신.

### 3.5.3 Meal 비활성 필드 정책 (상세)
| 항목 | 상태 | 재도입 조건 | 재도입 시 영향 |
|------|------|-------------|----------------|
| meal.size | 비활성 | 사이즈 정의(표준 g 범위) 합의 & 클라 UX 반영 | `bootstrap_version` Minor (필드 추가) |
| meal.calories | 비활성 | 캘로리 산출/입력 UX, 단위(kcal) 명확화 | `bootstrap_version` Minor, summary formula 변경 시 Major 검토 |

정책:
1) 비활성 기간 동안 클라이언트는 meal `data` 객체 내용을 신뢰하지 않고 단순 count 로직만 사용.
2) 활성화 PR 은 라벨 `meal-field-reactivation` 부착 + 본 표/3.3, 3.5 테이블/Change Log 업데이트 필수.
3) 만약 활성화 시 progress 확장(예: 칼로리 진행률) 도입은 별도 `progress_percent.calories` 필드 추가(Backward compatible) 로 처리.

### 3.6 삭제(Delete) 연산 표준
- DELETE 성공(존재 or 이미 삭제된 경우) → 200 `{ "data": { ...record_before? } , "affected_dates": [ ... ] }` 또는 존재하지 않아도 idempotent 보장 위해 `{ "data": null }` + `affected_dates` 생략.
- 204 No Content 사용하지 않음 (Envelope 일관성 유지).

### 3.7 Timestamp Clock Skew 허용
- 클라이언트 제공 timestamp_ms 허용 편차: 서버 현재 시간 기준 ±300초 초과 시 `VALIDATION_ERROR` (`details.timestamp_skew=true`).
- 허용 범위 내면 그대로 수용; 경계 근처(±250초 이상)는 WARN 레벨 로그.

---
## 4. Timestamp 정책 (전역)

| 범주 | 형식 | 정밀도 | 비고 |
|------|------|--------|------|
| 대부분(게시글/알림/Job 등) | ISO8601(Z) | ms(3자리) | tz-aware UTC |
| High-frequency 목록 (pet care records) | `timestamp_ms` (int) + 선택 ISO | ms | JSON 내 int |
| searchDate | YYYY-MM-DD | day | UTC 파생 키 |
| job terminal_at | ISO8601(Z) | ms | Terminal only |

**Freeze(계속 ms 유지) 필드 목록**: `pet_care.records.timestamp_ms`, `notifications.created_at_ms? (옵션)`, `analysis_jobs.created_at_ms (옵션)`.

---
## 5. Canonical JSON (멱등성 해시)

| 규칙 | 상세 |
|------|------|
| 키 정렬 | 사전순 | 
| 공백 제거 | 인라인(compact) |
| float | 정수 값이면 소수 제거 (1.0→1). 예외 필드: `PRESERVE_DECIMAL_FIELDS={"weight_goal","probability"}` → 최소 한 자리 유지 |
| boolean/null | 소문자(JSON 표준) |
| 숫자 범위 | 53bit 초과 위험 값은 문자열로 전달 (ID 류는 문자열 유지) |
| 해시 범위 | Body 만. Query 미포함 (POST with query 회피 권장) |
| 인코딩 | UTF-8 |
| 출력 | SHA256(hex) |

멱등 불일치: 동일 `X-Idempotency-Key` + 상이한 `request_hash` → `409 CONFLICT` (`error_code=IDEMPOTENCY_KEY_MISMATCH`).

### 5.1 예외 필드 목록 갱신 절차
- 새로운 float 필드가 “소수 한 자리 고정 표현” 필요 시 `PRESERVE_DECIMAL_FIELDS` 상수 & 본 섹션 테이블 동시 업데이트.
- PR 라벨 `canonical-json-change` 추가 + canonical_json_test 케이스 1건 추가.

### 5.2 Canonical 직렬화 샘플
| 원본 Body(JSON pretty) | Canonical String | SHA256(hex) |
|------------------------|------------------|-------------|
| `{"\n  \"b\":2,\n  \"a\":1.0\n}` | `{"a":1,"b":2}` | ecb669c08557ad0806258e68ec5251379217985b0c93a29c59c3701e6e24a04b |
| `{ "weight_goal": 7.0, "probability": 0.50 }` | `{"probability":0.5,"weight_goal":7.0}` | a5bd446299b13ebb55a495d95119fdeb990e6c578dbb5260e122488ebc3fb83a |
| `{ "nested": { "z":1, "a":2.0 } }` | `{"nested":{"a":2,"z":1}}` | ca38bac0e5f3953ec9c7f6b6b3f0413ca7c4664c53d66e8307d3dbca06a4afce |

*SHA256 값은 테스트 고정 expected 값으로 사용 (drift 감지용).*

---
## 6. Idempotency 정책

| 적용 | Endpoint | 비고 |
|------|----------|------|
| Job 생성 | `POST /api/analysis` | 타입 nose/eye 통합 |
| Upload finalize(bulk) | `POST /api/uploads/finalize` | 파일 다중 |

저장 문서: `idempotency_keys/{key}` → `{ key, op_type, request_hash, status_code, response_body, created_at }` (TTL=24h). 재생 시:
- 상태코드 & Body 동일.
- 헤더: `Idempotent-Replay: true` / `X-Request-Id` 새 값 / `Date` 새 값.
- 보존 만료 GC Job.
- TTL 경과(>24h) 후 동일 key 재사용 시: **새 요청으로 처리** (기존 해시/응답 매칭 없음).

---
## 7. Rate Limit

| 항목 | 규칙 |
|------|------|
| 윈도우 | Fixed 60s |
| 수준 우선순위 | per-user > per-IP(비인증) > global |
| 헤더 | X-RateLimit-Limit / Remaining / Reset (epoch seconds) |
| 401/403 | 카운트 소비 (보안 brute-force 감시) |
| 초과 응답 | 429 + Retry-After(정수 초) + category=RATE_LIMIT |
| 모니터 | `rate_limit_hits`, `auth_fail_rate` |

---
## 8. Pagination 계약 (전역)

| 파라미터 | 설명 | 기본/최대 |
|----------|------|-----------|
| limit | 페이지 크기 | default=20, max=100 (include_total시 계산 범위 내) |
| cursor | 이전 응답 `next_cursor` | - |
| include_total | true/false(“1”/“true” 허용) | total 조건부 |

메타 규칙:
- `next_cursor` 없으면 `null`.
- `has_more` = `next_cursor != null`.
- `total` 조건 미충족 시 **필드 제거(omit)**.

---
## 9. Partial Failure & 207 Multi-Status

| 항목 | 규칙 |
|------|------|
| 기본 | HTTP 200 + `meta.partial_failures` |
| Opt-in | `?accept_multi_status=true` OR 헤더 `X-Client-Capabilities: multi-status` → 207 |
| data 비어도 | `partial_failures` 존재 시 성공 처리 |
| 구조 | `partial_failures:[{file_path,error_code,message,retriable}]` |
| 재시도 allowlist | NETWORK_ERROR, TRANSIENT_STORAGE_ERROR, RATE_LIMIT_EXCEEDED |

---
## 10. Error Catalog 정책

| 필드 | 설명 |
|------|------|
| error_code | `DOMAIN_ACTION_OUTCOME` 패턴 (예: PET_CARE_RECORD_CREATION_FAILED) |
| category | VALIDATION / AUTH / PERMISSION / NOT_FOUND / CONFLICT / RATE_LIMIT / INTERNAL / DEPRECATION |
| http_status | 숫자 코드 |
| retriable | True/False 규칙 기반 |
| details | snake_case 키 사용 |

`NON_RETRYABLE` 예시: VALIDATION_ERROR, IMAGE_CORRUPT, PET_NOT_FOUND, PERMISSION_FORBIDDEN. 5xx 중 일부(네트워크/내부)만 retriable.

재시도 판정 공식 (최종):
```
retriable = (
    category ∈ { RATE_LIMIT, INTERNAL } OR http_status ∈ {408,500,502,503,504}
) AND error_code NOT IN NON_RETRYABLE_OVERRIDE
```
NON_RETRYABLE 목록 변경 시 CI가 diff 감지 → PR 라벨 `error-catalog-change` 요구.

자동 생성: Pytest 마커 → `error_samples.json` → OpenAPI `x-error-samples` 참조. CI: 누락/중복 FAIL.

---
## 11. Jobs (Analysis / Cartoon) 상태 머신

```
queued → processing → success
                                 ↘ → failed (retry_count<5 & retryable → queued)
queued|processing → canceled
```
불변식:
- Terminal(success/failed/canceled) 후 변이 금지
- terminal_at 설정 = state ∈ terminal
- failed & retryable: backoff = `min(2^retry_count * 5s, 120s)`
- retry_count 최대 5
- success: result 존재 & error_message 없음
- failed: error_message 필수 & result 없음

---
## 12. Dual-write Migration (selected_pet 임베드)

| 단계 | 설명 | 게이트 |
|------|------|--------|
| 0 | users.selected_pet 스키마 추가 | 배포 성공 |
| 1 | Dual-write ON | 실패율 <0.1% |
| 2 | Read 우선순위: users.selected_pet 우선 | Bootstrap 98% 채움 |
| 3 | Backfill + Validator (diff=0) | 누락율 <0.5% |
| 4 | Legacy 읽기 제거 | 48h 안정 |
| 5 | Legacy 쓰기 제거 | 실패 0.1% 이내 |
| 6 | 컬렉션 삭제 | 아카이브 해시 검증 |

Dead-letter: `dual_write_failures` { attempt_count, last_error_code, closed, resolution }. closed 조건:
- 재처리 성공 OR 수동 triage(`resolution=MANUAL_IGNORE`). 보존 14일 GC.

---
## 13. Bootstrap API 사양

Endpoint: `GET /api/app/bootstrap`

섹션 & TTL:
| 섹션 | TTL | Fallback |
|------|-----|----------|
| user | 즉시 | 오류 시 전체 500 |
| selected_pet | 즉시 | null |
| pet_settings | 30s | null |
| today_summary | 30s | 0값 구조 |
| notifications_recent | 15s (soft) | 빈 배열 |
| unread_count | 15s | 0 |
| static_config | 5m | `{}` |
| feature_flags | 30s | 모든 flag false |
| server_time | 즉시 | now() |

버전 필드:
```
bootstrap_version: "1"
static_config.schema_version: 1
feature_flags.schema_version: 1
```
변경 매트릭스:
| 변경 | bootstrap_version | section schema_version |
|------|-------------------|------------------------|
| 필드 추가(비파괴) | Minor | (선택) |
| 필드 제거 | Major | Major |
| 의미 변경 | Major | Major |
| rounding 등 비의미 변경 | Minor | No |

Schema mismatch: 서버 > 클라 지원 → 미지원 섹션 null 처리 (graceful degrade) 에러 반환 없음.

---
## 14. OpenAPI 버전 & Deprecation

OpenAPI:
- `info.version`: SemVer (예: 1.4.0)
- `x-api-version`: 연월 빌드 (예: 2025.09.1)
- `x-deprecated`: 목록 [{ path, replacement, sunset }]

Deprecation 헤더:
| 단계 | 헤더 | 바디 |
|------|------|------|
| Announce | `Deprecation: true`, `X-Sunset`, `X-Replacement` | 기존 응답 |
| Soft Block | + `Warning` 헤더 | 기존 응답 |
| Hard Removal | 410 | 표준 에러 바디 |

410 바디:
```
{
    "error_code": "ENDPOINT_REMOVED",
    "category": "DEPRECATION",
    "message": "This endpoint was removed after the announced sunset date.",
    "details": { "replacement": "/api/..." }
}
```

---
## 15. 캐시 & ETag 정책 (최종 확정)

| 리소스 | ETag | Cache-Control | 비고 |
|--------|------|---------------|------|
| /api/config/static (static_config) | Yes | public, max-age=60, stale-while-revalidate=240 | 변경 적음 |
| feature_flags (개별 fetch 또는 Bootstrap 내 재검증) | Yes | public, max-age=60, stale-while-revalidate=240 | rollout 빈도 대응 |
| Bootstrap (전체 조합) | No | no-store (또는 max-age=0) | 동적, 향후 재평가 |

클라이언트 지침:
- ETag 일치 → 304 처리, 기존 캐시 즉시 사용.
- stale-while-revalidate 윈도우(최대 240초) 동안 백그라운드 재검증 허용.
- 강제 새로고침 시 `If-None-Match` 우선.

---
## 16. Feature Flags

| 필드 | 설명 |
|------|------|
| key | 케밥 혹은 snake (문서 통일) |
| type | boolean / ratio / enum |
| value | 현재 값 |
| rollout | `{ ratio?:0..1, conditions?:[{attribute,op,value}] }` |
| updated_at | ISO8601 |

분포: hash(seed=`"happydog-flag-seed-v1"`, user_id) % 100 < ratio*100. χ² 분포 검증: 주 1회 p-value > 0.05.
Cleanup: disabled 14일 + code ref 탐색 0건 → 제거.

클라이언트 캐시 TTL: 30s, stale 재검증 허용. (클라이언트 병행 전략은 33절 참조)

#### 16.1 enum 타입 예시
```
"analysis_mode": {
    "type": "enum",
    "value": "fast",
    "allowed": ["fast","accurate"]
}
```

---
## 17. Observability & 모니터링

로그 표준(snake_case): `request_id, user_id, route, latency_ms, error_code, category, http_status`.

SLO / Alert (최종 확정):
| 지표 | 목표 | Alert 조건 |
|------|------|-------------|
| bootstrap p95 | <450ms | >700ms 15분 지속 |
| posts list p95 | <300ms | >600ms 10분 지속 |
| dual_write_failure_rate | <0.1% | >0.3% (5분 2회) |
| rate_limit_hits spike | 정상 추세 대비 | +300% 10분 |
| job_retry_attempts | <5 평균 | >10 (5분) |
| overall p99 | <1200ms | >1200ms 5분 지속 |
| idempotent_replay_count | 모니터링 | 급증(기준 대비 +200%) 10분 |
| sse_connected_clients (Phase2) | - | 비정상 급감(>50%) |

Note: p99 임계 1500ms → 1200ms, 지속 시간 10분 → 5분으로 조정 (신규 정책 반영).

Audit Event: `{ event_id, at, actor_id, resource_type, resource_id, action, before?, after?, request_id }` – before/after whitelist 키만 포함.

Redaction 로그 예:
```
{ "event":"notification_redacted", "template_id":"unknown", "original_hash":"sha256:ab12...", "reason":"UNAPPROVED_TEMPLATE", "request_id":"..." }
```

---
## 18. Security / Privacy

| 항목 | 정책 |
|------|------|
| Notification free-text | Allowlist 실패 시 message="[redacted]" |
| Bootstrap 민감 정보 | email 제외, 내부 시스템 ID 제외(faiss_id) |
| Audit diff | 허용 키만 저장(PHI/PII 제한) |

Redaction 문자열 Locale 영향 없음(고정).

---
## 19. Request / Response 헤더 목록

| 헤더 | 방향 | 설명 |
|------|------|------|
| X-Request-Id | In/Out | 없으면 서버 UUID(v7 또는 ULID) 생성 |
| X-Idempotency-Key | In | 멱등 연산 전용(선택) |
| Idempotent-Replay | Out | true 재생 응답 |
| X-RateLimit-Limit | Out | 윈도우 허용량 |
| X-RateLimit-Remaining | Out | 남은 횟수 |
| X-RateLimit-Reset | Out | epoch sec 윈도우 종료 |
| Retry-After | Out | 429 재시도(정수 초) |
| Deprecation | Out | true (Deprecated) |
| X-Sunset | Out | ISO8601 또는 날짜 |
| X-Replacement | Out | 대체 엔드포인트 |
| ETag | Out | 정적/캐시 가능 리소스 |
| Cache-Control | Out | 캐시 정책 |
| X-Client-Capabilities | In | 기능/옵션 토큰 목록 |

`X-Client-Capabilities` 정규식: `^[a-z0-9_:-]+(,[a-z0-9_:-]+)*$`

예시:
```
X-Client-Capabilities: multi-status,bootstrap-v1,flags-v1
```
설명:
- multi-status: 207 Multi-Status opt-in
- bootstrap-v1: bootstrap schema v1 지원
- flags-v1: feature flags schema v1 지원

---
## 20. Deprecation 운영 플로우

| 단계 | 기간(예시) | 자동/수동 | 측정 |
|------|-----------|-----------|------|
| Announce | ≥30d | 수동 시작 | 호출량 baseline |
| Soft Block | 14d | 자동(sunset-14d) | 경고 응답 비율 |
| Pre-Hard | 7d | 자동 + 승인 | 호출량 감소율(≥80%) |
| Hard (410) | - | 수동 플래그 | 에러 모니터링 |

Hard 이후 410 에러 표준 바디 사용.

---
## 21. 테스트 & 품질 게이트

| 테스트 | 목적 |
|--------|------|
| canonical_json_test | 해시 안정성/float 규칙 검증 |
| feature_flag_distribution_test | χ² 분포 균일성 |
| dual_write_dead_letter_retry_test | 재처리 및 closed 전환 |
| deprecation_410_contract_test | Hard 제거 바디 규격 |
| pagination_no_total_when_limit_gt_200 | total omit 규칙 |
| race_pet_register_bootstrap | selected_pet 레이스 0 관측 |
| care_summary_formula_test | 0분모 / rounding / cap |
| partial_failure_retries_test | allowlist 재시도 로직 |
| error_samples_extraction | catalog 생성 및 OpenAPI 참조 |
| chaos_latency_injection | 300ms 지연 시 p95 변동 모니터 |
| range_limit_boundary_test | 31일 OK / 32일 400 확인 |
| idempotent_ttl_expire_test | 24h 경과 후 동일 본문 새 처리 |
| preserve_decimal_fields_change_test | 목록 변경 시 CI fail 검증 |
| partial_failure_retry_cap_test | 3회 초과 중단 로직 |

검증 목표: Race 1000 시도 중 0 관측(문구: "0 observed in N=1000; target ≤0.1%").

CI 실패 조건:
- error_samples 누락/불일치
- canonical hash drift
- schema_version 증가 미문서화 (라벨/PR 체크)

---
## 22. 위험(Risk) & 상태

| 등급 | 항목 | 대응 |
|------|------|------|
| RED | Canonical float 모호성 | 예외 필드 + 문서 확정 (해소) |
| AMBER | Retry backoff 구체화 | 5회 / 지수 / 상한 120s (해소) |
| AMBER | 410 응답 바디 | 표준 포맷 문서화 (해소) |
| GREEN | 나머지 | 모니터 기반 지속 개선 |
| INFO | χ² 표본 부족(n<1000) | 분포 테스트 skip 규칙 적용 |

---
## 23. 실행 순서 (Phase 1)

1. Middleware: request_id, rate_limit, idempotency 구현
2. users.selected_pet dual-write 적용
3. Bootstrap v1 골격 + fallback
4. Pagination/Envelope 표준화 리팩터
5. Error category + catalog + extractor
6. OpenAPI 태그 & deprecated 헤더 반영
7. Backfill + Validator 동작
8. 모니터링 대시보드 & 알람 구성
9. 문서 커밋 & SemVer 태깅

Go/No-Go 체크리스트(추가 항목 포함) 모두 YES 시 배포.

---
## 24. 예시 응답 & 스니펫

### 24.1 기록 생성 성공
```
POST /api/pet-care/{pet_id}/records
201 { "data": { log_id, pet_id, record_type, timestamp_ms, searchDate, data }, "affected_dates": ["2025-09-09"] }
```

### 24.2 부분 실패 finalize (기본 200)
```
{
    "data": [ { "file_path":"a.jpg", "public_url":"..." } ],
    "meta": {
        "partial_failures": [ { "file_path":"b.jpg", "error_code":"FILE_NOT_FOUND", "message":"...", "retriable":false } ]
    }
}
```

### 24.3 Idempotent 재생
헤더: `Idempotent-Replay: true` 본문 동일.

---
## 25. 유지 & 거버넌스

| 주기 | 작업 |
|------|------|
| 일간 | idempotency GC / dual_write_failures 재시도 |
| 주간 | feature flag χ² / deprecated 사용 보고 |
| 분기 | 인덱스 성능 점검 / error code drift 리뷰 |

---
## 26. 변경 이력 (Change Log)
| 버전 | 날짜 | 내용 |
|------|------|------|
| 1.0.0 | 2025-09-09 | 초기 통합 문서 작성 (본 파일) |
| 1.0.1 | 2025-09-09 | 번호 재정렬(14.a→15), Units/Validation(3.5), Delete 표준(3.6), Clock Skew(3.7), Canonical 샘플(5.2), enum flag 예시(16.1), 추가 위험/테스트 보강 |
| 1.0.2 | 2025-09-09 | 섹션 24 하위 번호 수정, BCS/Meal 의미 추가(3.5.1/3.5.2), Clock Skew 로그 레벨, Canonical 해시 전체값, 추가 테스트/메트릭/거버넌스 행, TTL 만료 처리 명시 |
| 1.0.3 | 2025-09-09 | Meal size & kcal 비활성화(3.5/3.5.2), 관련 검증/테스트 제거, TOC 추가, OpenAPI 스니펫 들여쓰기 정규화 |
| 1.0.4 | 2025-09-09 | Meal 비활성 정책 세분화(3.5.3), meal_count 계산 명시(3.3), 비활성 필드 메인 Validation 표 분리, 클라이언트 섹션 번호 정규화 준비 |
| 1.0.5 | 2025-09-09 | weight_latest/bcs_latest 표준 객체 `{ value,timestamp_ms }` (기존 timestamp ISO → ISO 유지 + ms 병행), Clock Skew WARN 밴드(±250~300s) 로깅, Idempotency 다른 본문 재사용 409 `IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY`, ETag 확장(daily/range/summary range) + mutation 기반 invalidation, summary range 캐시/ETag 문서화 |
| 1.0.6 | 2025-09-09 | include_total 게이팅(limit≤50 & has_more=false & total≤5000) 구현, grouped=true Deprecation 헤더(announce), ETag hit/miss 메트릭 스텁, Pagination cross-page 테스트 추가, /health metrics 노출, RateLimit exceeded/requests 메트릭 추가, ETag 캐시 키 ordering 명시 |

---
## 27. 요약 (Executive Summary)
- 초기 진입: Bootstrap 1콜 → 네트워크/레이턴시 최적화.
- 데이터 일관성: selected_pet 임베드 + dual-write 마이그레이션 안전장치.
- 신뢰성: 멱등성/레이트리밋/재시도/Dead-letter/분포 테스트.
- 성능: 캐시 TTL + stale-while-revalidate + ms 필드 제한.
- 유지보수: OpenAPI 버전 태깅 + Deprecation 단계화 + Error Catalog 자동화.
- 관찰성: p95/p99, 실패율, 재시도 추적.

---
문의/업데이트 절차: 변경 제안 시 PR에 **spec-impact** 라벨 부착 + 관련 섹션 수정 → 리뷰어(Backend Lead + Client Lead) 동시 승인 필요.

---
## 28. 클라이언트 통합 가이드 (Android 중심)

### 28.1 공용 헤더 주입 규칙
| 헤더 | 주입 시점 | 값 소스 |
|------|-----------|---------|
| Authorization | 모든 인증 필요 호출 | AccessToken (만료 시 토큰 리프레시 후 재시도 1회) |
| X-Request-Id (선택) | 중요 추적(업로드/결제 등) | UUIDv7 생성 │ 없으면 서버 생성 |
| X-Idempotency-Key | 멱등 필요(Uploads finalize, Analysis) | UUIDv4 (호출 컨텍스트별 재사용) |
| X-Client-Capabilities | 앱 초기 + 조건부 | `multi-status,bootstrap-v1,flags-v1` (보유 기능) |

### 28.2 SafeApi → AppResult 매핑
| 서버 category | HTTP 예 | 클라이언트 AppResult | 기본 UX |
|---------------|---------|----------------------|---------|
| VALIDATION | 400 | Error.Validation | 입력 강조 + 스낵바 |
| AUTH | 401 | Error.Auth | 재로그인 유도 (토큰 재시도 실패 후) |
| PERMISSION | 403 | Error.Permission | 다이얼로그(권한 없음) |
| NOT_FOUND | 404 | Error.NotFound | 토스트/빈 상태 전환 |
| CONFLICT | 409 | Error.Conflict | 스낵바 재시도 │ 필드 리프레시 |
| RATE_LIMIT | 429 | Error.RateLimited(retryAfter) | 지수 백오프 재시도 큐 |
| INTERNAL | 5xx | Error.Server | 글로벌 에러 리포터/재시도 큐 |
| DEPRECATION | 410 | Error.Deprecated | 앱 업데이트 CTA |

### 28.3 Pagination 소비 패턴(Paging3 의사코드)
```
val pager = Pager(
    config = PagingConfig(pageSize = limit, enablePlaceholders=false),
    pagingSourceFactory = { RecordsPagingSource(api) }
)

class RecordsPagingSource : PagingSource<String, Record>() {
    override suspend fun load(params: LoadParams<String>): LoadResult<String, Record> {
        val res = api.getRange(cursor=params.key, limit=params.loadSize, includeTotal=false)
        return LoadResult.Page(
            data = res.data,
            prevKey = null,
            nextKey = res.meta.next_cursor
        )
    }
}
```
주의: `total` 필드 존재 여부 확인(Omit 처리) → null 아님을 기준으로 분기.

### 28.4 Retry / Backoff (클라이언트)
Exponential + Jitter:
```
base = 1000ms
attempt n delay = min(base * 2^n, 8000ms) * random(0.9..1.1)
abort if category !∈ {RATE_LIMIT, INTERNAL} && !retriable
```

### 28.5 Idempotency 키 클라이언트 전략
- 업로드 finalize: 동일 세트 재시도(네트워크 오류) 시 이전 키 재사용 → 재생 여부 헤더 관찰.
- Job 생성: 화면 단위 캐시(Map<temporaryRequestId, key>) 24h 내 재전송 시 키 유지.

### 28.6 Offline / Queue
| 작업 | 전략 |
|------|------|
| 케어 기록 생성 | 로컬 pending DB → 성공 시 서버 log_id 반영 후 제거 |
| 업로드 finalize | 실패 partial_failures subset 재시도 리스트 shrink |
| Notifications ack | 배치 큐 - 실패 시 백오프 재삽입 |

---
## 29. 클라이언트 타입 매핑 (Kotlin Data Classes)
```
data class Bootstrap(
    val user: User?,
    val selectedPet: PetLite?,
    val petSettings: PetSettings?,
    val todaySummary: TodaySummary?,
    val notificationsRecent: List<Notification>,
    val unreadCount: Int,
    val staticConfig: StaticConfig,
    val featureFlags: Map<String, Any>,
    val serverTime: Instant,
    val bootstrapVersion: String,
    val staticConfigSchemaVersion: Int,
    val featureFlagsSchemaVersion: Int
)

data class TodaySummary(
    val petId: String,
    val date: LocalDate,
    val weightLatest: WeightPoint?,
    val waterIntakeTotal: Int,
    val mealCount: Int,
    val activityMinutes: Int,
    val goals: Goals,
    val progressPercent: Progress,
    val updatedAt: Instant
)
```
주의: `total` 필드 존재하지 않을 수 있으므로 Optional.

---
## 30. Error Category → UX 매핑 세부
| 카테고리 | 사용자 메시지 톤 | 재시도 자동? | 로깅 레벨 |
|----------|------------------|--------------|-----------|
| VALIDATION | 구체적 필드 안내 | X | Info |
| AUTH | 세션 만료 안내 | 토큰 재발급 1회 | Warn |
| PERMISSION | 권한 부족 | X | Warn |
| NOT_FOUND | 리소스 없음 | X | Info |
| CONFLICT | 동시 수정 | O(한 번) | Warn |
| RATE_LIMIT | 서버 과부하 | O(백오프) | Warn |
| INTERNAL | 일시적 오류 | O(백오프) | Error |
| DEPRECATION | 기능 종료 | X (업데이트 CTA) | Info |

---
## 31. Idempotent 업로드 & Job 플로우 예시
시나리오(업로드 finalize):
1) 파일 업로드 성공 후 finalize 호출 (X-Idempotency-Key K1)
2) 네트워크 타임아웃 발생 → 동일 K1 재호출
3) 서버 재생 → 200 + `Idempotent-Replay: true`
4) 클라이언트 Telemetry: `idempotent_replay` 이벤트 전송

Job 플로우:
```
createJob(key=K2) → queued
poll until (success|failed|timeout)
if failed & retriable & attempt<3 → 지수 백오프 후 createJob 재호출 (동일 key 유지 금지) → 새 key (K3)
```

---
## 32. Bootstrap 소비 & 캐시 전략 (앱)
| 요소 | 저장소 | 만료 | 정책 |
|------|--------|------|------|
| user/selectedPet | In-Memory + Disk(DataStore) | 세션 | ETag 비교 후 업데이트 |
| todaySummary | In-Memory | 30s | 타임아웃 후 재조회 |
| staticConfig | Disk | 5m | ETag 304 시 재사용 |
| featureFlags | In-Memory | 60s | stale-while-revalidate 백그라운드 갱신 |

Cold Start 순서:
1) Disk 캐시 -> 즉시 렌더(스켈레톤) 2) Bootstrap 병렬 요청 3) diff 머지 4) 에러 시 최소 fallback 구조.

---
## 33. Feature Flags & Remote Config (클라이언트 병행)
| 구분 | 특징 | 사용 용도 |
|------|------|-----------|
| Feature Flags (서버) | 서버 결정 / 비율 롤아웃 | 기능 Gradual Rollout |
| Firebase Remote Config | 클라이언트 즉시 토글 / UI 재배치 | 카드 순서/실험적 UI |

병행 전략: 서버 flag → 비즈니스 로직; RC → 표현/레이아웃. 충돌 시 서버 flag 우선.

---
## 34. Observability 상관관계
클라이언트 로그 전송 필드: request_id, screen, action, latency_ms, error_code.
서버와 request_id 매칭 → 분포/슬로우쿼리 역추적.
Idempotent-Replay 수신 시 별도 metric 증가.

---
## 35. OpenAPI 스니펫 예시
```yaml
paths:
    /api/pet-care/{pet_id}/summary:
        get:
            summary: Get daily care summary
            parameters:
                - name: pet_id
                    in: path
                    required: true
                    schema: { type: string }
                - name: date
                    in: query
                    required: true
                    schema: { type: string, pattern: '^\\d{4}-\\d{2}-\\d{2}$' }
            responses:
                '200':
                    description: OK
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/PetCareSummaryResponse'
                '404': { description: Not Found }
components:
    schemas:
        PetCareSummaryResponse:
            type: object
            properties:
                data:
                    $ref: '#/components/schemas/PetCareSummary'
        PetCareSummary:
            type: object
            required: [pet_id,date,water_intake_total,meal_count,activity_minutes,goals,progress_percent,updated_at]
            properties:
                pet_id: { type: string }
                date: { type: string }
                weight_latest:
                    anyOf:
                        - $ref: '#/components/schemas/WeightPoint'
                        - { type: 'null' }
                water_intake_total: { type: integer }
                meal_count: { type: integer }
                activity_minutes: { type: integer }
                goals: { $ref: '#/components/schemas/CareGoals' }
                progress_percent: { $ref: '#/components/schemas/ProgressPercent' }
                updated_at: { type: string, format: date-time }
```
*전체는 별도 openapi.yaml 관리 – 스니펫은 문서 이해 참고 용도.*

---
## 36. 마이그레이션 타임라인 (텍스트 간트)
```
Week1: Middleware(base) ──────┐
Week2: Dual-write + Backfill ├───┐
Week3: Bootstrap v1           │   ├─ Validation & Metrics
Week4: Pagination Refactor    │   │
Week5: Error Catalog & Flags  │   │
Week6: Deprecation Phase(Start)┘   │
Week7: Hardening / Perf            │
Week8: Sunset Enforcement (if metrics ok)
```

---
## 37. 품질 점검 Quick Commands (참고)
```
# Summary (goal 0 case) 검증
curl -s -H "Authorization: Bearer <token>" "http://localhost:5000/api/pet-care/123/summary?date=2025-09-09" | jq

# Range pagination (total omit)
curl -s "http://localhost:5000/api/pet-care/123/records/range?start=2025-09-01&end=2025-09-10&limit=250&include_total=true" | jq '.meta'

# Idempotent replay 시나리오
KEY=$(uuidgen); curl -s -D - -H "X-Idempotency-Key: $KEY" -H "Authorization: Bearer <t>" -H "Content-Type: application/json" -d '{"files":[]}' http://localhost:5000/api/uploads/finalize
curl -s -D - -H "X-Idempotency-Key: $KEY" -H "Authorization: Bearer <t>" -H "Content-Type: application/json" -d '{"files":[]}' http://localhost:5000/api/uploads/finalize | grep Idempotent-Replay
```
(*실행 예시는 로컬 개발 환경 기준. Windows PowerShell일 경우 uuidgen 대체 필요.)

---
## 38. 변경 관리 (Change Governance)
| 변경 타입 | 요구 사항 | 승인자 |
|-----------|-----------|--------|
| 스키마 필드 추가(비파괴) | README 섹션 + OpenAPI 반영 | Backend Lead |
| 스키마 필드 제거/의미 변경 | bootstrap_version / schema_version 업데이트 + 마이그레이션 계획 | Backend + Client Lead |
| Error Code 추가 | error_samples 테스트 + 카탈로그 PR | Backend Lead |
| Feature Flag 신규 | 문서표(15) 행 추가 + 정리 티켓 생성 | Backend Lead |
| TTL/캐시 정책 변경 | 영향 분석 + SLO 리포트 링크 | Backend + Infra |
| Idempotency hash 규칙 변경 | 5.1/5.2 동시 수정 + canonical-json-change 라벨 | Backend Lead |
| Deprecation 착수 | Deprecated 목록 갱신 + 헤더 삽입 | Backend Lead |
| Deprecation Hard | 호출량 감소율 증빙 + 최종 알림 | Backend + Product |

승인 흐름: PR → CI(gates) → 자동 라벨 → 지정 리뷰어 → Merge → Changelog(25) 갱신.

---
## 39. 한눈 요약 (Frontend Onboarding TL;DR)
1) 앱 시작시 Disk 캐시 → Bootstrap 호출 → State 머지
2) 모든 API SafeApi → AppResult 변환 (category 기반 UX)
3) Pagination: total 필드 존재 여부로 총량 판단 (없으면 추정 금지)
4) 업로드/Job: X-Idempotency-Key 재사용 + Idempotent-Replay 로깅
5) Flags: 서버(flag) > Remote Config(UI) 우선
6) Record 변경 응답 affected_dates 활용해 일/요약 동시 무효화
7) 410/Deprecation 수신 시 앱 버전/경로 교체 안내
8) p95/p99 추적 위해 request_id 로깅 포함
9) Retry는 retriable 규칙 + 최대 3회 백오프
10) total omit / partial_failures 등 조건부 필드는 존재 여부 체크 방식 파싱

---

본 추가 섹션(28~39)으로 백엔드/프론트 공용 단일 문서 참조 체계를 완성. 향후 변경 시 38절 거버넌스 프로세스 준수.

---
## 40. 추가 명세 & UX 보강
### 40.1 selected_pet null UX
| 상황 | UI 처리 | 후속 액션 |
|------|---------|-----------|
| 최초 가입 / 펫 없음 | 빈 상태 + "첫 펫 등록" CTA | 등록 완료 후 Bootstrap 재호출 |
| 펫 삭제 후 선택 펫 소실 | Snackbar("선택된 펫이 삭제되었습니다") + 등록 CTA | 새 펫 등록 시 todaySummary 초기화 |

### 40.2 Partial Failure 클라이언트 재시도 한도
- retriable=true 항목에 대해 개별 파일/레코드 최대 3회 재시도. 초과 시 사용자에게 실패 사유 표시 후 중단.

### 40.3 Rate Limit Reset 계산 예시
Headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 12
X-RateLimit-Reset: 1736486400
```
현재 epoch=1736486390 → 남은 초 = 10 (reset - now). 클라이언트 지수 백오프 상한을 남은 초 이하로 조정.

### 40.4 SSE (Phase 2 고려)
- 현재 Job 상태 갱신은 polling (1s → 2s → 4s → 8s 최대) 권장.
- Phase 2: `/api/stream/events` SSE 채널에서 `job.update` 이벤트 수신 시 즉시 상태 동기화.

### 40.5 추가 테스트 제안
| 테스트 | 목적 |
|--------|------|
| bcs_score_bounds_test | 0,1,5,6 경계 검증 (1..5 허용) |
| timestamp_skew_test | ±300s 초과 거절 |
| retryable_error_policy_test | retriable 판정 공식 일치 |
| rate_limit_reset_math_test | Reset 남은 시간 계산 정확성 |
| idempotency_collision_test | 동일 hash/상이한 key & 반대 경우 처리 |

### 40.6 Canonical JSON 오용 예방
경고: 서로 다른 시맨틱 연산(예: 다른 op_type) 간 동일 `X-Idempotency-Key` 재사용 금지. 내부 모니터링에서 다중 op_type 동일 키 탐지 시 경고 로그.

### 40.7 Range API 과도 요청 보호
- start-end 일수 > 31 → 400 (error_code=RANGE_TOO_LARGE).

### 40.8 Summary 추가 개선(미도입 아이디어)
- 응답 필드 `calculation_basis_last_record_at` (향후 도입 시 stale 탐지) – 현재 문서화만, 비도입.


---
## 41. Spec Decisions (2025-09-09)
상태: 확정(Decision Log). 변경 시 Change Log > next 버전에 기록.

### 41.a (추가) 2025-09-09 Batch 업데이트 요약
본 배치에서 실제 구현 완료된 항목 (코드 반영됨):
1) weight_latest / bcs_latest 응답 형식 정규화: 기존 단일 값 또는 `{ value, timestamp }` 혼재 가능성 제거 → `{ value, timestamp_ms }` 구조 유지. (단일 값 기대하는 구버전 클라이언트 호환을 위해 서버 측에서 필요 시 wrapping 로직 포함) ISO `timestamp` 필드는 핵심 summary 사양(41.1) 유지.
2) Clock Skew Validation 경고 밴드: ±250s 초과~±300s 이하 구간 WARN 로그 + metric(`clock_skew_warn_total`) 증가. ±300s 초과는 기존과 동일하게 OUT_OF_RANGE Validation 실패.
3) Idempotency 충돌 정밀화: 동일 `X-Idempotency-Key` + 상이 해시(body) 시 `409 CONFLICT` + `error_code=IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY` (category=CONFLICT, retriable=false). 동일 해시 재생 시 200/201 + `Idempotent-Replay: true` 유지.
4) ETag 확장: `/records/daily`, `/records/range`, `/summary`(단일 및 range) 에 강한 ETag 적용 (조건: range는 cursor/타입 필터 없는 경우 캐시 가능). If-None-Match 일치 시 304 빈 JSON 바디.
5) 캐시 무효화: create/update/delete 시 `affected_dates` 기반으로 해당 날짜의 daily/summary/summary_range 관련 ETag 키 무효화 수행.
6) updated_at / computed_at: summary range 계산 완료 시각(ms) 반영 및 meta.cache_hit=false 세트 (304 경로에서는 제공 안 함).
클라이언트 영향: weight_latest/bcs_latest 구조 객체 형태 강제 → nullable 필드로 파싱. ETag 저장 키 스킴: `summary:<pet_id>:<date>`, `summary_range:<pet_id>:<start>:<end>`, `daily:<pet_id>:<date>`.

향후 예정(미구현):
- Metrics 실제 카운터(export) wiring (현재 로깅만).
- UNSUPPORTED_CLIENT_VERSION 정책 사용 여부 확정.
- summary stale 탐지용 `calculation_basis_last_record_at` 필드(40.8 아이디어) 도입 검토.


### 41.1 weight_latest & updated_at
Decision: summary 응답 내 `weight_latest` 객체 구조 유지 `{ value: <kg>, timestamp: ISO }` (존재 없으면 null). 별도 `weight_latest_ms` 추가하지 않음; ms 정밀 시 클라이언트는 동일 timestamp ISO 파싱 후 ms 변환.
`updated_at` 는 요약 산출(aggregation) 시점(모든 관련 daily records 중 가장 늦은 timestamp_ms 와 계산 완료 시각 중 더 최신)으로 설정.
Rationale: 추후 latency 감시/캐시 TTL 계산에 단일 필드로 충분. weight delta 계산은 value 로 가능.
Implementation Notes:
- Aggregator: collect candidate latestWeightRecord (type=weight). Null-safe.
- updated_at = max( last_record.timestamp, now_when_computation_finished )

### 41.2 Clock Skew Validation
Decision: 유지 ±300s 허용; WARN 임계치 ±250s; 내부 교정(adjust) 발생 시 응답 헤더 `X-Timestamp-Adjusted: true` + 로그 메타 (old_ms,new_ms,delta_ms).
Rationale: 모바일 네트워크 지연/간헐적 기기 시계 틀어짐 허용폭 현실적. 5분 초과는 데이터 품질 저해.
Implementation:
- If |client_ts - server_now| > 300_000 → 422 VALIDATION_ERROR details.timestamp.code=OUT_OF_RANGE
- If 250_000 < |delta| ≤ 300_000 → proceed; log WARN metric `clock_skew_warn`.
- If server normalizes (e.g., caps to now) store original and include header.

### 41.3 affected_dates (Create / Update / Delete)
Decision: Create 시 항상 단일 검색 날짜(UTC date_of(timestamp))만 포함. 단, cross-midnight 영향이 발생할 수 있는 Update/Delete (timestamp 변경 포함) 의 경우 변경 전/후 날짜가 다르면 두 날짜를 모두 포함(중복 제거).
Rationale: Create 는 최초 timestamp 기준 하나; Update 에서 timestamp 변경이 캐시 invalidation 누락 방지.

### 41.4 Pagination Total 규칙
Decision: Cursor 기반에서 `total` 은 기본 미제공. 단, limit ≤ 50 이고 첫 페이지 요청에서 `with_total=true` 쿼리 플래그가 있는 경우에만 계산 (최대 5000 레코드 이하 범위에서만). 응답: `meta.total`.
Rationale: 비용 절감 + 선택적 UX 필요(첫 페이지 프로그레스 바 위치 등). Large dataset full count 비싼 연산 회피.
Fallback: 조건 불만족 시 total omit.

### 41.5 Rate Limit (Per-User + Retry-After)
Decision: 60초 윈도우 고정(bucket). 기본 사용자 한도: write 60/min, read 180/min. 초과 시 429 + `Retry-After: <seconds>` (ceil 남은 윈도우) + `X-RateLimit-Limit`, `X-RateLimit-Remaining`.
Phase:
- Phase 1 (주차 1): 관측 전용 (헤더만, 차단 없음)
- Phase 2 (주차 2): write 한도만 강제
- Phase 3 (주차 3): read 한도 강제
Rationale: 점진적 도입 → false positive 튜닝.

### 41.6 Error Catalog 확장
Decision: 추가 코드:
- VALIDATION_ERROR.details.timestamp.code=OUT_OF_RANGE
- RATE_LIMIT_EXCEEDED
- CLOCK_SKEW_TOO_LARGE (별도 사용 안 하고 OUT_OF_RANGE 로 통합 가능; 단순화 위해 미도입) → 미도입
- IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY (409)
- UNSUPPORTED_CLIENT_VERSION (426) (미래 플래그)
Rationale: 관찰/조치 분류 명확화.

### 41.7 Canonical JSON 예외 필드 테스트 범위
Decision: Canonical 해시 계산에서 float normalization(소수점 트림) & key 정렬 대상: request body 전체. 예외 없음. 단, client-generated transient 필드 (ex: local_only_debug) 허용 안 됨 → 존재 시 400 INVALID_FIELD.
Test Cases:
- 동일 키 순서 다른 JSON → 동일 해시
- float 1.0 vs 1 → 동일
- 1.2300 vs 1.23 → 동일
- 배열 순서 변경 → 다른 해시 (순서 의미 있다고 가정)

### 41.8 ETag 전략
Decision: Stage 1: summary & daily(GET) 응답에 강한 ETag (hash(records[].id + updated_at(or last_timestamp_ms))). Stage 2: 조건부 If-None-Match → 304 지원. Mutation 후 affected_dates 포함 날짜들의 ETag 캐시 파기.
Scope 제외: POST/PUT/PATCH (no ETag). Settings GET (Stage 2 에 포함 예정).
Rationale: 가장 빈번한 read 경로 캐싱으로 데이터 전송 절감.

### 41.9 Summary Range TTL
Decision: summary 캐시 TTL = 30s (서버 내부 메모리/Redis). 요청 If-None-Match 로 30초 내 불변이면 304. Mutation 영향 시 강제 무효화.
Rationale: 충분히 신선 (UI 폴링 30s 미만 빈도 드묾), 부하 절감.

### 41.10 Feature Flags Sprint Progress (A..H)
Legend: ✓ 완료, ▷ 진행중, ○ 미착수, ✕ 제외
- A (Flatten Daily) ✓
- B (Meal size/kcal 제거) ✓
- C (Mutation timestamp_ms/affected_dates) ✓
- D (Idempotent dual header) ▷ (모니터링 1주 후 legacy 제거 결정)
- E (Rate limiting enforcement) ○ (Phase 1 관측 대기)
- F (ETag summary/daily) ○
- G (Retry/backoff client) ▷ (안드로이드 구현 중)
- H (Settings-driven increments) ✓

### 41.11 Blocking Decisions Summary
| 항목 | 결정 | 후속 액션 | 담당 | Target |
|------|------|----------|------|--------|
| weight_latest 포맷 | 유지(value,timestamp) | README change log next 버전 반영 | Backend | 즉시 |
| Rate limit 전환 | 3-Phase (위) | Phase 1 feature flag enable | Backend | 주차 1 수요일 |
| Clock skew 범위 | ±300s 유지 | WARN 로깅/메트릭 추가 | Backend | 주차 1 |
| ETag 범위 | daily+summary Stage1 | 서버 hash 구현 & If-None-Match 파싱 | Backend | 주차 2 |

### 41.12 Metrics 추가
- rate_limit_exceeded{type=read|write}
- idempotent_replay_total
- etag_hit_ratio
- clock_skew_warn_total

### 41.13 Client Impact Checklist
- Parse summary.weight_latest nullable
- On 422 timestamp OUT_OF_RANGE → 사용자 시계 동기화 안내
- Store ETag per (endpoint,date,pet_id) key
- Idempotent-Replay=true 처리 → UI 중복 삽입 방지
- After mutation: invalidate (affected_dates × daily, summary today) ETag entries

### 41.14 Open / Deferred
- Legacy header 제거 타임라인: 모니터링 후 결정 
- UNSUPPORTED_CLIENT_VERSION 실제 사용: 최소 버전 정책 정의 후


