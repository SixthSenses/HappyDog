# app/api/posts/schemas.py
from marshmallow import Schema, fields, validate

# --- 재사용을 위한 중첩 스키마 ---
class AuthorSchema(Schema):
    """게시물 응답에 포함될 작성자 정보 스키마."""
    user_id = fields.Str(required=True)
    nickname = fields.Str(required=True)
    profile_image_url = fields.URL(allow_none=True)

class PetInfoSchema(Schema):
    """게시물 응답에 포함될 반려동물 정보 스키마."""
    pet_id = fields.Str(required=True)
    name = fields.Str(required=True)
    breed = fields.Str(required=True)
    birthdate = fields.DateTime(required=True)

# --- API 요청/응답 스키마 ---

class PostCreateSchema(Schema):
    """POST /api/posts 요청 본문의 유효성을 검사합니다."""
    text = fields.Str(required=True, validate=validate.Length(min=1, max=2000))
    file_paths = fields.List(fields.Str(), required=True, validate=validate.Length(min=1))

class PostUpdateSchema(Schema):
    """PATCH /api/posts/{post_id} 요청 본문의 유효성을 검사합니다."""
    text = fields.Str(required=True, validate=validate.Length(min=1, max=2000))

class PostResponseSchema(Schema):
    """게시글 정보 응답을 위한 최종 JSON 형식을 정의합니다."""
    post_id = fields.Str(dump_only=True)
    author = fields.Nested(AuthorSchema, required=True)
    pet = fields.Nested(PetInfoSchema, required=True)
    image_urls = fields.List(fields.URL(), required=True)
    text = fields.Str(required=True)
    like_count = fields.Int(required=True)
    comment_count = fields.Int(required=True)
    created_at = fields.DateTime(required=True)
    updated_at = fields.DateTime(required=True)
    is_liked = fields.Bool(dump_only=True, dump_default=False)