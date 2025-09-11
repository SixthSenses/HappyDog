# app/api/users/schemas.py
from marshmallow import Schema, fields
from marshmallow import validates, ValidationError
import uuid

class UserPublicResponseSchema(Schema):
    """
    GET /api/users/{user_id}
    다른 사용자의 프로필 정보를 응답할 때 사용하는 스키마.
    민감한 정보(예: email, google_id, fcm_token)는 제외하고
    공개 가능한 정보만 포함하여 반환하도록 정의합니다.
    프로필 이미지는 Pet 정보에서 가져오도록 변경됨.
    """
    user_id = fields.Str(required=True, dump_only=True)
    nickname = fields.Str(required=True)
    post_count = fields.Int(required=True)

class FCMTokenSchema(Schema):
    """
    POST /api/users/me/fcm-token
    FCM 토큰 등록/업데이트 요청 본문의 유효성을 검사하는 스키마.
    """
    fcm_token = fields.Str(required=True, error_messages={"required": "fcm_token은 필수 항목입니다."})

class NotificationPreferencesSchema(Schema):
    """유저 알림 개인 설정 스키마."""
    mode = fields.Str(required=False, allow_none=True)
    # 타입별 on/off. 키는 NotificationType의 문자열 값 사용을 권장
    types = fields.Dict(keys=fields.Str(), values=fields.Bool(), required=False)


## Deprecated schema removed: SelectedPetUpdateSchema