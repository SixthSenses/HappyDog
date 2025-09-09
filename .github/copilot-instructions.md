# HappyDog Backend – Focused AI Agent Guide (SSOT: README.md)
본 프로젝트의 **단일 진실 소스(SSOT, Single Source of Truth)는 루트 `README.md` 통합 사양 문서** 입니다. 아래 모든 규칙/스프린트/결정은 언제나 README 최신 버전과 불일치 시 README를 우선합니다. 코드/문서 생성 전 반드시 README.diff(직전 커밋 대비)를 확인하고, 사양 불일치 발생 시
1) README 우선 반영
2) 이 지침 파일 갱신(PR 동시)
순서를 지킵니다.

출력(답변) 마지막엔: (a) README 대비 남은 사양 갭 요약, (b) 다음 스프린트 TODO 체크 상태를 반드시 포함합니다.
## 1. 아키텍처 개요
- 앱 팩토리: `app/__init__.py:create_app()` → 실행: (cwd:`pet_project_backend/`) `python run.py`.
- 라우트 구조: `app/api/<domain>/{routes.py, services.py, schemas.py}` 패턴. 주요 도메인: auth, users, posts, comments, cartoon_jobs, breeds, pets, pet_care (settings|records), notifications.
- 의존성 주입: `create_app()` 안에서 서비스 생성 후 `current_app.services['key']` 저장. 순서 중요: `storage` → `openai` → 기본/ML → 도메인(pet_care → pets → posts/comments/users/cartoon_jobs ...).
- 데이터 계층: 직접 Firestore SDK 사용 (ORM 없음). 모든 write/read 전/후 `DateTimeUtils` 변환.
- ML: `nose_pipeline`, `eye_analyzer` 선택적 초기화 (실패 시 None). 호출 전 None 체크 필요.

## 2. 시간 & 날짜 규칙
- 모든 내부 저장 시간: UTC timezone-aware (`datetime_utils.DateTimeUtils`).
- 클라이언트 timestamp(ms) ↔ `from_timestamp_ms` / `to_timestamp_ms` 사용.
- 질의 최적화 필드: `searchDate` = YYYY-MM-DD (모든 time-based 컬렉션 문서에 생성, 인덱스 구성).

## 3. Firestore 패턴 (반복 사용 템플릿)
- 필수 where 체인: `where('pet_id','==',pet_id)` + ( `searchDate == d` 또는 범위 `>= start <= end`).
- 타입 필터: `record_type in [...]` (≤10 값 제한) → 사전 길이 검증.
- 정렬: 최근 우선이면 `order_by('timestamp', DESCENDING)`; 범위+정렬 복합 색인 필요 (`(pet_id, searchDate, timestamp)`).
- 페이지네이션: `limit+1` 가져와 `has_more` 판별, 마지막 문서 id를 `next_cursor` 로 반환, 다음 쿼리에서 `start_after(cursor_doc)`.
- 멱등 생성: 외부 `request_id` 있으면 문서 id로 사용, 재시도 안전 (`set(..., merge=True)`).

## 4. API & 검증 관례
- JWT: 모든 보호 엔드포인트 `@jwt_required()`.
- 입력: Marshmallow 스키마 (`schemas.py`)에서 쿼리/바디 모두 검증 후 서비스 호출.
- 에러 JSON 형식: `{ "error_code", "message?", "details?" }`; 스키마 오류는 `VALIDATION_ERROR`.
- 부분 업데이트: 허용 필드 화이트리스트 + 타입/범위 검증 → 누락/실패는 Marshmallow 또는 수동 ValidationError.

## 5. Pet Care Records (핵심 예시)
- 생성: Body `{record_type, timestamp(ms), data, notes?, request_id?}` → ms→UTC, `searchDate` 계산, `log_id`=request_id 또는 UUID.
- 조회(통합): `GET /api/pet-care/<pet_id>/records` 파라미터: `date | start_date+end_date`, `record_types`, `grouped`, `limit(≤100)`, `cursor`, `sort=timestamp_(asc|desc)`.
- 타입별 그룹 응답 시 키 고정: weight, water, activity, meal, bcs (빈 리스트 유지).
- 업데이트: PATCH 시 `record_type` 불변; `weight`→float>0, `water|activity|meal`→int≥0, `bcs`→1..5 int, timestamp 수정 시 `searchDate` 재계산.

