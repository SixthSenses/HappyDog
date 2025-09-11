# notifications API (코드 기준 최신)

알림 도메인. Swagger 예시는 구버전 값(필드명, 오류코드) 포함 → 본 문서가 단일 진실 소스.

## 1. 최근 변경 (2025-09)
| 변경 | 설명 |
|---|---|
| Summary 정규화 | 제어문자 제거 + 80자 초과 시 말줄임표(…) (`SUMMARY_MAX_LEN=80`) |
| 새 알림 타입 | PET_CARE_GOAL_REACHED 도입 (활동/식사 목표 달성) |
| Daily Summary 예정 | PET_CARE_DAILY_SUMMARY Enum 준비 (아직 비활성) |
| Unread 카운터 | users.notification_unread_count 증감 (best-effort, 레이스 시 재계산 fallback 가능) |
| FCM 실패 토큰 정리 | reason ∈ {unregistered, invalid-argument} 즉시 fcm_token 제거 |
| 메트릭 | notifications.created / notifications.push.sent / notifications.push.failure(reason=*) |

## 2. 엔드포인트
Base URL: `/api/notifications`

| Method | Path | Auth | 설명 | 정상 Status | 비고 |
|---|---|---|---|---|---|
| GET | /api/notifications | 필수 | 내 알림 목록 커서 페이지 조회 | 200 | `items` + `meta` |
| POST | /api/notifications/{notification_id}/ack | 필수 | 단일 알림 읽음 처리 | 200 | 이미 읽음일 경우 no-op ok |
| GET | /api/notifications/unread-count | 필수 | 현재 미읽음 수 조회 | 200 | 실시간 계산 |

## 3. 요청 파라미터 (목록)
| 이름 | 위치 | 타입 | 기본 | 제약 | 설명 |
|---|---|---|---|---|---|
| limit | query | int | 20 (schema 내부 기본) | >0 (상한 정책 내부) | 반환 최대 개수 |
| cursor | query | string | null |  | 다음 페이지 포인터 |
| format | query | string | mobile | enum: mobile, web | 프레젠테이션 포맷(타이틀/메시지 구성 분기) |

## 4. 응답 스키마

### 4.1 목록 (GET /api/notifications)
```
{
	"items": [
		{
			"id": "notif_001",
			"type": "COMMENT",
			"title": "새로운 댓글",
			"message": "테스트유저님이 댓글을 남겼습니다",
			"created_at": "2025-01-10T12:00:00Z",
			"deeplink": "app://posts/post_123",
			"read": false
		}
	],
	"meta": {"next_cursor": "cursor_123", "has_more": true}
}
```

### 4.2 읽음 처리 (POST /ack)
성공:
```
{ "status": "ok" }
```
실패 (권한/존재X): 404 + `{ "error_code": "NOT_FOUND_OR_FORBIDDEN", ... }`

### 4.3 미읽음 수 (GET /unread-count)
```
{ "unread_count": 5 }
```

## 5. 알림 타입 (Enum NotificationType)
| 값 | 설명 | 타겟 ID 예시 |
|---|---|---|
| COMMENT | 내 게시글에 새 댓글 | post_id/comment_id |
| POST_LIKE | 내 게시글 좋아요 | post_id |
| COMMENT_LIKE | 내 댓글 좋아요 | comment_id |
| MENTION | 나를 멘션 | post_id/comment_id |
| CARTOON_SUCCESS | 만화 변환 성공 (구 성공 알림) | job_id |
| CARTOON_FAILED | 만화 변환 실패/취소 (구 취소도 FAILED 처리) | job_id |
| CARTOON_PROGRESS | 진행 상황 (선택적) | job_id |
| CARTOON_COMPLETED | 최종 완료 (성공 세분화) | job_id |
| PET_CARE_GOAL_REACHED | 펫케어 목표 달성 | record_id/goal_id |
| PET_CARE_DAILY_SUMMARY | (예정) 하루 요약 | synthetic |

## 6. 에러 코드 (routes.py 실제 사용)
| 엔드포인트 | 코드 | HTTP | 조건 |
|---|---|---|---|
| 목록 | INVALID_PARAMETER | 400 | 쿼리 검증 실패 (Marshmallow) |
|  | FETCH_FAILED | 500 | 조회 중 내부 오류 |
| ack | NOT_FOUND_OR_FORBIDDEN | 404 | 소유자 불일치 또는 미존재(ack 실패) |
|  | ACK_FAILED | 500 | ack 처리 중 예외 |
| unread-count | FETCH_FAILED | 500 | 카운트 조회 중 예외 |

JWT 오류(MISSING_JWT, INVALID_JWT)는 공통 처리.

## 7. 비즈니스 로직 요약
| 단계 | 내용 |
|---|---|
| 생성 | preferences (type on/off, channel mode) 검사 후 in-app 저장 + (조건부) FCM 발송 |
| summary 정규화 | target_summary sanitize (제어문자 제거, 80자 초과 잘림) 후 템플릿 조립 |
| unread 증가 | 새로운 in-app 알림 생성 시 +1 (실패 시 재계산 여지) |
| 목록 조회 | presentation_service 포맷 변환 (제목/메시지 i18n/구성) + 커서 페이지네이션 |
| ack | is_read==False → True 전환 시 unread_count -1 (동일 알림 재요청은 no-op) |
| unread-count | 원본 저장소 count (캐시 없음) |
| 토큰 정리 | push 실패 reason 분류 → 치명적 유형이면 fcm_token null 처리 |
| 메트릭 | created / push.sent / push.failure(reason=*) 누적 |

## 8. 커서 페이지네이션
| 항목 | 설명 |
|---|---|
| 전략 | limit+1 조회 후 next_cursor 생성 → has_more 플래그 계산 |
| next_cursor | 마지막 항목의 created_at + ID 조합(내부 포맷) |
| 안정성 | 동일 created_at 다건 시 ID 보조정렬 사용 |

## 9. 보안/권한
| 항목 | 내용 |
|---|---|
| 목록/ack/unread | JWT 필수, user_id = recipient_id 매칭 확인 |
| 권한 오류 | ack에서만 404 (NOT_FOUND_OR_FORBIDDEN)로 은닉 처리 |

## 10. 향후 개선 메모
| 이슈 | 현상 | 개선안 |
|---|---|---|
| NOT_FOUND_OR_FORBIDDEN 혼합 | 리소스 없음 vs 권한 구분 불가 | ErrorCatalog 분리 (NOT_FOUND, FORBIDDEN) 적용 예정 |
| unread 레이스 | 동시 ack 처리 시 count 일시 불일치 | 주기적 재집계 배치 or transaction 이용 |
| summary 중복 sanitize | 일부 도메인 잔존 중복 util 미사용 | text_utils.truncate_summary 전면 적용 (PR4) |
| push 실패 사유 다양화 | 세부 reason 더 필요 | FCM 응답 코드 매핑 확장 (quota, auth 등) |

---
문서 버전: 2025-09 코드 스냅샷 기준 (notifications/routes.py, notification_service.py, models/notification.py)
