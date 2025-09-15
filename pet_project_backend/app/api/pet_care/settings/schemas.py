# app/api/pet_care/settings/schemas.py
from marshmallow import Schema, fields, validate

class PetCareSettingsSchema(Schema):
    """
    펫케어 설정 조회, 수정 및 생성을 위한 스키마.
    사용자가 설정할 수 있는 기본 목표값들을 관리합니다.
    """
    # 하루 기본 식사횟수
    daily_meal_count = fields.Int(required=True, validate=validate.Range(min=1, max=10))
    
    # 하루 목표 식사횟수 
    target_daily_meal_count = fields.Int(required=True, validate=validate.Range(min=1, max=10))
    
    # 하루 목표 활동량 (분)
    target_daily_activity_minutes = fields.Int(required=True, validate=validate.Range(min=0, max=1440))
    
    # 하루 목표 활동량 증감 (분)
    daily_activity_increment = fields.Int(required=True, validate=validate.Range(min=1, max=180))
    
    # 목표 몸무게 (kg)
    target_weight = fields.Float(required=True, validate=validate.Range(min=0.1, max=200.0))
    
    # 응답에만 포함될 필드
    pet_id = fields.Str(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)