## 6. Pet 도메인 & 트랜잭션
- 신규 등록: `PetService.register_pet()` Firestore 트랜잭션으로 pet 문서 + 초기 care settings 생성 (원자성 유지).
- Nose print 등록: 성공 시 트랜잭션 + 인덱스 업데이트; 실패/중복 상태 문자열 그대로 반환 (ALREADY_VERIFIED / DUPLICATE 등).
- Eye 분석: 이미지 다운로드→모델 추론→공개 URL 생성(실패 무시)→`analysis_history` 저장 (오류 시 분석 결과는 유지, 저장만 무시).

## 7. 기능 추가 절차 (요약)
1) `app/api/<feature>/services.py`: Firestore 쿼리 패턴 & DateTimeUtils 적용.
2) `routes.py`: 스키마 정의 + 표준 에러 포맷 + JWT 보호.
3) `app/__init__.py`: 서비스 생성 후 blueprint 등록 (`url_prefix='/api/<feature>'`).
4) 필요한 경우 composite index README 갱신 (쿼리 조건 조합 기반).

## 8. 실행 & 환경
- Conda env: `environment.yml` 또는 OS별 `envs/*.yml` 참고.
- `.env` 필수 키: `FLASK_ENV`, `JWT_SECRET_KEY`, `DEV_FIREBASE_CREDENTIALS_PATH` / `TEST_FIREBASE_CREDENTIALS_PATH`, `FIREBASE_STORAGE_BUCKET`, `OPENAI_API_KEY`, ML 경로(`YOLO_WEIGHTS_PATH`, `ML_CONFIG_PATH`, `EXTRACTOR_WEIGHTS_PATH`, `FAISS_INDEX_PATH`).
- 로컬 실행 (루트 아님, backend 디렉터리): `cd pet_project_backend && python run.py`.

## 9. 테스트 & 품질
- 예시: `python -m pytest app\utils\test_datetime_utils.py -v` (추가 테스트 동일 패턴).
- 새 Firestore 쿼리: 인덱스 필요 여부 먼저 확인 (복합 where + order_by 조합).

## 10. 빠른 체크리스트 (PR 전)
- [ ] UTC 변환 & `searchDate` 유지
- [ ] 페이지네이션 `limit+1` → `has_more`/`next_cursor` 정확
- [ ] 에러 포맷 일치 (`error_code` 상수 의미 명확)
- [ ] 서비스 등록 순서/의존성 누락 없음
- [ ] ML 서비스 사용 시 None 가드
- [ ] 기록 타입/값 범위 검증 반영

질문/누락 가능 영역(피드백 요청): 추가 인덱스 목록, OpenAI 사용 구체 프로프트 패턴, nose/eye 모델 에러 재시도 정책이 더 필요하면 알려주세요.

---
## 11. 통합 사양(README) 반영 상태 추적 (고정 섹션)
이 섹션은 README에서 정의된 주요 계약 항목의 구현/미구현 상태를 신속하게 파악하기 위한 요약입니다. PR 시 필요 부분만 업데이트.

