# users API

사용자(users) 도메인 API 요약입니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| GET | /api/users/{user_id} | optional | 공개 프로필 + post_count | 200 |
| PATCH | /api/users/me/profile-image | jwt_required | file_path 기반 프로필 이미지 갱신 | 200, 401 |
| DELETE | /api/users/me | jwt_required | 계정 삭제(Firebase Auth) | 204, 401, 500 |
| GET | /api/users/me/notification-preferences | jwt_required | 알림 개인 설정 조회 | 200, 401 |
| PATCH | /api/users/me/notification-preferences | jwt_required | 알림 개인 설정 업데이트 | 200, 400, 401, 500 |
| POST | /api/users/me/fcm-token | jwt_required | FCM 토큰 등록/업데이트 | 200, 401 |
| GET | /api/users/{user_id}/summary | optional | 공개 사용자 요약 + (pet_id) 반려견 요약 | 200, 500 |
| GET | /api/users/me/summary | jwt_required | 내 프로필 + 단일 반려견 + 해당 케어 설정 요약 | 200, 500 |
| GET | /api/users/me/profile | jwt_required | 내 프로필 요약(alias of /me/summary) | 200, 500 |

정책/비고
- 1명=1펫 정책을 따릅니다. 서버가 사용자의 첫/유일 펫을 자동으로 해석하여 /me/summary 응답의 pet에 포함합니다.
- 기존 selected-pet 개념/엔드포인트는 제거되었습니다. 클라이언트는 별도의 선택 저장 없이 /me/summary를 사용하세요.

## 스키마/데이터 타입

| 스키마 | 필드 | 타입 | 비고 |
|---|---|---|---|
| UserPublicResponseSchema | user_id | UUID |  |
|  | nickname | string |  |
|  | post_count | int | profile_image_url은 Pet 정보에서 가져옴 |
| FCMTokenSchema | fcm_token | string |  |
| NotificationPreferencesSchema | mode | string|null | optional |
|  | types | object{ [type:string]: boolean } | optional |

## Persistence & Services

| 항목 | 내용 |
|---|---|
| users | 프로필, fcm_token, notification_preferences 저장 |
