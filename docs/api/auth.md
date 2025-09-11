# auth API

이 문서는 인증(auth) 도메인 API를 요약합니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/auth/social | - | 소셜 로그인/회원가입 처리 (Google 코드 교환 → 토큰 발급) | 200, 401, 500 |
| POST | /api/auth/token/refresh | Refresh JWT | Refresh 토큰으로 Access 토큰 재발급 | 200 |
| POST | /api/auth/logout | Access/Refresh JWT | 전달된 access/refresh JWT 블랙리스트 처리(서버 로그아웃) | 200, 400, 422, 500 |

## 요청 스키마

| 스키마 | 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|---|
| SocialLoginSchema | provider | string | ✔ | 'google' 등 |
|  | auth_code | string | ✔ | OAuth 인증 코드 |
| LogoutRequestSchema | access_token | string(JWT) | ✔ |  |
|  | refresh_token | string(JWT) | ✔ |  |

## 응답/데이터 타입 요약

| 엔드포인트 | 2xx 응답 | 타입 | 비고 |
|---|---|---|---|
| POST /social | { access_token, refresh_token, user_id, is_new_user, user_info{ user_id,email,nickname,profile_image_url } } | object | user_id: UUID, profile_image_url: URL|null |
| POST /token/refresh | { access_token } | object |  |
| POST /logout | { message } | object |  |

## 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| /social | 401 INVALID_AUTH_CODE | 코드 교환 실패 |
|  | 500 INTERNAL_SERVER_ERROR | 서버 오류 |
| /token/refresh | - | 데코레이터에서 Refresh 검증 처리 |
| /logout | 400 VALIDATION_ERROR | 스키마 검증 실패 |
|  | 422 INVALID_TOKEN | 디코드 실패 |
|  | 500 LOGOUT_FAILED | 서버 오류 |

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | INVALID_AUTH_CODE | 유효하지 않은 인증 코드입니다. |
| 400 | VALIDATION_ERROR | 요청 형식이 올바르지 않습니다. |
| 422 | INVALID_TOKEN | 유효하지 않은 토큰입니다. |
| 500 | INTERNAL_SERVER_ERROR/LOGOUT_FAILED | 서버 내부 오류가 발생했습니다. |

## 저장/검증 로직

| 단계 | 내용 |
|---|---|
| 1 | GoogleAuthService로 userinfo 조회 → users upsert |
| 2 | 신규: user_id(UUID), google_id(sub), email, nickname, join_date(UTC) 저장 |
| 3 | 로그아웃: JWT 디코드 → jti/exp 추출 → revoked_tokens {revoked_at, expires_at} 저장 |
