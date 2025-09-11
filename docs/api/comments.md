# comments API

댓글(comments) 도메인 API 요약입니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/posts/{post_id}/comments | jwt_required | 댓글 생성 | 201, 400, 401, 404, 500 |
| GET | /api/posts/{post_id}/comments | optional | 댓글 목록 조회(페이징) | 200, 500 |
| DELETE | /api/comments/{comment_id} | jwt_required | 댓글 삭제(작성자만) | 204, 401, 403, 404 |
| POST | /api/comments/{comment_id}/like | jwt_required | 댓글 좋아요 토글 | 200, 401, 404, 500 |

## 요청/응답 스키마

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

## 오류/예외

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

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 403 | FORBIDDEN | 이 리소스를 삭제/변경할 권한이 없습니다. |
| 404 | NOT_FOUND/COMMENT_NOT_FOUND | 요청한 리소스를 찾을 수 없습니다. |
| 400 | VALIDATION_ERROR | 요청 데이터 검증에 실패했습니다. |
| 500 | COMMENT_CREATION_FAILED/INTERNAL_SERVER_ERROR/LIKE_TOGGLE_FAILED | 서버 내부 오류가 발생했습니다. |

## 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 컬렉션 | comments, posts, users, likes |
| 키 | comment_id=UUID, like 키: comment_{user_id}_{comment_id} |
| 생성 | 트랜잭션: comments set + posts.comment_count 증가 |
| 멘션 | @nickname → NotificationType.MENTION 알림 (한글/영문/숫자/_/.- 지원, 조사 자동 제거) |
| 좋아요 | likes upsert/delete + comments.like_count 증감, COMMENT_LIKE 알림 |
