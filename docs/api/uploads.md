# uploads API

업로드(uploads) 도메인 API 요약입니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/uploads/url | jwt_required | 업로드용 Pre-signed URL 발급 | 200, 400, 401, 500 |
| POST | /api/uploads/finalize-cartoon | jwt_required | 업로드된 파일 공개 전환 및 URL 반환 | 200, 400, 401, 404, 500 |

## 요청/응답 타입

| 엔드포인트 | Request | Response |
|---|---|---|
| /url | { upload_type:string(enum), filename:string, content_type:string } | { upload_url:URL, file_path:string } |
| /finalize-cartoon | { file_path:string } | { public_url:URL } |

## 오류/검증

| 코드 | 조건 |
|---|---|
| 400 INVALID_PARAMETERS | upload_type/filename/content_type 누락/형식 오류 |
| 400 VALIDATION_ERROR | file_path 스키마 검증 실패 |
| 400 INVALID_UPLOAD_TYPE | 미지원 upload_type |
| 404 FILE_NOT_FOUND | Storage에 파일 없음 |
| 500 URL_GENERATION_FAILED/INTERNAL_SERVER_ERROR | 서버 오류 |

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 400 | INVALID_PARAMETERS | 필수 파라미터가 누락되었거나 형식이 올바르지 않습니다. |
| 400 | INVALID_UPLOAD_TYPE | 지원하지 않는 업로드 타입입니다. |
| 404 | FILE_NOT_FOUND | 업로드된 파일을 찾을 수 없습니다. |
| 500 | URL_GENERATION_FAILED/INTERNAL_SERVER_ERROR | 업로드 URL 생성/처리 중 오류가 발생했습니다. |

## Persistence & Services

| 항목 | 내용 |
|---|---|
| 업로드 URL | StorageService.generate_upload_url(user_id, upload_type, filename, content_type) |
| 공개 전환 | StorageService.make_public_and_get_url(file_path) |
| 저장 | Firestore 저장 없음(경로/URL 발급/전환) |
