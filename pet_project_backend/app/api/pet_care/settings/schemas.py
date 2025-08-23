# app/api/pet_care/settings/schemas.py
from marshmallow import Schema, fields, validate

class PetCareSettingsSchema(Schema):
    """
    펫케어 설정 조회, 수정 및 생성을 위한 스키마.
    """
    goalWeight = fields.Float(required=True, validate=validate.Range(min=0.1))
    waterBowlCapacity = fields.Int(required=True, validate=validate.Range(min=1))
    waterIncrementAmount = fields.Int(required=True, validate=validate.Range(min=1))
    goalActivityMinutes = fields.Int(required=True, validate=validate.Range(min=0))
    activityIncrementMinutes = fields.Int(required=True, validate=validate.Range(min=1))
    goalMealCount = fields.Int(required=True, validate=validate.Range(min=1))
    mealIncrementCount = fields.Int(required=True, validate=validate.Range(min=1))
    
    # 응답에만 포함될 필드
    pet_id = fields.Str(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)