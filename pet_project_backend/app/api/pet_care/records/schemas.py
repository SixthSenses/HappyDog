# app/api/pet_care/records/schemas.py
from marshmallow import Schema, fields, validate, validates_schema, ValidationError, pre_load
from typing import List

class CareRecordCreateSchema(Schema):
    """
    POST /api/pet-care/<pet_id>/records 요청 본문을 위한 통합 스키마.
    """
    record_type = fields.Str(required=True, validate=validate.OneOf(['weight', 'water', 'activity', 'meal']))
    timestamp = fields.Int(required=True)  # 클라이언트에서 생성한 Unix time (ms)
    data = fields.Raw(required=True)  # 기록 값 (타입에 따라 다름)
    notes = fields.Str(required=False, allow_none=True)
    
    @validates_schema
    def validate_data_by_type(self, data, **kwargs):
        """record_type에 따라 data 필드의 타입을 검증합니다."""
        record_type = data.get('record_type')
        value = data.get('data')
        
        if record_type == 'weight':
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValidationError('체중은 양수여야 합니다.', 'data')
        elif record_type == 'water':
            if not isinstance(value, int) or value < 0:
                raise ValidationError('물 섭취량은 0 이상의 정수여야 합니다.', 'data')
        elif record_type == 'activity':
            if not isinstance(value, int) or value < 0:
                raise ValidationError('활동 시간은 0 이상의 정수여야 합니다.', 'data')
        elif record_type == 'meal':
            if not isinstance(value, int) or value < 0:
                raise ValidationError('식사 횟수는 0 이상의 정수여야 합니다.', 'data')

class RecordItemSchema(Schema):
    """개별 기록 항목 스키마."""
    log_id = fields.Str(dump_only=True)
    pet_id = fields.Str(dump_only=True)
    record_type = fields.Str()
    timestamp = fields.Int()
    data = fields.Raw()
    notes = fields.Str(allow_none=True)
    searchDate = fields.Str(dump_only=True)

class RecordsResponseSchema(Schema):
    """
    유연한 쿼리 응답을 위한 스키마.
    """
    records = fields.List(fields.Nested(RecordItemSchema), dump_default=[])
    meta = fields.Dict(dump_default={})
    grouped = fields.Dict(dump_default={})  # 타입별 그룹화 (grouped=true일 때만)

class RecordsQuerySchema(Schema):
    """
    GET /api/pet-care/<pet_id>/records 쿼리 파라미터 검증 스키마.
    """
    # 날짜 파라미터 (상호 배타적)
    date = fields.Str(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    start_date = fields.Str(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    end_date = fields.Str(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    
    # 타입 필터링
    record_types = fields.List(fields.Str(validate=validate.OneOf(['weight', 'water', 'activity', 'meal'])))
    
    # 응답 옵션
    grouped = fields.Bool(load_default=False)  # 타입별 그룹화 여부
    limit = fields.Int(validate=validate.Range(min=1, max=100), load_default=50)
    offset = fields.Int(validate=validate.Range(min=0), load_default=0)
    sort = fields.Str(validate=validate.OneOf(['timestamp_asc', 'timestamp_desc']), load_default='timestamp_desc')
    
    @pre_load
    def preprocess_data(self, data, **kwargs):
        """쿼리 파라미터 전처리."""
        # ImmutableMultiDict를 수정 가능한 딕셔너리로 변환
        processed_data = dict(data)
        
        # record_types 문자열을 리스트로 변환
        if 'record_types' in processed_data and isinstance(processed_data['record_types'], str):
            processed_data['record_types'] = [t.strip() for t in processed_data['record_types'].split(',')]
        
        # grouped 파라미터를 boolean으로 변환
        if 'grouped' in processed_data and isinstance(processed_data['grouped'], str):
            grouped_str = processed_data['grouped'].lower()
            processed_data['grouped'] = grouped_str in ('true', '1', 'yes')
        
        return processed_data
    
    @validates_schema
    def validate_date_parameters(self, data, **kwargs):
        """날짜 파라미터 검증."""
        date = data.get('date')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        # date와 start_date/end_date는 상호 배타적
        if date and (start_date or end_date):
            raise ValidationError("'date'와 'start_date'/'end_date'는 동시에 사용할 수 없습니다.")
        
        # start_date와 end_date는 함께 사용되어야 함
        if (start_date and not end_date) or (end_date and not start_date):
            raise ValidationError("'start_date'와 'end_date'는 함께 사용되어야 합니다.")
        
        # 날짜 파라미터가 하나는 있어야 함
        if not date and not start_date and not end_date:
            raise ValidationError("날짜 파라미터('date' 또는 'start_date'/'end_date')가 필요합니다.")

class RecordTypeQuerySchema(Schema):
    """
    GET /api/pet-care/<pet_id>/records/{record_type} 쿼리 파라미터 검증 스키마.
    """
    # 날짜 파라미터 (상호 배타적)
    date = fields.Str(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    start_date = fields.Str(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    end_date = fields.Str(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    
    # 페이지네이션
    limit = fields.Int(validate=validate.Range(min=1, max=100), load_default=50)
    cursor = fields.Str()  # 커서 기반 페이지네이션용
    
    @validates_schema
    def validate_date_parameters(self, data, **kwargs):
        """날짜 파라미터 검증."""
        date = data.get('date')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        # date와 start_date/end_date는 상호 배타적
        if date and (start_date or end_date):
            raise ValidationError("'date'와 'start_date'/'end_date'는 동시에 사용할 수 없습니다.")
        
        # start_date와 end_date는 함께 사용되어야 함
        if (start_date and not end_date) or (end_date and not start_date):
            raise ValidationError("'start_date'와 'end_date'는 함께 사용되어야 합니다.")

# 기존 호환성을 위한 스키마
class DailyRecordsResponseSchema(Schema):
    """
    GET /api/pet-care/<pet_id>/records?date=... 응답을 위한 스키마 (기존 호환성).
    기록을 타입별로 그룹화하여 반환합니다.
    """
    weight = fields.List(fields.Dict(), dump_default=[])
    water = fields.List(fields.Dict(), dump_default=[])
    activity = fields.List(fields.Dict(), dump_default=[])
    meal = fields.List(fields.Dict(), dump_default=[])