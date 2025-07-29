from marshmallow import Schema, fields

class PetSchema(Schema):
    """Pet 데이터의 유효성 검증 및 직렬화/역직렬화를 위한 스키마."""
    id = fields.Str(dump_only=True)
    
    # required=True: 요청 시 필수 필드
    name = fields.Str(required=True)
    breed = fields.Str(required=True)
    birth_date = fields.Date(format='iso', required=True)
    
    # load_only=True: 요청 시에만 사용 (내부적으로 owner_id를 받기 위함)
    # 응답에는 포함되지 않음
    owner_id = fields.Str(load_only=True)