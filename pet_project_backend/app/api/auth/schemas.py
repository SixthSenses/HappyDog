#app/api/auth/schemas.py
from marshmallow import Schema, fields, validate

class SocialLoginSchema(Schema):
    """소셜 로그인 요청의 유효성을 검사하는 스키마"""
    # provider: 소셜 로그인 제공자. 현재는 'google'만 허용합니다. (확장성 고려)
    provider = fields.Str(
        required=True, 
        metadata={"description": "소셜 로그인 제공자 (e.g., google)"}
    )
    auth_code = fields.Str(
        required=True, 
        metadata={"description": "Google OAuth 2.0 인증 코드"}
    )
    
class LogoutRequestSchema(Schema):
    """로그아웃 요청의 유효성을 검사하는 스키마"""
    access_token = fields.Str(required=True)
    refresh_token = fields.Str(required=True)


class AuthorizationUrlResponseSchema(Schema):
    """GET /api/auth/google/authorize 응답 스키마"""
    authorization_url = fields.Url(required=True)
    redirect_uri = fields.Url(required=True)
    state = fields.Str(required=True)


class AuthUserInfoSchema(Schema):
    """토큰 발급 시 함께 반환되는 사용자 요약 정보"""
    user_id = fields.Str(required=True)
    email = fields.Email(required=True)
    nickname = fields.Str(required=True)


class AuthTokensResponseSchema(Schema):
    """소셜 로그인/콜백 성공 시 토큰/유저 정보."""
    access_token = fields.Str(required=True)
    refresh_token = fields.Str(required=True)
    user_id = fields.Str(required=True)
    is_new_user = fields.Boolean(required=True)
    user_info = fields.Nested(AuthUserInfoSchema, required=True)


class AuthTokensRefreshResponseSchema(Schema):
    """토큰 재발급 응답 (새 access_token)."""
    access_token = fields.Str(required=True)


class AuthLogoutResponseSchema(Schema):
    """로그아웃 응답."""
    message = fields.Str(required=True)