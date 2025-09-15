# users API

실제 코드(app/api/users/routes.py) 기준 최신 상태. 사용 중지(deprecated) 엔드포인트는 본 표에서 제거.

## 엔드포인트

| Method | Path | Auth | 설명 | 상태코드 (성공) | 비고 |
|---|---|---|---|---|---|
| GET | /api/users/me | JWT | 내 기본 정보 (user_id, nickname, email, has_pet, pet_id) | 200 | |
| GET | /api/users/me/summary | JWT | 사용자 + 단일 펫 + 펫케어 설정 통합 | 200 | 마이페이지/프로필 공용 |
| GET | /api/users/me/notification-preferences | JWT | 알림 설정 조회 | 200 | |
| PUT | /api/users/me/notification-preferences | JWT | 알림 설정 갱신 | 200 | PATCH 아님 |
| PUT | /api/users/me/fcm-token | JWT | FCM 토큰 업데이트 | 200 | POST 아님 |

문서에 있었던 다음 엔드포인트는 현재 코드에 없음: PATCH /me/profile-image, DELETE /me, GET /{user_id}/summary, GET /me/profile (alias). 필요 시 별도 구현 후 문서화.

Deprecated 참고: `GET /api/users/{user_id}/public` 는 `/api/pets/profile?view=social&user_id=` 로 대체되었으며 향후 제거 예정이므로 본 표에서 제외했습니다.

## 알림 설정 스키마
NotificationPreferencesSchema (요청/응답 동일):
{
	"push_enabled": bool,
	"email_enabled": bool,
	"marketing_enabled": bool
}
모두 boolean, 부분 업데이트 미지원(전체 payload 필요).

## FCM 토큰
PUT /api/users/me/fcm-token
Request: { "fcm_token": "string" }
성공 시 {"message": "FCM 토큰이 업데이트되었습니다."}
이전 토큰(cleanup)은 notification 서비스가 주기적으로 정리.

## 통합 요약 (/me/summary) 응답 예
{
	"user": { user_id, nickname, post_count? },
	"pet": { pet_id, name, breed, profile_image_url, is_verified, ... },
	"pet_care_settings": { daily_meal_count, target_daily_meal_count, target_daily_activity_minutes, target_weight }
}
pet 혹은 settings 없으면 null/생략될 수 있음.

## 오류 코드 (주요)
| 상황 | error_code |
|---|---|
| 사용자 미존재 | USER_NOT_FOUND |
| 인증 누락/만료 | MISSING_JWT / INVALID_JWT |
| 스키마 검증 실패(알림/FCM) | VALIDATION_ERROR |
| 내부 조회 실패 | FETCH_FAILED |
| 업데이트 실패(알림/FCM) | UPDATE_FAILED |

## 데이터 저장
| 컬렉션 | 내용 |
|---|---|
| users | 기본 프로필, fcm_token, notification_preferences |

프로필 이미지 URL 노출은 Pet 프로필을 통해 통합(사용자 문서 단독 제공 X).

