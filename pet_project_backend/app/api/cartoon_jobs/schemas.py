# app/api/cartoon_jobs/schemas.py
from marshmallow import Schema, fields, validate

class CartoonJobCreateSchema(Schema):
    """
    POST /api/cartoon-jobs
    만화 생성을 요청할 때의 데이터 형식을 정의하고 유효성을 검사합니다.
    """
    file_paths = fields.List(
        fields.URL(), 
        required=True, 
        validate=validate.Length(min=1, max=1),
        error_messages={
            "required": "만화를 생성할 이미지는 필수입니다.",
            "min": "이미지가 최소 1장 필요합니다.",
            "max": "만화 생성은 이미지 1장만 지원합니다."
        }
    )
    user_text = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500), 
                          error_messages={"max": "텍스트는 500자를 초과할 수 없습니다."})

class CartoonJobResponseSchema(Schema):
    """
    만화 생성 작업 정보 응답을 위한 최종 JSON 형식을 정의합니다.
    (생성, 조회, 취소 시 모두 이 스키마를 사용)
    """
    job_id = fields.Str(required=True)
    user_id = fields.Str(required=True)
    status = fields.Str(required=True)
    original_image_url = fields.URL(required=True)
    user_text = fields.Str(allow_none=True)
    result_image_url = fields.URL(allow_none=True)
    error_message = fields.Str(allow_none=True)
    created_at = fields.DateTime(required=True)
    updated_at = fields.DateTime(required=True)