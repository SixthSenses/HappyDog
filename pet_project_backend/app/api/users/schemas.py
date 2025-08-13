# app/api/users/schemas.py
from marshmallow import Schema, fields

class UserPublicResponseSchema(Schema):
    """
    GET /api/users/{user_id}
    다른 사용자의 프로필 정보를 응답할 때 사용하는 스키마.
    민감한 정보(예: email, google_id, fcm_token)는 제외하고
    공개 가능한 정보만 포함하여 반환하도록 정의합니다.
    """
    user_id = fields.Str(required=True, dump_only=True)
    nickname = fields.Str(required=True)
    profile_image_url = fields.URL(allow_none=True)
    post_count = fields.Int(required=True)

class FCMTokenSchema(Schema):
    """
    POST /api/users/me/fcm-token
    FCM 토큰 등록/업데이트 요청 본문의 유효성을 검사하는 스키마.
    """
    fcm_token = fields.Str(required=True, error_messages={"required": "fcm_token은 필수 항목입니다."})