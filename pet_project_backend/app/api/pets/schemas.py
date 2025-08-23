# app/api/pets/schemas.py
from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from flask import current_app
from app.models.pet import PetGender

def validate_breed_exists(value):
    """BreedService를 통해 품종의 존재 여부를 실시간으로 검증합니다."""
    breed_service = current_app.services.get('breeds')
    if not breed_service or not breed_service.breed_exists(value):
        raise ValidationError(f"'{value}'은(는) 데이터베이스에 존재하지 않는 품종입니다.")

class PetRegistrationSchema(Schema):
    """POST /api/pets/ 최초 반려동물 등록 요청 스키마."""
    name = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    gender = fields.Str(required=True, validate=validate.OneOf([e.value for e in PetGender]))
    breed = fields.Str(required=True, validate=[validate.Length(min=1, max=30), validate_breed_exists])
    birthdate = fields.Date(required=True, format="%Y-%m-%d")
    current_weight = fields.Float(required=True, validate=validate.Range(min=0.1, max=200.0))
    fur_color = fields.Str(required=False, allow_none=True)
    health_concerns = fields.List(fields.Str(), required=False, allow_none=True)

class PetUpdateSchema(Schema):
    """PATCH /api/pets/<pet_id> 정보 수정을 위한 스키마 (부분 업데이트용)."""
    name = fields.Str(validate=validate.Length(min=1, max=20))
    fur_color = fields.Str()
    health_concerns = fields.List(fields.Str())

class BiometricAnalysisRequestSchema(Schema):
    """비문 및 안구 분석 요청을 위한 공통 스키마."""
    file_path = fields.Str(required=True, error_messages={"required": "GCS에 업로드된 파일 경로(file_path)는 필수입니다."})

class PetProfileResponseSchema(Schema):
    """소유자 전용 프로필 정보 응답 스키마 (모든 정보 포함)."""
    pet_id = fields.Str(dump_only=True)
    user_id = fields.Str(dump_only=True)
    name = fields.Str()
    gender = fields.Str()
    breed = fields.Str()
    birthdate = fields.Date()
    initial_weight = fields.Float()
    fur_color = fields.Str(allow_none=True)
    health_concerns = fields.List(fields.Str())
    is_verified = fields.Bool()
    nose_print_url = fields.URL(allow_none=True)
    faiss_id = fields.Int(allow_none=True)

class PetPublicProfileResponseSchema(Schema):
    """멍스타그램 등 공개용 프로필 조회 시 사용할 응답 스키마 (민감 정보 제외)."""
    pet_id = fields.Str(dump_only=True)
    name = fields.Str()
    gender = fields.Str()
    breed = fields.Str()
    birthdate = fields.Date()
    initial_weight = fields.Float()
    fur_color = fields.Str(allow_none=True)
    is_verified = fields.Bool()

class EyeAnalysisResponseSchema(Schema):
    """안구 분석 결과 응답 스키마."""
    analysis_id = fields.Str(required=True)
    disease_name = fields.Str(required=True)
    probability = fields.Float(required=True)