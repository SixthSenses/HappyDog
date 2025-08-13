# app/api/cartoon_jobs/schemas.py
from marshmallow import Schema, fields, validate

class CartoonJobCreateSchema(Schema):
    """
    POST /api/cartoon-jobs
    만화 생성을 요청할 때의 데이터 형식을 정의하고 유효성을 검사합니다.
    """
    image_url = fields.URL(required=True, error_messages={"required": "만화를 생성할 이미지 URL은 필수입니다."})

class CartoonJobResponseSchema(Schema):
    """
    만화 생성 작업 정보 응답을 위한 최종 JSON 형식을 정의합니다.
    (생성, 조회, 취소 시 모두 이 스키마를 사용)
    """
    job_id = fields.Str(required=True)
    user_id = fields.Str(required=True)
    status = fields.Str(required=True)
    original_image_url = fields.URL(required=True)
    result_image_url = fields.URL(allow_none=True)
    error_message = fields.Str(allow_none=True)
    created_at = fields.DateTime(required=True)
    updated_at = fields.DateTime(required=True)