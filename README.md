## HappyDog Backend

이 저장소는 Flask + Firebase(Firestore/Storage) 기반 백엔드입니다. 최신 API 문서는 도메인별로 분리되어 있습니다.

### 시작하기
- 아나콘다 가상환경 'happydog-backend' 반드시 실행
- 실행(Windows, cmd): `pet_project_backend/` 폴더에서 서버 실행. 세부는 `pet_project_backend/README_SETTING.md`와 환경 파일(`envs/`) 참고.
- 환경 변수: `.github/copilot-instructions.md`와 `pet_project_backend/app/core/config.py` 설명 참조.

### API 문서 (도메인별)
- 인덱스: `README.tables.md`
- 세부 문서: `docs/api/` 폴더의 각 md 파일(auth, pets, pet_care, posts, comments, notifications, cartoon_jobs, uploads, breeds, users).
- 최근 변경(2025-09): notifications summary 정규화/토큰 정리, 펫케어 goal 달성 알림 도입.

### 코드 가이드
- 블루프린트/서비스/미들웨어/에러 규약: `.github/copilot-instructions.md` 요약 참조.
- 표준 에러 응답: `app/utils/error_catalog.py` 기반.
- 멱등 처리: `app/middleware/idempotency_middleware.py` 참고.

### 참고
- 이전 “Minimal Spec” 문서는 보관됨: `docs/archived/README.minimal-legacy.md`



