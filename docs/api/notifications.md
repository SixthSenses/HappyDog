# notifications API

알림(notifications) 도메인 API 요약입니다.

## 최근 변경 (2025-09)
- summary 정규화: 제어문자 제거 및 80자 초과 시 말줄임표(`…`) 처리.
- unread 카운터: 사용자 문서(`users.notification_unread_count`)에 증감 반영 (best-effort). ack 시 최초 1회만 감소.
- FCM 실패 분류 및 토큰 정리: unregistered/invalid-argument 분류 시 `fcm_token` 제거.
- 메트릭 추가: `notifications.created`, `notifications.push.sent`, `notifications.push.failure(reason=*)`.
- 신규 타입: `PET_CARE_GOAL_REACHED` (펫케어 활동/식사 목표 달성) 사용 개시.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| GET | /api/notifications | jwt_required | 내 알림 목록 조회(페이징) | 200, 401, 500 |
| POST | /api/notifications/{notification_id}/ack | jwt_required | 알림 읽음 처리 (최초 읽음만 unread 감소) | 200/204, 401, 404, 500 |
| GET | /api/notifications/unread-count | jwt_required | 읽지 않은 알림 개수 조회 (실시간 재조회, 캐시 미사용) | 200, 401, 500 |

## 출력/데이터 타입

| 객체 | 필드 | 타입 | 비고 |
|---|---|---|---|
| Notification item | id | UUID |  |
|  | type | string(enum) |  |
|  | title | string |  |
|  | message | string |  |
|  | created_at | ISO8601 |  |
|  | deeplink | string(app://...) |  |
|  | read | boolean |  |
| List Response | notifications | array<item> |  |
|  | next_cursor | string | optional |
|  | has_more | boolean | optional |
| Ack Response | message | string |  |

## 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| 목록 | 500 FETCH_FAILED | 서버 오류 |
| ack | 404 NOT_FOUND_OR_FORBIDDEN | 미존재/권한 없음 |
|  | 500 ACK_FAILED | 서버 오류 |
| unread-count | 500 FETCH_FAILED | 서버 오류 |

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 404 | NOT_FOUND_OR_FORBIDDEN | 알림을 찾을 수 없거나 권한이 없습니다. |
| 500 | FETCH_FAILED/ACK_FAILED | 알림 데이터를 처리하는 중 오류가 발생했습니다. |

## 저장/비즈니스 로직

| 항목 | 내용 |
|---|---|
| 생성 | recipient 검증 + preferences(types, mode) 반영, in-app 저장, 필요 시 FCM 발송, 실패 분류 후 토큰 무효 처리, unread_count 증분 |
| 목록 | recipient_id 기준 내림차순, limit+1로 has_more 판단, created_at ISO 직렬화 |
| ack | 소유자 일치 & 미읽음일 때 is_read=true 및 unread_count 1 감소 |
| unread | count() 또는 stream 합산 (향후 캐시/집계 고려) |
| summary 정규화 | 제어문자 제거, 80자 초과 잘림+… (댓글/멘션/좋아요 등 target_summary) |
| push metrics | notifications.push.sent / failure(reason) 기록 |
| 토큰 정리 | FCM 오류 reason ∈ {unregistered, invalid-argument} 시 사용자 문서 fcm_token 제거 |
