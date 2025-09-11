# comments API (코드 기준 최신)

댓글 도메인. Swagger 문서 일부 필드/에러코드가 구버전이므로 실제 routes.py 구현을 기준으로 재정의했습니다.

## 1. 엔드포인트

| Method | Path | Auth | 설명 | 정상 Status | 비고 |
|---|---|---|---|---|---|
| POST | /api/posts/{post_id}/comments | 필수 | 댓글 생성 | 201 | 멘션/알림 트리거 |
| GET | /api/posts/{post_id}/comments | 선택 | 댓글 목록 페이지 조회 | 200 | 로그인시 is_liked 포함 |
| DELETE | /api/comments/{comment_id} | 필수 | 댓글 삭제 (작성자) | 204 | 무본문 응답 |
| POST | /api/comments/{comment_id}/like | 필수 | 좋아요 토글 | 200 | liked boolean 반환 |

## 2. 스키마

### 2.1 생성 요청 (CommentCreateSchema)
| 필드 | 타입 | 제약 | 비고 |
|---|---|---|---|
| text | string | 1..1000자 | 멘션 포함 가능 (@nickname) |

### 2.2 응답 (CommentResponseSchema 실제 구성)
routes.py 직렬화 결과 기준.

| 필드 | 타입 | 설명 |
|---|---|---|
| comment_id | string | 댓글 ID |
| post_id | string | 부모 게시글 ID |
| user_id | string | 작성자 사용자 ID |
| text | string | 본문 |
| created_at | ISO8601 | 생성 시각 |
| like_count | int | 현재 좋아요 수 |
| is_liked | bool | (옵션) 로그인 사용자 좋아요 여부, 미로그인/ enrichment 실패 시 생략 |

예시 (GET 목록, 로그인):
```
{
	"comments": [
		{
			"comment_id": "c1",
			"post_id": "p1",
			"user_id": "u2",
			"text": "멋진 사진! @doglover",
			"created_at": "2025-01-10T12:00:00Z",
			"like_count": 3,
			"is_liked": true
		}
	],
	"next_cursor": "c1__1712131230000"
}
```

## 3. 페이지네이션
| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---|---|
| limit | int | 10 | 1~(서비스 정책 상 합리적 상한, 현재 코드 제한 없음) |
| cursor | string | null | 다음 페이지 위치 토큰 |

응답: comments[], next_cursor (더 없음=null)

## 4. 에러 코드 (build_error 호출 실측)

| 엔드포인트 | 코드 | HTTP | 조건 |
|---|---|---|---|
| POST | VALIDATION_ERROR | 400 | Marshmallow 검증 실패 |
|  | NOT_FOUND | 404 | 존재하지 않는 post 등 ValueError |
|  | RECORD_CREATION_FAILED | 500 | 저장/이벤트 내부 예외 |
| GET | FETCH_FAILED | 500 | 목록 조회 중 예외 |
| DELETE | FORBIDDEN | 403 | 작성자 불일치 (PermissionError) |
|  | NOT_FOUND | 404 | 대상 없음(ValueError) |
| LIKE | NOT_FOUND | 404 | 대상 없음(ValueError) |
|  | UPDATE_FAILED | 500 | 토글 처리 중 예외/알림 실패 |

주의: 구 문서에 COMMENT_CREATION_FAILED/LIKE_TOGGLE_FAILED 등의 이름이 있었으나 현재 routes.py는 RECORD_CREATION_FAILED, UPDATE_FAILED 를 사용.

## 5. 멘션 처리
| 항목 | 내용 |
|---|---|
| 패턴 | @nickname (한글/영문/숫자/_/.-) |
| 해석 | comment_mentions 서비스 `resolve_mentions_from_text` (실패 시 경고 로그 후 무시) |
| 알림 | comment_events.handle_comment_created 호출 시 mention_data 전달 → MENTION 알림 생성 |

## 6. 좋아요 처리
| 항목 | 내용 |
|---|---|
| 토글 | toggle_comment_like → action: liked / unliked |
| 알림 | liked 시에만 handle_comment_liked 트리거 |
| is_liked 계산 | 목록 조회 시 사용자 인증된 경우 batch `check_likes_for_comments` 후 각 항목에 주입 (실패 시 경고 로그, 필드 생략) |

## 7. 트랜잭션 & 카운트
| 동작 | 내용 |
|---|---|
| 생성 | comments insert + posts.comment_count 증가 (서비스 내부 트랜잭션) |
| 삭제 | comments 삭제 + posts.comment_count 감소 |
| 좋아요 | likes upsert/delete + comments.like_count 증감 |

## 8. 예외/로그 전략
| 상황 | 처리 |
|---|---|
| 멘션 파싱 실패 | warning 후 계속 진행 |
| 좋아요 is_liked enrichment 실패 | warning 후 필드 생략 |
| 일반 예외 (생성/목록/토글) | logging.error + 대응 build_error 코드 |

## 9. 향후 개선 메모
| 이슈 | 현상 | 개선 아이디어 |
|---|---|---|
| NOT_FOUND 사용 범위 | 존재 X vs 권한 문제 혼재 가능 | 권한 별도 코드 분리 (PERMISSION_DENIED) 재검토 |
| is_liked N회전 위험 | batch 사용하나 limit 확대시 성능 검증 필요 | LIKE_BATCH 상수화 & 인덱스 점검 |
| 멘션 중복 알림 | 동일 사용자 다중 멘션 시 중복 가능성 | set 처리 및 de-dup 로직 강화 |

---
문서 버전: 2025-09 코드 스냅샷 기준 (comments/routes.py)
