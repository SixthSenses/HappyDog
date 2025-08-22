# app/api/pet_care/records/schemas.py
from marshmallow import Schema, fields, validate, validates, ValidationError

class CareRecordCreateSchema(Schema):
    """
    POST /api/pet-care/<pet_id>/records 요청 본문을 위한 통합 스키마.
    """
    record_type = fields.Str(required=True, validate=validate.OneOf(['weight', 'water', 'activity', 'meal']))
    timestamp = fields.Int(required=True)  # 클라이언트에서 생성한 Unix time (ms)
    data = fields.Raw(required=True)  # 기록 값 (타입에 따라 다름)
    notes = fields.Str(required=False, allow_none=True)
    
    @validates('data')
    def validate_data_by_type(self, value, **kwargs):
        """record_type에 따라 data 필드의 타입을 검증합니다."""
        record_type = kwargs.get('data', {}).get('record_type')
        if record_type == 'weight':
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValidationError('체중은 양수여야 합니다.')
        elif record_type == 'water':
            if not isinstance(value, int) or value < 0:
                raise ValidationError('물 섭취량은 0 이상의 정수여야 합니다.')
        elif record_type == 'activity':
            if not isinstance(value, int) or value < 0:
                raise ValidationError('활동 시간은 0 이상의 정수여야 합니다.')
        elif record_type == 'meal':
            if not isinstance(value, int) or value < 0:
                raise ValidationError('식사 횟수는 0 이상의 정수여야 합니다.')

class DailyRecordsResponseSchema(Schema):
    """
    GET /api/pet-care/<pet_id>/records?date=... 응답을 위한 스키마.
    기록을 타입별로 그룹화하여 반환합니다.
    """
    weight = fields.List(fields.Dict(), dump_default=[])
    water = fields.List(fields.Dict(), dump_default=[])
    activity = fields.List(fields.Dict(), dump_default=[])
    meal = fields.List(fields.Dict(), dump_default=[])