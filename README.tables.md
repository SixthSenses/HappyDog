# API Reference — Domain Index

문서가 길어 유지보수 불편이 커져, 도메인별 파일로 분리했습니다. 아래 링크로 이동하세요.

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
