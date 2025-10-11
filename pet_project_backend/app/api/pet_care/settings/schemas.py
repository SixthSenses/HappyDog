# app/api/pet_care/settings/schemas.py
from marshmallow import Schema, fields, validate

class PetCareSettingsSchema(Schema):
    """펫케어 설정 조회/수정 스키마.

    목표 활동 분(`target_daily_activity_minutes`)은 파생 필드이며
    ( `target_daily_activity_sessions` × `activity_session_minutes` ) 로 계산됩니다.
    클라이언트는 PATCH/PUT 요청에서 `target_daily_activity_minutes` 값을 전송하지 말아야 하며,
    서버는 전송하더라도 무시합니다.

    식사 목표는 `target_daily_meal_count`(=goalMealCount)만 사용합니다.
    과거에 존재하던 `daily_meal_count` 필드는 혼동 방지를 위해 제거되었습니다.
    """
    # 내부 저장 키를 필드명으로 사용, API 노출/입력 키는 data_key로 지정
    goalWeight = fields.Float(required=False, validate=validate.Range(min=0.1, max=200.0), data_key='target_weight')
    goalMealCount = fields.Int(required=False, validate=validate.Range(min=1, max=10), data_key='target_daily_meal_count')
    # 파생 필드(읽기 전용): goalActivitySessions × activitySessionMinutes 로 계산됨
    # Method A: 클라이언트는 target_daily_activity_minutes를 전송하지 말아야 하며 서버는 무시
    goalActivityMinutes = fields.Int(
        required=False,
        dump_only=True,
        validate=validate.Range(min=0, max=1440),
        data_key='target_daily_activity_minutes'
    )
    goalActivitySessions = fields.Int(required=False, validate=validate.Range(min=0, max=48), data_key='target_daily_activity_sessions')
    activitySessionMinutes = fields.Int(required=False, validate=validate.Range(min=0, max=600), data_key='activity_session_minutes')
    activityIncrementMinutes = fields.Int(required=False, validate=validate.Range(min=1, max=180), data_key='daily_activity_increment')


    # 응답에만 포함될 필드
    pet_id = fields.Str(dump_only=True)
    updated_at = fields.DateTime(dump_only=True, format="iso8601")