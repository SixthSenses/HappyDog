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
    # weight 필드는 Pet 정체성 모델에서 제거되었습니다.
    fur_color = fields.Str(required=False, allow_none=True)
    health_concerns = fields.List(fields.Str(), required=False, allow_none=True)
    profile_image_url = fields.Str(required=False, allow_none=True)  # 프로필 이미지 URL

class PetUpdateSchema(Schema):
    """PATCH /api/pets/<pet_id> 정보 수정을 위한 스키마 (부분 업데이트용)."""
    name = fields.Str(validate=validate.Length(min=1, max=20))
    fur_color = fields.Str()
    health_concerns = fields.List(fields.Str())
    profile_image_url = fields.Str(allow_none=True)  # 프로필 이미지 URL

class BiometricAnalysisRequestSchema(Schema):
    """비문 및 안구 분석 요청을 위한 공통 스키마."""
    file_path = fields.Str(required=True, error_messages={"required": "GCS에 업로드된 파일 경로(file_path)는 필수입니다."})

class PetProfileResponseSchema(Schema):
    """소유자 전용 프로필 정보 응답 스키마 (모든 정보 포함)."""
    pet_id = fields.Str(dump_only=True)
    user_id = fields.Str(dump_only=True)
    name = fields.Str()
    gender = fields.Str(validate=validate.OneOf([e.value for e in PetGender]))
    breed = fields.Str()
    birthdate = fields.Date()
    # weight 관련 필드 제거됨
    fur_color = fields.Str(allow_none=True)
    health_concerns = fields.List(fields.Str())
    is_verified = fields.Bool()
    profile_image_url = fields.Str(allow_none=True)  # 프로필 이미지 URL
    nose_print_url = fields.URL(allow_none=True)     # 비문 인증용 URL
    faiss_id = fields.Int(allow_none=True)

## Deprecated: PetPublicProfileResponseSchema 제거 (PR4 정리)

class PetViewBasedResponseSchema(Schema):
    """뷰 기반 필터링이 적용된 Pet 프로필 응답 스키마."""
    # 기본 정보 (모든 뷰에서 사용)
    pet_id = fields.Str(dump_only=True)
    name = fields.Str(required=True)
    profile_image_url = fields.Str(allow_none=True)
    is_verified = fields.Bool(required=True)
    
    # 마이페이지/멍스타그램 전용
    birthdate = fields.Date(allow_none=True)
    gender = fields.Str(allow_none=True, validate=validate.OneOf([e.value for e in PetGender])) 
    breed = fields.Str(allow_none=True)
    
    # 멍스타그램 전용 (나이 계산된 값)
    age_months = fields.Int(allow_none=True)
    post_count = fields.Int(allow_none=True)

    # 입력 gender 값이 소문자여도 Enum 대문자 값으로 정규화
    @staticmethod
    def _normalize_gender(value: str) -> str:
        if isinstance(value, str):
            upper = value.upper()
            if upper in [e.value for e in PetGender]:
                return upper
        return value

from marshmallow import pre_load

class _GenderNormalizeMixin:
    @pre_load
    def normalize_gender(self, data, **kwargs):
        g = data.get('gender')
        if isinstance(g, str):
            upper = g.upper()
            if upper in [e.value for e in PetGender]:
                data['gender'] = upper
        return data

# 적용을 위해 기존 Registration/Update 스키마 상속 구조 간단히 재정의
class PetRegistrationSchema(_GenderNormalizeMixin, PetRegistrationSchema):
    pass
class PetUpdateSchema(_GenderNormalizeMixin, PetUpdateSchema):
    pass

class EyeAnalysisResponseSchema(Schema):
    """안구 분석 결과 응답 스키마."""
    analysis_id = fields.Str(required=True)
    disease_name = fields.Str(required=True)
    probability = fields.Float(required=True)
    image_url = fields.Str(allow_none=True)

class NosePrintRegistrationResponseSchema(Schema):
    """비문(코) 등록/인증 결과 응답 스키마."""
    success = fields.Bool(required=True)
    confidence = fields.Float(allow_none=True)
    features = fields.Raw(allow_none=True)
    analysis_id = fields.Str(allow_none=True)
    metadata = fields.Dict(allow_none=True)
    status = fields.Str(allow_none=True)