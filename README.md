# API Reference — Domain Index

문서가 길어 유지보수 불편이 커져, 도메인별 파일로 분리했습니다. 

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

## 도메인별 문서

- auth: docs/api/auth.md
- breeds: docs/api/breeds.md
- cartoon_jobs: docs/api/cartoon_jobs.md
- comments: docs/api/comments.md
- notifications: docs/api/notifications.md
- pet_care/records: docs/api/pet_care.records.md
- pet_care/settings: docs/api/pet_care.settings.md
- pets: docs/api/pets.md
- posts: docs/api/posts.md
- uploads: docs/api/uploads.md
- users: docs/api/users.md

각 문서는 엔드포인트 표, 요청/응답 스키마, 오류 코드, 저장/비즈니스 로직을 포함합니다.

---

## OpenAPI Spec Generation (Unified)

공식 스펙 생성 스크립트는 단일화되었습니다. (레거시 `generate_swagger.py` 제거)

### 기본 생성 (전체 초기화)
```
conda run -n pet-backend python pet_project_backend/scripts/swagger_build.py \
	--app pet_project_backend.app:create_app \
	--out openapi.json --validate
```

### 경량 모드 (문서 전용, 외부 서비스 생략)
Firebase / Storage / ML / OpenAI 초기화를 모두 건너뜁니다.
```
conda run -n pet-backend python pet_project_backend/scripts/swagger_build.py \
	--app pet_project_backend.app:create_app \
	--out openapi.json --validate --docs-mode
```

### 추가 옵션
| 플래그 | 설명 |
|--------|------|
| `--pretty-out FILE` | Pretty JSON 2차 출력 파일 생성 |
| `--minify` | 압축(JSON, 공백 최소화) 출력 |
| `--yaml` | YAML 포맷 출력 |
| `--add-servers` | 서버 리스트 섹션 포함 |
| `--add-tags` | 첫 세그먼트 기반 단순 태그 추론 |
| `--title / --version` | 메타데이터 재정의 |
| `--validate` | prance 기반 OpenAPI 문법 검증 |
| `--docs-mode` | 무거운 외부 초기화 비활성화 |

Docstring 규칙: 첫 줄 Summary, 빈 줄 후 Description. (예: `app/api/.../routes.py` 함수).

에러 응답: `error_catalog` 의 정의가 `components.responses`에 표준화된 형태로 자동 매핑됩니다.

### CI 권장
1. `--docs-mode` 로 스펙 생성 (환경 의존 제거)
2. 생성된 `openapi.json` 을 이전 커밋과 diff → drift 감지 실패 시 PR 실패 처리

### 향후 확장 계획
- Marshmallow 스키마 리플렉션 → components.schemas 자동화
- 인증 스키마(Bearer / Refresh) 추가
- 페이징 공통 meta 구조 자동 삽입
- 커버리지: 실제 라우트 대비 스펙 누락 감지 테스트

이전 `api_documentation` 데코레이터 기반 상세 예제 시스템은 단계적으로 중단되며, 필요 시 추후 메타데이터 병합 유틸 추가 예정입니다.