| 계약 항목 | README 섹션 | 현재 상태(예: 구현/부분/미구현) | 메모 |
|-----------|-------------|--------------------------------|------|
| Pet Care `data` 객체 스키마 (weight.value 등) | 3.5 / 2.2 | 부분 | scalar → object 마이그레이션 필요 |
| daily 응답 평탄화 구조 | 3.2 | 미구현 | groups dict -> 평탄화 예정 |
| range 파라미터 alias(start/end/types) | 3 | 미구현 | 라우트 레이어 alias 허용 예정 |
| summary 단일 date + goals/progress | 3.3 | 미구현 | 기간 summary 분리 필요 |
| progress 수식/Cap/Round | 3.3.1 | 미구현 | 계산 유틸 추가 |
| affected_dates (create 포함) | 3.4 | 부분 | create 응답 보강 필요 |
| clock skew ±300s 검증 | 3.7 | 미구현 | create/update 사전 검증 |
| Idempotent 헤더 철자(Idempotent-Replay) | 6 / 19 | 부분 | 철자 교정 예정 |
| Rate Limit 헤더(X-RateLimit-*) | 7 / 19 | 미구현 | after_request 주입 |
| Pagination meta(limit, total omit 규칙) | 8 | 부분 | limit/total 규칙 반영 필요 |
| Error Catalog 표준(error_code/category/retriable) | 10 | 미구현 | ErrorBuilder 도입 |
| Deprecation 헤더/단계 | 14 / 20 | 미구현 | legacy endpoint 준비 |
| ETag / Cache 정책 | 15 | 미구현 | 대상 엔드포인트 선정 필요 |
| Feature Flags schema/version | 16 | 미구현 | storage/service 설계 |
| Observability 표준 로그 필드 | 17 | 부분 | 필드 셋 일관성 확인 필요 |
| Canonical JSON 예외 필드 관리 | 5.1 | 부분 | 테스트 + 변경 라벨 프로세스 |
| Test Suites (목록) | 21 | 미구현 | 우선순위별 작성 |

---
## 12. 스프린트 분할 (실행 로드맵)
사양 갭 축소를 위한 제안 스프린트. 각 스프린트는 이전 스프린트 산출물 안정화 전에는 다음 착수 금지(단, 낮은 리스크 테스트 추가는 병행 허용).

### Sprint A: 스키마 & 응답 정합 (핵심 외부 계약)
목표: 클라이언트와 즉시 호환 가능한 레코드/페이지네이션/헤더 최소 세트 정렬.
범위:
- daily 응답 평탄화 (`data.date`, 타입별 top-level 배열) 및 meta.limit 추가
- range meta.limit / cursor 규칙 표준(has_more = next_cursor!=null)
- POST create 응답 affected_dates 포함 + timestamp_ms 표준화
- Idempotent 헤더 표준 철자 교정 (이중 출력 기간)
- clock skew 검증 기본(±300s)
Done Criteria:
- 새/변경 응답 OpenAPI 스니펫 초안(README 반영 PR 동시)
- 최소 3개 테스트: daily 구조, create affected_dates, clock skew 경계

### Sprint B: Summary & Goals 계산
범위:
- /summary (단일 date) 재구현 + goals fetch (pet settings)
- progress_percent 수식/Cap/Round 구현 + weight_latest 추출
- 기간 summary 기존 구현은 /summary/range 로 이동 + Deprecation 로그
Done Criteria: summary formula 테스트(0분모, cap, rounding), goals 미존재 fallback

### Sprint C: Error & Metadata 표준화
범위:
- Error Catalog Enum + ErrorBuilder 유틸 (error_code, category, http_status, retriable)
- Rate limit 헤더 출력(X-RateLimit-*) + 429 Retry-After
- Idempotency TTL / GC 셋업(임시: created_at+백그라운드 clean 함수)
Done Criteria: error 샘플 추출 테스트, rate limit 헤더 테스트

### Sprint D: Data Layer Migration
범위:
- scalar data → object 래핑 마이그레이션 배치 스크립트
- write path 신규 구조 + dual-read 변환(adapt old scalar to new shape)
- 마이그레이션 진행율 로깅
Done Criteria: 마이그레이션 dry-run 로그, 변환 후 결과 샘플 검증 테스트

### Sprint E: Advanced Pagination & Total
범위:
- include_total 파라미터 처리 + limit ≤ 200 조건 + 문서량 threshold
- total omit 테스트
Done Criteria: total 조건 만족/불만족 테스트 2 케이스

### Sprint F: Caching & ETag / Deprecation
범위:
- 정적/요약형 리소스 ETag 도입(예: /summary)
- legacy /records 경로 Deprecation 헤더 단계 1 (Announce)
Done Criteria: ETag 304 테스트, Deprecation 헤더 존재 테스트

