# app/api/pets/schemas.py
from marshmallow import Schema, fields, validate, post_load
from app.models.pet import PetGender

class PetSchema(Schema):
    """
    반려동물 데이터의 유효성 검사 및 직렬화/역직렬화를 위한 스키마.
    """
    pet_id = fields.Str(dump_only=True)
    user_id = fields.Str(dump_only=True)
    
    name = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    gender = fields.Str(required=True, validate=validate.OneOf([e.value for e in PetGender]))
    breed = fields.Str(required=True, validate=validate.Length(min=1, max=30))
    birthdate = fields.Date(required=True, format="%Y-%m-%d")
    fur_color = fields.Str(required=True)
    health_concerns = fields.List(fields.Str(), required=False)
    
    #is_verified = fields.Bool(dump_only=True)
    nose_print_url = fields.Str(dump_only=True, allow_none=True)
    faiss_id = fields.Int(dump_only=True, allow_none=True)

class PetUpdateSchema(Schema):
    """
    반려동물 정보의 부분 수정을 위한 스키마 (모든 필드 선택 사항).
    """
    name = fields.Str(required=False, validate=validate.Length(min=1, max=20))
    gender = fields.Str(required=False, validate=validate.OneOf([e.value for e in PetGender]))
    breed = fields.Str(required=False, validate=validate.Length(min=1, max=30))
    birthdate = fields.Date(required=False, format="%Y-%m-%d")
    fur_color = fields.Str(required=False)
    health_concerns = fields.List(fields.Str(), required=False)
class EyeAnalysisResponseSchema(Schema):
    """
    안구 분석 API의 최종 응답 형식을 정의하는 스키마.
    """
    analysis_id = fields.Str(required=True)
    disease_name = fields.Str(required=True)
    probability = fields.Method("format_probability", required=True)

    def format_probability(self, obj: dict) -> str:
        """서비스 계층에서 받은 float 확률값을 퍼센트 문자열로 포맷팅합니다."""
        prob_value = obj.get("probability", 0.0)
        return f"{prob_value:.2%}"