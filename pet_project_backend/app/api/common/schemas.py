from marshmallow import Schema, fields


class ErrorResponseSchema(Schema):
    error_code = fields.String(required=True)
    category = fields.String(required=True)
    retriable = fields.Boolean(required=True)
    message = fields.String(required=False)
    details = fields.Dict(required=False)


class EmptyRequestSchema(Schema):
    """바디가 없는 요청(POST/PUT/PATCH)도 명시적으로 문서화하기 위한 placeholder."""
    pass


class NoContentSchema(Schema):
    """204 No Content 응답 본문 없음 표시 placeholder."""
    pass


class HealthStatusResponseSchema(Schema):
    status = fields.String(required=True)
    counters = fields.Dict(required=True)
