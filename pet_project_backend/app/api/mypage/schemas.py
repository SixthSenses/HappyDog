from marshmallow import Schema, fields, validate, post_load
from datetime import date
from app.models.pet import Pet, PetGender

class PetSchema(Schema):
    """
    반려동물 데이터의 유효성 검사 및 직렬화/역직렬화를 위한 스키마.
    - 직렬화 (dump): 파이썬 객체 -> JSON
    - 역직렬화 (load): JSON -> 파이썬 딕셔너리
    """
    # dump_only=True: 이 필드들은 서버가 클라이언트에게 응답을 보낼 때만 사용됩니다.
    pet_id = fields.Str(dump_only=True)
    user_id = fields.Str(dump_only=True)
    
    # required=True: 이 필드들은 반려동물 최초 등록 시 반드시 필요합니다.
    name = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    # OneOf 검증을 통해 'MALE' 또는 'FEMALE' 값만 허용합니다.
    gender = fields.Str(required=True, validate=validate.OneOf([e.value for e in PetGender]))
    breed = fields.Str(required=True, validate=validate.Length(min=1, max=30))
    birthdate = fields.Date(required=True, format="%Y-%m-%d")
    
    # required=False: 선택적으로 입력받는 필드입니다.
    vaccination_status = fields.Str(required=False, allow_none=True)
    
    # [수정됨] 비문 인증 관련 필드들을 응답(dump) 전용으로 추가합니다.
    is_verified = fields.Bool(dump_only=True)
    nose_print_url = fields.Str(dump_only=True, allow_none=True)
    faiss_id = fields.Int(dump_only=True, allow_none=True)

    # 주석 처리된 필드들 (향후 확장 가능성)
    # is_neutered = fields.Bool(required=True)
    # weight_response = fields.Float(attribute="weight", dump_only=True, allow_none=True)

class PetUpdateSchema(Schema):
    """
    반려동물 정보의 부분 수정을 위한 스키마.
    모든 필드는 선택 사항(required=False)입니다.
    """
    name = fields.Str(required=False, validate=validate.Length(min=1, max=20))
    gender = fields.Str(required=False, validate=validate.OneOf([e.value for e in PetGender]))
    breed = fields.Str(required=False, validate=validate.Length(min=1, max=30))
    birthdate = fields.Date(required=False, format="%Y-%m-%d")
    vaccination_status = fields.Str(required=False, allow_none=True)
    # is_neutered = fields.Bool(required=False)

class NotificationSettingsSchema(Schema):
    likes = fields.Bool(required=True)
    comments = fields.Bool(required=True)