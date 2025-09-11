# auth API

이 문서는 인증(auth) 도메인 API를 요약합니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/auth/social | - | 소셜 로그인/회원가입 처리 (Google 코드 교환 → 토큰 발급) | 200, 401, 500 |
| POST | /api/auth/token/refresh | Refresh JWT | Refresh 토큰으로 Access 토큰 재발급 | 200 |
| POST | /api/auth/logout | Access/Refresh JWT | 전달된 access/refresh JWT 블랙리스트 처리(서버 로그아웃) | 200, 400, 422, 500 |
# auth API

최신 구현 기준 인증(auth) 도메인 API 요약. (swagger 예시는 무시함)

## 1. 엔드포인트 개요

| Method | Path | 인증 요구 | 설명 | 비고 |
|--------|------|----------|------|------|
| GET | /api/auth/google/authorize | - | Google OAuth 인증 URL 발급 또는 즉시 리다이렉트 | redirect 파라미터 지원 |
| POST | /api/auth/social | - | Google OAuth code 교환 → 로그인/회원가입 | 모바일/백엔드 직접 코드 교환 |
| GET | /api/auth/social | - | 브라우저 콜백(code 쿼리) 처리 | 웹 리다이렉트 플로우 |
| POST | /api/auth/token/refresh | Refresh JWT | 새 Access 토큰 발급 | @jwt_required(refresh=True) |
| POST | /api/auth/logout | - | Access/Refresh 토큰 블랙리스트 처리 | 본문에 두 토큰 모두 필요 |

## 2. 요청 스키마

### 2.1 SocialLoginSchema (POST /api/auth/social)
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| provider | string | ✔ | 현재 'google'만 지원 (확장 대비) |
| auth_code | string | ✔ | Google OAuth 인증 코드 (Authorization Code Grant) |

### 2.2 LogoutRequestSchema (POST /api/auth/logout)
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| access_token | string(JWT) | ✔ | 기존 발급 Access JWT (만료 가능) |
| refresh_token | string(JWT) | ✔ | 기존 발급 Refresh JWT (만료 가능) |

Refresh 토큰 재발급 요청(POST /api/auth/token/refresh)은 별도 본문 필요 없음. Authorization 헤더: `Bearer <refresh_token>`.

## 3. 응답 구조

### 3.1 성공 응답
| 엔드포인트 | 응답 JSON 필드 | 설명 |
|-----------|----------------|------|
| POST /social, GET /social | access_token, refresh_token, user_id, is_new_user, user_info{ user_id,email,nickname } | 최초/기존 사용자 공통 |
| POST /token/refresh | access_token | 새 Access JWT |
| POST /logout | message | 로그아웃 완료 메시지 |
| GET /google/authorize | authorization_url, redirect_uri, state | redirect=false(default) 시 JSON 반환 |

user_info.profile_image_url 은 현재 반환하지 않음 (Pet 프로필 분리 정책 반영).

### 3.2 사용자 생성/조회 내부 저장 필드(요약)
| 필드 | 내용 |
|------|------|
| user_id | 내부 UUID (identity) |
| google_id | Google sub 값 |
| email | 사용자 이메일 |
| nickname | 최초 생성 시 파생 또는 기본값 |
| join_date | UTC 기준 가입 시각 |

## 4. 오류 코드 / 처리

실제 코드에서 사용하는 오류 Enum 기준.

| 상황 | HTTP | error_code | 메시지(영문 기본) | 비고 |
|------|------|-----------|-------------------|------|
| 소셜 코드 무효 | 401 | INVALID_SOCIAL_TOKEN | Social login token is invalid. | code 교환 실패/토큰 검증 실패 |
| client secrets 미설정 | 500 | MISSING_CLIENT_SECRETS | Google client secrets not configured. | 환경 설정 누락 |
| Refresh 토큰 문제 | 401 | TOKEN_REFRESH_FAILED | Failed to refresh access token. | 데코레이터 내부/블록리스트 |
| Logout 처리 실패 | 400 | LOGOUT_FAILED | Failed to process logout request. | 내부 로직 실패 |
| JWT 미제공 | 401 | MISSING_JWT | Authentication token is required. | 헤더 누락 |
| JWT 무효/만료 | 401 | INVALID_JWT | The provided JWT is invalid or has expired. | 서명/만료/블록 |
| 검증 실패 | 400 | VALIDATION_ERROR | Request validation failed. | marshmallow 스키마 오류 |
| 내부 오류 | 500 | INTERNAL_ERROR | An unexpected error occurred on the server. | 포괄적 예외 |

추가: 로그아웃 시 invalid token 구조적 오류 발생 시 FORBIDDEN(코드 내 build_error('FORBIDDEN')) 활용 가능 (정규화 예정).

## 5. 플로우 요약.

### 5.1 모바일/백엔드 직접 코드 교환
1. 클라이언트가 Google OAuth 동의 → auth_code 획득
2. POST /api/auth/social { provider, auth_code }
3. 서버: GoogleAuthService.exchange_code_for_user_info → userinfo
4. users 컬렉션 upsert (신규시 is_new_user=true)
5. Access / Refresh JWT 생성 반환

### 5.2 웹 리다이렉트 플로우
1. GET /api/auth/google/authorize 호출 (redirect=true) → 302 Google
2. 사용자가 동의 → redirect_uri (서버 설정) 로 code 전달
3. GET /api/auth/social?code=... 처리 → 동일한 토큰/응답 반환

### 5.3 토큰 재발급
1. Authorization: Bearer <refresh_jwt>
2. POST /api/auth/token/refresh → 새 access_token

### 5.4 로그아웃
1. POST /api/auth/logout { access_token, refresh_token }
2. 두 토큰 decode(verify_exp=False) → jti / exp 추출
3. Blocklist(or revoked_tokens) 저장 → 이후 접근 차단

## 6. 보안 & 모범 사례
- Refresh 토큰은 httpOnly/secure 쿠키 또는 안전한 저장소에 보관 권장.
- Access 토큰 짧은 수명 유지 (설정에서 TTL 조정).
- 로그아웃은 만료된 토큰도 수용(verify_exp=False)하여 블랙리스트 정합성 유지.
- client secrets 누락 시 조기 실패(MISSING_CLIENT_SECRETS) 로그 남김.
- 추후 다중 소셜(provider 확장) 시 SocialLoginSchema provider validate.OneOf 도입 권장.

---
문서 갱신: 2025-09-11
