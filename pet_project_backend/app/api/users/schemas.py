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


class UserMeResponseSchema(Schema):
    """GET /api/users/me 응답.

    내 기본 정보 (민감정보 제외) 및 보조 상태(has_pet/pet_id) 포함.
    """
    user_id = fields.Str(required=True)
    nickname = fields.Str(required=True)
    email = fields.Email(required=True)
    has_pet = fields.Bool(required=False)
    pet_id = fields.Str(required=False, allow_none=True)


class UserSummaryUserSchema(Schema):
    """요약 응답 중 user 부분 (post_count 등 추가 필드 포함 가능)."""
    user_id = fields.Str(required=True)
    nickname = fields.Str(required=True)
    post_count = fields.Int(required=False)


class UserSummaryPetSchema(Schema):
    """요약 응답 중 pet 부분 (단일 반려동물 정책)."""
    pet_id = fields.Str(required=True)
    name = fields.Str(required=True)
    breed = fields.Str(required=True)
    profile_image_url = fields.URL(required=False, allow_none=True)
    is_verified = fields.Bool(required=False)


class UserSummaryResponseSchema(Schema):
    """GET /api/users/me/summary 응답.

    user / pet / pet_care_settings (옵셔널) 통합 구조.
    pet_care_settings는 동적 dict 로 덤프.
    """
    user = fields.Nested(UserSummaryUserSchema, required=True)
    pet = fields.Nested(UserSummaryPetSchema, required=False, allow_none=True)
    pet_care_settings = fields.Dict(required=False, allow_none=True)


class NotificationPreferencesResponseSchema(Schema):
    """알림 설정 조회/수정 결과 응답 스키마 (GET/PUT 공용)."""
    mode = fields.Str(required=False, allow_none=True)
    types = fields.Dict(keys=fields.Str(), values=fields.Bool(), required=False)


class FCMTokenUpdateResponseSchema(Schema):
    """FCM 토큰 업데이트 결과 메시지."""
    message = fields.Str(required=True)