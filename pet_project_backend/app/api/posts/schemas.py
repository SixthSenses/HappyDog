# app/api/posts/schemas.py
from marshmallow import Schema, fields, validate
from app.api.common.schemas import EmptyRequestSchema, NoContentSchema

# --- 재사용을 위한 중첩 스키마 ---
class AuthorSchema(Schema):
    """게시물 응답에 포함될 작성자 정보 스키마."""
    user_id = fields.Str(required=True)
    nickname = fields.Str(required=True)
    # profile_image_url는 Pet 정보에서 가져오도록 변경됨

class PetInfoSchema(Schema):
    """게시물 응답에 포함될 반려동물 정보 스키마."""
    pet_id = fields.Str(required=True)
    name = fields.Str(required=True)
    breed = fields.Str(required=True)
    birthdate = fields.DateTime(required=True, format="iso8601")
    profile_image_url = fields.URL(allow_none=True)  # Pet 프로필 이미지 추가

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
    created_at = fields.DateTime(required=True, format="iso8601")
    updated_at = fields.DateTime(required=True, format="iso8601")
    is_liked = fields.Bool(dump_only=True, dump_default=False)


class PostsFeedResponseSchema(Schema):
    """피드/사용자별 게시글 목록 응답 래퍼.

    GET /api/posts, GET /api/posts/users/{author_id}/posts 에서 사용.
    posts 배열과 다음 페이지 커서가 포함됩니다.
    """
    posts = fields.List(fields.Nested(PostResponseSchema), required=True)
    next_cursor = fields.Str(allow_none=True)


class PostLikeToggleResponseSchema(Schema):
    """POST /api/posts/{post_id}/like 좋아요 토글 결과.

    단순 메시지 필드만을 포함합니다.
    """
    message = fields.Str(required=True)

