# app/api/pets/schemas.py
from marshmallow import Schema, fields, validate, post_load, validates
from marshmallow.exceptions import ValidationError
from app.models.pet import PetGender, ActivityLevel, DietType

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
    
    # 펫케어 기능을 위한 추가 필드들
    activity_level = fields.Str(required=False, allow_none=True, 
                               validate=validate.OneOf([e.value for e in ActivityLevel]))
    diet_type = fields.Str(required=False, allow_none=True,
                          validate=validate.OneOf([e.value for e in DietType]))
    is_neutered = fields.Bool(required=False, allow_none=True)
    current_weight = fields.Float(required=False, allow_none=True, 
                                 validate=validate.Range(min=0.1, max=200.0))
    care_settings = fields.Dict(required=False, allow_none=True)
    
    #is_verified = fields.Bool(dump_only=True)
    nose_print_url = fields.Str(dump_only=True, allow_none=True)
    faiss_id = fields.Int(dump_only=True, allow_none=True)
    
    @validates('breed')
    def validate_breed(self, value):
        """품종 유효성 검사 - Firestore에서 품종 존재 여부 확인"""
        from app.api.breeds.services import BreedService
        
        if not value or not value.strip():
            raise ValidationError("품종명은 필수입니다.")
        
        # Firestore에서 품종 존재 여부 확인
        try:
            breed_service = BreedService()
            if not breed_service.breed_exists(value.strip()):
                raise ValidationError(f"존재하지 않는 품종입니다: {value}")
        except Exception as e:
            # 품종 서비스 오류 시 경고 로그만 남기고 통과
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"품종 유효성 검사 중 오류 발생: {e}")
        
        return value

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