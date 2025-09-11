# posts API

실제 코드(app/api/posts/routes.py) 기준으로 재작성된 멍스타그램(posts) 도메인 사양입니다. (swagger 예시 무시)

## 엔드포인트

| Method | Path | Auth | 설명 | 성공 | 주요 오류 |
|---|---|---|---|---|---|
| POST | /api/posts/ | JWT 필수 | 게시글 생성 | 201 | 400 VALIDATION_ERROR, 404 NOT_FOUND(작성자/펫 없음), 500 RECORD_CREATION_FAILED |
| GET | /api/posts/ | 선택 | 피드 페이지네이션 (is_liked 포함) | 200 | 500 FETCH_FAILED |
| GET | /api/posts/{post_id} | 선택 | 게시글 상세 (is_liked) | 200 | 404 NOT_FOUND |
| PATCH | /api/posts/{post_id} | JWT 필수 | 게시글 수정 | 200 | 400 VALIDATION_ERROR, 403 FORBIDDEN, 404 NOT_FOUND |
| DELETE | /api/posts/{post_id} | JWT 필수 | 게시글 삭제(이미지 정리 + 이벤트) | 204 | 403 FORBIDDEN, 404 NOT_FOUND |
| POST | /api/posts/{post_id}/like | JWT 필수 | 좋아요 토글 (liked 시 알림 이벤트) | 200 | 404 NOT_FOUND, 500 UPDATE_FAILED (내부) |
| GET | /api/posts/users/{author_id}/posts | 선택 | 특정 사용자 게시글 목록 | 200 | 500 FETCH_FAILED |

## 요청/응답 스키마 (핵심)

| 스키마 | 필드 | 타입/제약 | 비고 |
|---|---|---|---|
| PostCreateSchema | text | string(1..2000) | 선택 (이미지 없이 텍스트만 가능) |
|  | file_paths | array<string>(min 1) | 업로드된 GCS 경로 목록 |
| PostUpdateSchema | text | string(1..2000) | 필수 (빈 문자열 불가) |
| PostResponseSchema | post_id | string |  |
|  | user_id | string | 작성자 ID (author.user_id 전개됨) |
|  | text | string |  |
|  | image_urls | string[] | 업로드 후 공개 URL |
|  | like_count | int |  |
|  | comment_count | int |  |
|  | created_at / updated_at | ISO8601 | Firestore timestamp 변환 |
|  | is_liked | bool | 요청자 기준 (미로그인= false) |

추가 메타(내부): author, pet 서브객체는 서비스 계층에서 합성되며 클라이언트에는 납작(flat) 또는 필요한 필드만 노출될 수 있음.

## 피드/페이지네이션
응답 형식 (GET /api/posts/ 및 /api/posts/users/{author_id}/posts):
{
	"posts": PostResponseSchema[],
	"next_cursor": string|null
}
cursor: 마지막 문서 created_at + ID 기반 서버 생성 커서 (불투명). limit 기본값 10.

## 좋아요(is_liked) 배치 처리
요청자가 인증된 경우 현재 페이지 내 post_id 목록을 한 번에 post_like_service.check_likes_for_posts 로 조회 후 각 객체에 is_liked 주입. 비로그인/빈 결과는 False 고정.

## 이벤트 사이드이펙트
| 액션 | 이벤트 서비스 호출 | 후속 효과 |
|---|---|---|
| 생성 | post_events_service.handle_post_created | 작성자/펫 통계 증가, 알림 생성 가능 |
| 삭제 | post_events_service.handle_post_deleted | 이미지 정리 후 통계 감소 |
| 좋아요(liked) | post_events_service.handle_post_liked | 게시글 작성자에게 알림 (중복 토글 해제 시 없음) |

## 오류 코드 (실제 build_error 사용)
| 상황 | error_code | 비고 |
|---|---|---|
| 스키마 검증 실패 | VALIDATION_ERROR | marshmallow ValidationError.details 포함 |
| 작성자/펫 정보 누락 (create) | NOT_FOUND | ValueError 변환 |
| 게시글 미존재 | NOT_FOUND | get / patch / delete / like ValueError |
| 권한 없음 (소유자 아님) | FORBIDDEN | PermissionError 변환 |
| 생성 내부 오류 | RECORD_CREATION_FAILED | 500 |
| 목록 조회 오류 | FETCH_FAILED | 500 |
| 좋아요 내부 처리 실패(None 반환) | UPDATE_FAILED | 서비스 None 반환 시 |

LIKE_TOGGLE_FAILED 등 과거 문자열은 코드 경량화 과정에서 UPDATE_FAILED 로 통일(미정리 영역 존재 가능) 되었으며, 클라이언트는 code 기반 분기 권장.

## 스토리지 연계
이미지 업로드는 사전 /api/uploads/url 로 경로 확보 → file_paths 로 전달 → 저장 후 image_urls 로 변환.

## 인덱스 및 성능
| 쿼리 | 인덱스 | 비고 |
|---|---|---|
| 글로벌 피드 | created_at DESC | 기본 정렬 |
| 사용자별 | (author.user_id, created_at DESC) | 파이어스토어 복합 인덱스 |

## 주의 사항
1) 응답 키는 items 가 아니라 posts.
2) 삭제 성공 시 204 No Content (본문 없음).
3) 좋아요 토글은 멱등 아님: 반복 호출 시 like ↔ unlike 전환.
4) 비로그인 피드 조회 가능하나 is_liked 항상 false.
5) text 와 image 둘 다 비어있는 요청은 ValidationError.

