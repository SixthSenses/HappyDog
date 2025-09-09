# app/api/pet_care/summary/schemas.py
"""Summary API 스키마 정의 (Sprint C)"""
from marshmallow import Schema, fields, validate, validates_schema, ValidationError, pre_load


class SingleDateSummaryQuerySchema(Schema):
    """GET /summary?date= 쿼리 파라미터 검증"""
    date = fields.Str(
        required=True,
        validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'),
        error_messages={'required': '날짜는 필수 파라미터입니다.'}
    )
    with_total = fields.Bool(load_default=False)
    
    @pre_load
    def preprocess_params(self, data, **kwargs):
        """쿼리 파라미터 전처리"""
        processed = dict(data)
        
        # with_total 문자열을 boolean으로 변환
        if 'with_total' in processed and isinstance(processed['with_total'], str):
            val = processed['with_total'].lower()
            processed['with_total'] = val in ('true', '1', 'yes')
        
        return processed


class RangeSummaryQuerySchema(Schema):
    """GET /summary/range?start_date=&end_date= 쿼리 파라미터 검증"""
    start_date = fields.Str(
        required=True,
        validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'),
        error_messages={'required': '시작 날짜는 필수 파라미터입니다.'}
    )
    end_date = fields.Str(
        required=True,
        validate=validate.Regexp(r'^\d{4}-\d{2}-\d{2}$'),
        error_messages={'required': '종료 날짜는 필수 파라미터입니다.'}
    )
    
    @pre_load
    def preprocess_params(self, data, **kwargs):
        """별칭 처리"""
        processed = dict(data)
        
        # start/end 별칭 지원
        if 'start' in processed and 'start_date' not in processed:
            processed['start_date'] = processed['start']
        if 'end' in processed and 'end_date' not in processed:
            processed['end_date'] = processed['end']
        
        return processed
    
    @validates_schema
    def validate_date_range(self, data, **kwargs):
        """날짜 범위 검증"""
        import datetime
        start = datetime.datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        end = datetime.datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        
        if end < start:
            raise ValidationError('종료 날짜는 시작 날짜보다 빠를 수 없습니다.', 'end_date')
        
        # 최대 31일 제한은 라우트에서 처리 (더 명확한 에러 메시지를 위해)