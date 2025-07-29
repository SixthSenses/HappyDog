#에시 코드입니다.
from marshmallow import Schema, fields

class UserSchema(Schema):
    """User 데이터의 직렬화를 위한 스키마"""
    id = fields.Str(dump_only=True)
    google_id = fields.Str(dump_only=True)
    email = fields.Email(dump_only=True)
    name = fields.Str(dump_only=True)
    picture = fields.URL(dump_only=True)
    created_at = fields.DateTime(dump_only=True)