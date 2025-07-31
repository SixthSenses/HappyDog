# pet_project_backend/app/api/mypage/routes.py
import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.models.pet import Pet, PetGender
from app.api.mypage.schemas import PetSchema, PetUpdateSchema
from app.api.mypage.services import PetService

mypage_bp = Blueprint('mypage_bp', __name__)
pet_service = PetService()

@mypage_bp.route('/pet', methods=['POST'])
@jwt_required()
def register_pet():
    """로그인된 사용자의 반려동물을 최초 등록합니다."""
    user_id = get_jwt_identity()
    
    # 서비스 계층을 통해 로직 처리
    if pet_service.get_pet_by_user_id(user_id) is not None:
        return jsonify({"error_code": "PET_ALREADY_EXISTS", "message": "이미 등록된 반려동물이 있습니다."}), 409

    try:
        pet_schema = PetSchema()
        pet_data = pet_schema.load(request.get_json())
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "message": "입력값 유효성 검사에 실패했습니다.", "details": err.messages}), 400

    new_pet = Pet(
        pet_id=str(uuid.uuid4()),
        user_id=user_id,
        name=pet_data['name'],
        gender=PetGender(pet_data['gender']), # 문자열을 Enum 객체로 변환
        breed=pet_data['breed'],
        birthdate=pet_data['birthdate'],
        #is_neutered=pet_data['is_neutered'],
        vaccination_status=pet_data.get('vaccination_status'),
        is_verified=False
    )

    # 서비스 계층을 통해 데이터 생성
    created_pet_data = pet_service.create_pet(new_pet)
    
    response_data = PetSchema().dump(created_pet_data)
    return jsonify(response_data), 201

@mypage_bp.route('/pet', methods=['PATCH'])
@jwt_required()
def update_pet():
    """로그인된 사용자의 반려동물 정보를 수정합니다."""
    user_id = get_jwt_identity()
    
    pet_info = pet_service.get_pet_by_user_id(user_id)
    if pet_info is None:
        return jsonify({"error_code": "PET_NOT_FOUND", "message": "등록된 반려동물을 찾을 수 없습니다."}), 404
    
    try:
        update_data = PetUpdateSchema().load(request.get_json())
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "message": "입력값 유효성 검사에 실패했습니다.", "details": err.messages}), 400
        
    pet_id = pet_info['pet_id']
    updated_pet_data = pet_service.update_pet(pet_id, update_data)
    
    response_data = PetSchema().dump(updated_pet_data)
    return jsonify(response_data), 200


@mypage_bp.route('/pet', methods=['GET'])
@jwt_required()
def get_pet():
    """로그인된 사용자의 반려동물 정보를 조회합니다."""
    # 1. JWT 토큰에서 사용자 ID를 가져옵니다.
    user_id = get_jwt_identity()
    
    # 2. 서비스 계층을 통해 반려동물 정보를 가져옵니다.
    pet_info = pet_service.get_pet_by_user_id(user_id)
    
    # 3. 반려동물이 없으면 404 에러를 반환합니다.
    if pet_info is None:
        return jsonify({"error_code": "PET_NOT_FOUND", "message": "등록된 반려동물을 찾을 수 없습니다."}), 404
    
    # 4. 조회된 정보를 스키마를 통해 JSON으로 변환(직렬화)합니다.
    response_data = PetSchema().dump(pet_info)
    
    # 5. JSON 데이터와 함께 200 OK 상태 코드를 반환합니다.
    return jsonify(response_data), 200