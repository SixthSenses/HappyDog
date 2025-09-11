# app/api/pet_care/records/schemas.py
from marshmallow import Schema, fields, validate, validates_schema, ValidationError

class CareRecordCreateSchema(Schema):
    """
    개별 펫케어 기록 생성을 위한 스키마.
    각 기록 타입별로 개별적으로 받을 수 있습니다.
    """
    record_type = fields.Str(required=True, validate=validate.OneOf(['meal_count', 'activity', 'bcs', 'weight', 'stool', 'vomit']))
    timestamp = fields.Int(required=True)  # Unix timestamp (ms)
    data = fields.Raw(required=True)  # 기록 값 (타입에 따라 다름)
    memo = fields.Str(required=False, allow_none=True)
    
    @validates_schema
    def validate_data_by_type(self, data, **kwargs):
        """record_type에 따라 data 필드의 타입을 검증합니다."""
        record_type = data.get('record_type')
        value = data.get('data')
        
        if record_type == 'meal_count':
            # 하루 식사 횟수
            if not isinstance(value, int) or value < 0:
                raise ValidationError('식사 횟수는 0 이상의 정수여야 합니다.', 'data')
        elif record_type == 'activity':
            # 활동량 (분)
            if not isinstance(value, int) or value < 0:
                raise ValidationError('활동량은 0 이상의 정수(분)여야 합니다.', 'data')
        elif record_type == 'bcs':
            # BCS 1~5
            if not isinstance(value, int) or value < 1 or value > 5:
                raise ValidationError('BCS는 1~5 범위의 정수여야 합니다.', 'data')
        elif record_type == 'weight':
            # 몸무게 (kg)
            if not isinstance(value, (int, float)) or float(value) <= 0:
                raise ValidationError('몸무게는 0보다 큰 수여야 합니다.', 'data')
        elif record_type == 'stool':
            # 대변 기록: 문자열 또는 객체
            if isinstance(value, str):
                # 간단한 문자열 기록
                pass
            elif isinstance(value, dict):
                # 상세 객체 기록
                allowed_quality = {'normal', 'soft', 'hard', 'diarrhea', 'none'}
                allowed_color = {'brown', 'yellow', 'black', 'red', 'orange', 'green', 'other'}
                q = value.get('quality')
                if q is not None and q not in allowed_quality:
                    raise ValidationError(f"stool.quality는 {sorted(list(allowed_quality))} 중 하나여야 합니다.", 'data.quality')
                c = value.get('color')
                if c is not None and c not in allowed_color:
                    raise ValidationError(f"stool.color는 {sorted(list(allowed_color))} 중 하나여야 합니다.", 'data.color')
            else:
                raise ValidationError('stool 데이터는 문자열 또는 객체여야 합니다.', 'data')
        elif record_type == 'vomit':
            # 구토 기록: 문자열 또는 객체
            if isinstance(value, str):
                # 간단한 문자열 기록
                pass
            elif isinstance(value, dict):
                # 상세 객체 기록
                allowed_type = {'food', 'bile', 'foam', 'blood', 'other'}
                allowed_color = {'clear', 'yellow', 'brown', 'red', 'white', 'green', 'other'}
                t = value.get('type')
                if t is not None and t not in allowed_type:
                    raise ValidationError(f"vomit.type는 {sorted(list(allowed_type))} 중 하나여야 합니다.", 'data.type')
                c = value.get('color')
                if c is not None and c not in allowed_color:
                    raise ValidationError(f"vomit.color는 {sorted(list(allowed_color))} 중 하나여야 합니다.", 'data.color')
            else:
                raise ValidationError('vomit 데이터는 문자열 또는 객체여야 합니다.', 'data')

class CareRecordUpdateSchema(Schema):
    """
    기존 펫케어 기록 수정을 위한 스키마.
    """
    data = fields.Raw(required=False)  # 수정할 데이터
    memo = fields.Str(required=False, allow_none=True)  # 수정할 메모

class DailyRecordsQuerySchema(Schema):
    """
    특정 날짜의 모든 기록 조회를 위한 스키마.
    """
    date = fields.Str(required=True)  # YYYY-MM-DD 형식
    
class RecordResponseSchema(Schema):
    """
    기록 응답을 위한 스키마.
    """
    log_id = fields.Str()
    pet_id = fields.Str()
    record_type = fields.Str()
    timestamp = fields.Int()
    timestamp_ms = fields.Int()
    data = fields.Raw()
    memo = fields.Str(allow_none=True)
    searchDate = fields.Str()

class DailyRecordsResponseSchema(Schema):
    """
    특정 날짜의 모든 기록 응답 스키마.
    """
    date = fields.Str()  # YYYY-MM-DD
    records = fields.List(fields.Nested(RecordResponseSchema))
    summary = fields.Dict(allow_none=True)  # 타입별 요약
