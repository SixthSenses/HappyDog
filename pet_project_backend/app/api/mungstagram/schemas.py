# app/api/mungstagram/schemas.py
from marshmallow import Schema, fields, validate

# --- 중첩 스키마 ---
class AuthorSchema(Schema):
    """게시물 응답에 포함될 작성자 정보 스키마."""
    user_id = fields.Str(required=True)
    nickname = fields.Str(required=True)
    profile_image_url = fields.Str(allow_none=True)

class PetInfoSchema(Schema):
    """게시물 응답에 포함될 반려동물 정보 스키마."""
    pet_id = fields.Str(required=True)
    name = fields.Str(required=True)
    breed = fields.Str(required=True)
    birthdate = fields.DateTime(required=True)

# --- API 요청/응답 스키마 ---
class PostCreateSchema(Schema):
    """POST /posts 요청 본문의 유효성을 검사하는 스키마."""
    text = fields.Str(required=True, validate=validate.Length(max=2000))
    file_paths = fields.List(fields.Str(), required=True, validate=validate.Length(min=1))

class PostUpdateSchema(Schema):
    """PUT /posts/{post_id} 요청 본문의 유효성을 검사하는 스키마."""
    text = fields.Str(required=True, validate=validate.Length(max=2000))

class PostResponseSchema(Schema):
    """게시물 정보 응답을 위한 스키마."""
    post_id = fields.Str(dump_only=True)
    author = fields.Nested(AuthorSchema, required=True)
    pet = fields.Nested(PetInfoSchema, required=True)
    image_urls = fields.List(fields.Str(), required=True)
    text = fields.Str(required=True)
    like_count = fields.Int(required=True)
    comment_count = fields.Int(required=True)
    created_at = fields.DateTime(required=True)
    updated_at = fields.DateTime(required=True)

    is_liked = fields.Bool(dump_default=False)

class CartoonJobCreateSchema(Schema):
    """POST /cartoon-jobs 요청 본문의 유효성을 검사하는 스키마."""
    file_paths = fields.List(fields.Str(), required=True, validate=validate.Length(min=1))
    text = fields.Str(required=True, validate=validate.Length(max=2000))

class CartoonJobResponseSchema(Schema):
    """만화 생성 작업 정보 응답을 위한 스키마."""
    job_id = fields.Str(required=True)
    user_id = fields.Str(required=True)
    status = fields.Str(required=True)
    source_image_urls = fields.List(fields.Str(), required=True)
    source_text = fields.Str(required=True)
    result_cartoon_url = fields.Str(allow_none=True)
    created_at = fields.DateTime(required=True)
