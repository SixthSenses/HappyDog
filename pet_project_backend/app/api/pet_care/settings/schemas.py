# app/api/pet_care/settings/schemas.py
from marshmallow import Schema, fields, validate

class PetCareSettingsSchema(Schema):
    """
    펫케어 설정 조회, 수정 및 생성을 위한 스키마.
    """
    # 기본값/최대값 정책
    # - goalWeight: kg 단위, 0.1~200.0
    # - waterBowlCapacity: ml 단위, 1~5000
    # - waterIncrementAmount: ml 단위, 1~1000
    # - goalActivityMinutes: 분, 0~1440
    # - activityIncrementMinutes: 분, 1~180
    # - goalMealCount: 회, 1~10
    # - mealIncrementCount: 회, 1~5
    goalWeight = fields.Float(required=True, validate=validate.Range(min=0.1, max=200.0))
    waterBowlCapacity = fields.Int(required=True, validate=validate.Range(min=1, max=5000))
    waterIncrementAmount = fields.Int(required=True, validate=validate.Range(min=1, max=1000))
    goalActivityMinutes = fields.Int(required=True, validate=validate.Range(min=0, max=1440))
    activityIncrementMinutes = fields.Int(required=True, validate=validate.Range(min=1, max=180))
    goalMealCount = fields.Int(required=True, validate=validate.Range(min=1, max=10))
    mealIncrementCount = fields.Int(required=True, validate=validate.Range(min=1, max=5))
    
    # 응답에만 포함될 필드
    pet_id = fields.Str(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)