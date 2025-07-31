from marshmallow import Schema, fields, validate, post_load
from datetime import date
from app.models.pet import Pet, PetGender

class PetSchema(Schema):
    """반려동물 데이터의 유효성 검사 및 직렬화를 위한 스키마"""
    pet_id = fields.Str(dump_only=True)
    user_id = fields.Str(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    # Enum의 값(value)들을 리스트로 만들어 유효성 검사를 수행합니다.
    gender = fields.Str(required=True, validate=validate.OneOf([e.value for e in PetGender]))
    breed = fields.Str(required=True, validate=validate.Length(min=1, max=30))
    birthdate = fields.Date(required=True, format="%Y-%m-%d")
    #is_neutered = fields.Bool(required=True)
    vaccination_status = fields.Str(required=False, allow_none=True)
    is_verified = fields.Bool(dump_only=True)
    weight_response = fields.Float(attribute="weight", dump_only=True, allow_none=True)

class PetUpdateSchema(PetSchema):
    """반려동물 정보 부분 수정을 위한 스키마"""
    name = fields.Str(required=False, validate=validate.Length(min=1, max=20))
    gender = fields.Str(required=False, validate=validate.OneOf([e.value for e in PetGender]))
    breed = fields.Str(required=False, validate=validate.Length(min=1, max=30))
    birthdate = fields.Date(required=False, format="%Y-%m-%d")
    #is_neutered = fields.Bool(required=False)