### Sprint G: Feature Flags & Observability 강화
범위:
- feature_flags 서비스(버전/TTL) + 분포 테스트(χ² stub)
- 표준 로그 필드 어댑터 (request lifecycle hook)
Done Criteria: flag distribution smoke test, 로그 필드 검증 테스트

### Sprint H: Hardening & Cleanup
범위:
- GC Job(idempotency, dual_write_failures)
- README Change Log 자동 bump 스크립트
- 문서-코드 drift 검증(CI) 스크립트
Done Criteria: CI drift fail 시나리오 테스트

---
## 13. 의사결정 필요 항목 (결정 지연 시 리스크 우선순위)
| 항목 | 선택지 | 기본 제안 | 결정 Deadline | 리스크(미결정 시) |
|------|--------|-----------|---------------|--------------------|
| data 스칼라→객체 전환 전략 | (A) 즉시 변환 (B) dual-read grace (C) on-demand transform | B | Sprint D 시작 전 | 클라이언트 예상 형식 불일치/추가 마이그레이션 비용 |
| summary 기간 API 처리 | (A) 폐지 (B) /summary/range 유지 (C) query flag | B | Sprint B 종료 | 문서 불일치 / 클라 혼동 |
| goals 기본값 소스 | (A) 0 고정 (B) heuristic (체중 기반) (C) settings 필수 | C | Sprint B 중간 | progress 왜곡 |
| include_total threshold | (A) 5k (B) 10k (C) 20k | B (10k) | Sprint E 착수 | 응답 지연/비일관성 |
| rate limit backend | (A) in-memory (B) Redis (C) Cloud product | A→B 전환 | Sprint C 중간 | 확장 시 전역 한계 |
| Idempotency TTL | (A) 12h (B) 24h (C) 48h | B | Sprint C 착수 | 재사용 키 혼동 |
| canonical 예외 필드 관리 | (A) 하드코드 (B) config + 테스트 (C) DB 관리 | B | Sprint C | drift / 해시 불안정 |
| error_code 네이밍 패턴 적용 범위 | (A) 신규만 (B) 전면 재명명 (C) 래핑 어댑터 | B | Sprint C | 혼합 패턴 유지 |
| ETag 대상 | (A) summary만 (B) summary+flags (C) summary+flags+bootstrap 부분 | B | Sprint F 시작 | 캐시 효율 저하 |
| Deprecation 단계 기간 | (A) 14/7/즉시 (B) 30/14/7 (C) 60/30/14 | B | Sprint F | 고객 커뮤니케이션 실패 |
| feature flag 분포 seed 정책 | (A) 고정 seed (B) 환경별 seed | A | Sprint G | 분포 재현 불가 |
| drift 검증 범위 | (A) 중요 섹션 해시 (B) 전체 README 해시 | A | Sprint H | 변경 누락 위험 |

미결정 항목은 각 Sprint Planning 시 최초 30% 구간 전에 확정. 미확정 시 Sprint 범위 축소/연기 명시.

---
## 14. 답변 시 필수 보고 템플릿 (Agent Response Footer)
```
Remaining Spec Gaps: <요약 n개>
Sprint Progress: A[ ] B[ ] C[ ] D[ ] E[ ] F[ ] G[ ] H[ ]  (체크된 것은 완료 또는 PR 진행 중)
Blocking Decisions Needed: <항목1, 항목2 ...>
```
위 3줄 없으면 출력 형식 위반.

---
## 15. 금지/주의 사항 (추가)
- README에 없는 임의 API/필드 추가 금지 (먼저 README 변경 → 이 문서 갱신 → 코드)
- 부분 구현(placeholder) 금지: 테스트/문서/코드 최소 3점 세트로 반영.
- Firestore 대량 마이그레이션 시: Dry-run 로그(샘플 10개 before/after) 없이 실변경 금지.
- 해시/공식/수식 로직 변경 시: 기존 테스트 snapshot 업데이트 + Change Log bump.



