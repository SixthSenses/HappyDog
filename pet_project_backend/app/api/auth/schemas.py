#app/api/auth/schemas.py
from marshmallow import Schema, fields

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