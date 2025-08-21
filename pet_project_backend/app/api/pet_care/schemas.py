# app/api/pet_care/schemas.py
from marshmallow import Schema, fields, validate, post_load, validates_schema, ValidationError
from typing import Optional
from datetime import datetime, date

from app.models.pet_care_log import (
    FoodType, PoopShape, PoopColor, PoopSpecialNote,
    ActivityType, ActivityIntensity, VomitType
)

# 기본 로그 스키마들
class FoodLogSchema(Schema):
    """음식 섭취 로그 스키마"""
    log_id = fields.Str(dump_only=True)
    calories = fields.Float(required=True, validate=validate.Range(min=0, max=10000))
    timestamp = fields.DateTime(required=True)
    date = fields.Date(required=True, format="%Y-%m-%d")  # date 필드 추가
    food_type = fields.Str(required=True, validate=validate.OneOf([e.value for e in FoodType]))
    food_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    amount_g = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0, max=5000))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

class WaterLogSchema(Schema):
    """물 섭취 로그 스키마"""
    log_id = fields.Str(dump_only=True)
    amount_ml = fields.Float(required=True, validate=validate.Range(min=0, max=10000))
    timestamp = fields.DateTime(required=True)
    date = fields.Date(required=True, format="%Y-%m-%d")  # date 필드 추가
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

class PoopLogSchema(Schema):
    """배변 로그 스키마"""
    log_id = fields.Str(dump_only=True)
    shape = fields.Str(required=True, validate=validate.OneOf([e.value for e in PoopShape]))
    color = fields.Str(required=True, validate=validate.OneOf([e.value for e in PoopColor]))
    timestamp = fields.DateTime(required=True)
    date = fields.Date(required=True, format="%Y-%m-%d")  # date 필드 추가
    special_notes = fields.List(fields.Str(validate=validate.OneOf([e.value for e in PoopSpecialNote])), 
                               required=False, load_default=[])
    size = fields.Str(required=False, allow_none=True, validate=validate.OneOf(['작음', '보통', '큼']))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

class ActivityLogSchema(Schema):
    """활동 로그 스키마"""
    log_id = fields.Str(dump_only=True)
    duration_minutes = fields.Int(required=True, validate=validate.Range(min=1, max=1440))
    activity_type = fields.Str(required=True, validate=validate.OneOf([e.value for e in ActivityType]))
    intensity = fields.Str(required=True, validate=validate.OneOf([e.value for e in ActivityIntensity]))
    timestamp = fields.DateTime(required=True)
    date = fields.Date(required=True, format="%Y-%m-%d")  # date 필드 추가
    distance_km = fields.Float(required=False, allow_none=True, validate=validate.Range(min=0, max=100))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

class VomitLogSchema(Schema):
    """구토 로그 스키마"""
    log_id = fields.Str(dump_only=True)
    vomit_type = fields.Str(required=True, validate=validate.OneOf([e.value for e in VomitType]))
    timestamp = fields.DateTime(required=True)
    date = fields.Date(required=True, format="%Y-%m-%d")  # date 필드 추가
    amount = fields.Str(required=False, allow_none=True, validate=validate.OneOf(['적음', '보통', '많음']))
    frequency = fields.Int(required=False, load_default=1, validate=validate.Range(min=1, max=50))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

class WeightLogSchema(Schema):
    """체중 로그 스키마"""
    log_id = fields.Str(dump_only=True)
    weight_kg = fields.Float(required=True, validate=validate.Range(min=0.1, max=200))
    timestamp = fields.DateTime(required=True)
    date = fields.Date(required=True, format="%Y-%m-%d")  # date 필드 추가
    bcs_level = fields.Int(required=False, allow_none=True, validate=validate.Range(min=1, max=5))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

# 메인 펫케어 로그 스키마
class PetCareLogSchema(Schema):
    """펫케어 로그 생성/수정을 위한 스키마"""
    log_id = fields.Str(dump_only=True)
    pet_id = fields.Str(dump_only=True)
    user_id = fields.Str(dump_only=True)
    date = fields.Date(required=True, format="%Y-%m-%d")
    
    # 각종 로그 목록들
    food_logs = fields.List(fields.Nested(FoodLogSchema), required=False, load_default=[])
    water_logs = fields.List(fields.Nested(WaterLogSchema), required=False, load_default=[])
    poop_logs = fields.List(fields.Nested(PoopLogSchema), required=False, load_default=[])
    activity_logs = fields.List(fields.Nested(ActivityLogSchema), required=False, load_default=[])
    vomit_logs = fields.List(fields.Nested(VomitLogSchema), required=False, load_default=[])
    weight_logs = fields.List(fields.Nested(WeightLogSchema), required=False, load_default=[])

    
    # 하루 총합 정보 (자동 계산됨)
    total_calories = fields.Float(dump_only=True)
    total_water_ml = fields.Float(dump_only=True)
    total_activity_minutes = fields.Int(dump_only=True)
    current_weight_kg = fields.Float(dump_only=True, allow_none=True)
    
    # 메타데이터
    general_notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    mood = fields.Str(required=False, allow_none=True, validate=validate.OneOf(['좋음', '보통', '나쁨']))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class PetCareLogResponseSchema(Schema):
    """펫케어 로그 조회 응답을 위한 스키마"""
    log_id = fields.Str(required=True)
    pet_id = fields.Str(required=True)
    user_id = fields.Str(required=True)
    date = fields.Date(required=True, format="%Y-%m-%d")
    
    # 로그 개수 요약
    food_logs_count = fields.Int(required=True)
    water_logs_count = fields.Int(required=True)
    poop_logs_count = fields.Int(required=True)
    activity_logs_count = fields.Int(required=True)
    vomit_logs_count = fields.Int(required=True)
    weight_logs_count = fields.Int(required=True)

    
    # 하루 총합 정보
    total_calories = fields.Float(required=True)
    total_water_ml = fields.Float(required=True)
    total_activity_minutes = fields.Int(required=True)
    current_weight_kg = fields.Float(allow_none=True)
    
    # 메타데이터
    general_notes = fields.Str(allow_none=True)
    mood = fields.Str(allow_none=True)
    created_at = fields.DateTime(required=True)
    updated_at = fields.DateTime(required=True)

