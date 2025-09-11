# posts API

멍스타그램(posts) 도메인 API 요약입니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/posts/ | jwt_required | 게시글 생성 | 201, 400, 401, 404, 500 |
| GET | /api/posts/ | optional | 피드 조회(페이징) | 200 |
| GET | /api/posts/{post_id} | optional | 게시글 상세(+is_liked) | 200, 404 |
| PATCH | /api/posts/{post_id} | jwt_required | 게시글 수정 | 200, 400, 401, 403, 404 |
| DELETE | /api/posts/{post_id} | jwt_required | 게시글 삭제(스토리지/문서) | 204, 401, 403, 404 |
| POST | /api/posts/{post_id}/like | jwt_required | 좋아요 토글(트랜잭션) | 200, 401, 404, 500 |
| GET | /api/posts/users/{author_id}/posts | optional | 특정 사용자 게시글 목록 | 200 |

## 스키마/데이터 타입

| 스키마 | 필드 | 타입 | 비고 |
| 스키마 | 필드 | 타입 | 비고 |
|---|---|---|---|
| Author | user_id | UUID |  |
|  | nickname | string | profile_image_url은 Pet 정보에서 가져옴 |
| PetInfo | pet_id | UUID |  |
|  | name | string |  |
|  | breed | string |  |
|  | birthdate | string(YYYY-MM-DD) |  |
|  | profile_image_url | URL|null | Pet 프로필 이미지 |
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

## 오류/예외 (요약)

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

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 403 | FORBIDDEN | 이 게시글을 수정/삭제할 권한이 없습니다. |
| 404 | POST_NOT_FOUND/RESOURCE_NOT_FOUND | 요청한 게시글/리소스를 찾을 수 없습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 500 | POST_CREATION_FAILED/LIKE_TOGGLE_FAILED | 서버 내부 오류가 발생했습니다. |

## 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 컬렉션 | posts, users, pets, likes |
| 생성 | Author/PetInfo 구성 → DateTimeUtils.for_firestore 저장 |
| 피드 | created_at desc 정렬, cursor 페이징, is_liked 추론(batched) |
| 수정 | 소유자 확인 후 text/updated_at |
| 삭제 | 스토리지 파일 삭제 후 문서 삭제 |
| 인덱스 | (created_at desc), (author.user_id, created_at desc) |
