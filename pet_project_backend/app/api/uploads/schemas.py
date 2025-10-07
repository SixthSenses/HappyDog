"""Schemas for uploads domain.

Option A 정렬: storage_service.path_map 과 1:1 매칭되는 canonical 타입만 허용.
Deprecated alias 는 라우트 단계에서 canonical 로 변환 후 검증.
"""
from marshmallow import Schema, fields, validate

# Canonical upload types (실제 storage_service.generate_upload_url path_map 기준)
ALLOWED_UPLOAD_TYPES = [
    'pet_profile',         # Pet 프로필 이미지
    'pet_nose_print',      # 비문 분석 원본 (staging)
    'eye_analysis',        # 안구 분석 이미지
    'post_image',          # 게시글 이미지
    'cartoon_source_image' # 만화 변환 원본
]

# Deprecated aliases (라우트에서만 사용, 스키마에는 포함하지 않음)
DEPRECATED_UPLOAD_TYPE_ALIASES = {
    'profile_image': 'pet_profile',
    'cartoon_source': 'cartoon_source_image',
    # 'cartoon_result' 는 클라이언트 직접 업로드 필요 없으므로 제거
}


class UploadUrlRequestSchema(Schema):
    upload_type = fields.Str(required=True, validate=validate.OneOf(ALLOWED_UPLOAD_TYPES))  # alias 변환 후 값
    filename = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    content_type = fields.Str(required=True, validate=validate.Length(min=3, max=120))


class FinalizeCartoonRequestSchema(Schema):
    file_path = fields.Str(required=True, error_messages={"required": "file_path는 필수입니다."})


class UploadUrlResponseSchema(Schema):
    """업로드 URL 발급 응답."""
    upload_url = fields.URL(required=True)
    file_path = fields.Str(required=True)
    expires_at = fields.DateTime(required=True, format="iso8601")


class FinalizeCartoonResponseSchema(Schema):
    """만화 원본 공개 전환 응답."""
    public_url = fields.URL(required=True)


__all__ = [
    'UploadUrlRequestSchema',
    'FinalizeCartoonRequestSchema',
    'UploadUrlResponseSchema',
    'FinalizeCartoonResponseSchema',
    'ALLOWED_UPLOAD_TYPES',
    'DEPRECATED_UPLOAD_TYPE_ALIASES'
]