class MonthlySummarySchema(Schema):
    """월별 요약 응답을 위한 스키마"""
    month = fields.Str(required=True)  # YYYY-MM 형식
    pet_id = fields.Str(required=True)
    user_id = fields.Str(required=True)
    
    # 일별 기록 유무 (캘린더 표시용)
    daily_records = fields.Dict(keys=fields.Str(), values=fields.List(fields.Str()), required=True)
    # 예: {"2025-01-15": ["food", "poop", "activity"], "2025-01-16": ["food", "water"]}
    
    # 월별 통계
    total_logged_days = fields.Int(required=True)
    avg_calories_per_day = fields.Float(required=True)
    avg_water_ml_per_day = fields.Float(required=True)
    avg_activity_minutes_per_day = fields.Int(required=True)

class GraphDataPointSchema(Schema):
    """그래프 데이터 포인트 스키마"""
    date = fields.Date(required=True, format="%Y-%m-%d")
    value = fields.Float(required=True)
    
class GraphDataSchema(Schema):
    """그래프 데이터 응답을 위한 스키마"""
    metric = fields.Str(required=True)  # weight, calories, water, activity 등
    period = fields.Str(required=True)  # weekly, monthly, yearly
    data_points = fields.List(fields.Nested(GraphDataPointSchema), required=True)
    
    # 통계 정보
    min_value = fields.Float(required=True)
    max_value = fields.Float(required=True)
    avg_value = fields.Float(required=True)
    trend = fields.Str(required=True)  # increasing, decreasing, stable

class RecommendationSchema(Schema):
    """권장량 계산 응답을 위한 스키마"""
    pet_id = fields.Str(required=True)
    
    # 기본 정보
    current_weight_kg = fields.Float(allow_none=True)
    ideal_weight_kg = fields.Float(allow_none=True)
    age_months = fields.Int(required=True)
    
    # 계산 결과
    rer_calories = fields.Float(required=True)  # 휴식대사율
    mer_calories = fields.Float(required=True)  # 유지대사율
    recommended_water_ml = fields.Float(required=True)  # 권장 물 섭취량
    
    # 계산에 사용된 승수 정보
    multiplier_used = fields.Float(required=True)
    multiplier_reason = fields.Str(required=True)
    
    # 추가 권장사항
    weight_status = fields.Str(required=True)  # underweight, normal, overweight, obese
    recommendations = fields.List(fields.Str(), required=True)
    
    calculated_at = fields.DateTime(required=True)

class PetCareLogCreateRequestSchema(Schema):
    """펫케어 로그 생성 요청을 위한 스키마"""
    date = fields.Date(required=True, format="%Y-%m-%d")
    
    # 선택적 로그 데이터들
    food_logs = fields.List(fields.Nested(FoodLogSchema), required=False, load_default=[])
    water_logs = fields.List(fields.Nested(WaterLogSchema), required=False, load_default=[])
    poop_logs = fields.List(fields.Nested(PoopLogSchema), required=False, load_default=[])
    activity_logs = fields.List(fields.Nested(ActivityLogSchema), required=False, load_default=[])
    vomit_logs = fields.List(fields.Nested(VomitLogSchema), required=False, load_default=[])
    weight_logs = fields.List(fields.Nested(WeightLogSchema), required=False, load_default=[])

    
    general_notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    mood = fields.Str(required=False, allow_none=True, validate=validate.OneOf(['좋음', '보통', '나쁨']))
    
    @validates_schema
    def validate_at_least_one_log(self, data, **kwargs):
        """최소 하나 이상의 로그가 있는지 확인"""
        log_fields = [
            'food_logs', 'water_logs', 'poop_logs', 'activity_logs', 
            'vomit_logs', 'weight_logs'
        ]
        
        has_logs = any(data.get(field) for field in log_fields)
        has_notes = data.get('general_notes') and data.get('general_notes').strip()
        
        if not has_logs and not has_notes:
            raise ValidationError("최소 하나 이상의 로그 데이터 또는 메모가 필요합니다.")

class ErrorResponseSchema(Schema):
    """에러 응답을 위한 스키마"""
    error_code = fields.Str(required=True)
    message = fields.Str(required=True)
    details = fields.Raw(required=False)
