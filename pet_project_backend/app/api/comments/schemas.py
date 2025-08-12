# app/api/comments/schemas.py
from marshmallow import Schema, fields, validate
from app.api.posts.schemas import AuthorSchema # 작성자 정보는 게시글 스키마의 것을 재사용

class CommentCreateSchema(Schema):
    """
    POST /api/posts/{post_id}/comments
    댓글 생성을 요청할 때의 데이터 형식을 정의하고 유효성을 검사합니다.
    """
    text = fields.Str(required=True, validate=validate.Length(min=1, max=1000, error="댓글은 1~1000자 사이여야 합니다."))

class CommentResponseSchema(Schema):
    """
    댓글 정보 응답을 위한 최종 JSON 형식을 정의합니다.
    """
    comment_id = fields.Str(required=True)
    post_id = fields.Str(required=True)
    author = fields.Nested(AuthorSchema, required=True)
    text = fields.Str(required=True)
    like_count = fields.Int(required=True)
    created_at = fields.DateTime(required=True)
    
    # 서비스 로직에서 채워주는 응답 전용 필드
    is_liked = fields.Bool(dump_only=True, dump_default=False)