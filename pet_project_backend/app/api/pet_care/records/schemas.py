# app/api/pet_care/records/schemas.py
from marshmallow import Schema, fields, validate, validates_schema, ValidationError, pre_load
from typing import List

class CareRecordCreateSchema(Schema):
    """
    POST /api/pet-care/<pet_id>/records 요청 본문을 위한 통합 스키마.
    """
    record_type = fields.Str(required=True, validate=validate.OneOf(['weight', 'water', 'activity', 'meal', 'bcs']))
    timestamp = fields.Int(required=True)  # 클라이언트에서 생성한 Unix time (ms)
    data = fields.Raw(required=True)  # 기록 값 (타입에 따라 다름)
    notes = fields.Str(required=False, allow_none=True)
    # 중복 방지용 선택 필드: 같은 request_id로 여러 번 호출해도 같은 문서를 대상으로 처리
    request_id = fields.Str(required=False)
    
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
        elif record_type == 'bcs':
            # 1(마름) ~ 5(비만) 5단계 정수
            if not isinstance(value, int) or value < 1 or value > 5:
                raise ValidationError('BCS는 1~5 범위의 정수여야 합니다.', 'data')

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

class CareRecordUpdateSchema(Schema):
    """PATCH /api/pet-care/<pet_id>/records/<log_id> 요청 스키마."""
    data = fields.Raw(required=False)
    notes = fields.Str(required=False, allow_none=True)
    timestamp = fields.Int(required=False)

class RecordsQuerySchema(Schema):
    """
    GET /api/pet-care/<pet_id>/records 쿼리 파라미터 검증 스키마.
    """
    # 날짜 파라미터 (상호 배타적)
    date = fields.Str(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    start_date = fields.Str(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    end_date = fields.Str(validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    
    # 타입 필터링
    record_types = fields.List(fields.Str(validate=validate.OneOf(['weight', 'water', 'activity', 'meal', 'bcs'])))
    
    # 응답 옵션
    grouped = fields.Bool(load_default=False)  # 타입별 그룹화 여부
    limit = fields.Int(validate=validate.Range(min=1, max=100), load_default=50)
    offset = fields.Int(validate=validate.Range(min=0), load_default=0)
    cursor = fields.Str()  # 커서 기반 페이지네이션용
    sort = fields.Str(validate=validate.OneOf(['timestamp_asc', 'timestamp_desc']), load_default='timestamp_desc')
    include_total = fields.Bool(load_default=False)  # Sprint E preview: total count 게이팅
    
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

        # sort 별칭 허용: asc/desc -> timestamp_asc/desc
        if 'sort' in processed_data and isinstance(processed_data['sort'], str):
            s = processed_data['sort'].lower()
            if s == 'asc':
                processed_data['sort'] = 'timestamp_asc'
            elif s == 'desc':
                processed_data['sort'] = 'timestamp_desc'
        
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
    bcs = fields.List(fields.Dict(), dump_default=[])

# 신규 스펙 전용 쿼리 스키마들
class DailyQuerySchema(Schema):
    """GET /records/daily 쿼리 파라미터: date 필수, record_types 선택."""
    date = fields.Str(required=True, validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    record_types = fields.List(fields.Str(validate=validate.OneOf(['weight','water','activity','meal','bcs'])))
    limit = fields.Int(load_default=100, validate=validate.Range(min=1, max=500))
    cursor = fields.Str()  # 마지막 문서 id

    @pre_load
    def alias_params(self, data, **kwargs):  # types -> record_types
        mutable = dict(data)
        if 'types' in mutable and 'record_types' not in mutable:
            val = mutable['types']
            if isinstance(val, str):
                mutable['record_types'] = [t.strip() for t in val.split(',') if t.strip()]
            elif isinstance(val, list):
                mutable['record_types'] = val
        return mutable

class RangeQuerySchema(Schema):
    """GET /records/range 쿼리 파라미터: start_date/end_date 필수, record_types 선택 (최대 31일)."""
    start_date = fields.Str(required=True, validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    end_date = fields.Str(required=True, validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    record_types = fields.List(fields.Str(validate=validate.OneOf(['weight','water','activity','meal','bcs'])))
    limit = fields.Int(load_default=300, validate=validate.Range(min=1, max=1000))  # 기간 전체에서 수집할 최대 문서 수
    cursor = fields.Str()  # 이전 페이지 마지막 문서 id (searchDate+timestamp order 기반)

    @pre_load
    def alias_params(self, data, **kwargs):  # start/end/types 별칭 처리
        mutable = dict(data)
        if 'start' in mutable and 'start_date' not in mutable:
            mutable['start_date'] = mutable['start']
        if 'end' in mutable and 'end_date' not in mutable:
            mutable['end_date'] = mutable['end']
        if 'types' in mutable and 'record_types' not in mutable:
            val = mutable['types']
            if isinstance(val, str):
                mutable['record_types'] = [t.strip() for t in val.split(',') if t.strip()]
            elif isinstance(val, list):
                mutable['record_types'] = val
        return mutable

    @validates_schema
    def validate_range(self, data, **kwargs):
        import datetime as _dt
        s = _dt.datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        e = _dt.datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        if e < s:
            raise ValidationError('end_date는 start_date보다 빠를 수 없습니다.', 'end_date')
        if (e - s).days > 31:
            raise ValidationError('최대 31일 범위만 조회할 수 있습니다.', 'end_date')

class SummaryQuerySchema(Schema):
    """GET /records/summary (범위 요약: start_date ~ end_date)"""
    start_date = fields.Str(required=True, validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))
    end_date = fields.Str(required=True, validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'))

    @pre_load
    def alias_params(self, data, **kwargs):  # start/end 별칭 처리
        mutable = dict(data)
        if 'start' in mutable and 'start_date' not in mutable:
            mutable['start_date'] = mutable['start']
        if 'end' in mutable and 'end_date' not in mutable:
            mutable['end_date'] = mutable['end']
        return mutable

    @validates_schema
    def validate_range(self, data, **kwargs):
        import datetime as _dt
        s = _dt.datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        e = _dt.datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        if e < s:
            raise ValidationError('end_date는 start_date보다 빠를 수 없습니다.', 'end_date')
        if (e - s).days > 31:
            raise ValidationError('최대 31일 범위만 요약할 수 있습니다.', 'end_date')