# pet_project_backend/app/api/mypage/routes.py
import uuid
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.models.pet import Pet, PetGender
from app.api.mypage.schemas import PetSchema, PetUpdateSchema
from app.api.mypage.services import pet_service

mypage_bp = Blueprint('mypage_bp', __name__)


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


@mypage_bp.route('/pet/nose-print', methods=['POST'])
@jwt_required()
def register_nose_print():
    """
    [수정] 업로드된 비문 이미지의 경로를 받아 ML 분석 후 등록/인증합니다.
    """
    user_id = get_jwt_identity()
    
    # [수정] request.files 대신 request.get_json()으로 file_path를 받습니다.
    data = request.get_json()
    if not data or 'file_path' not in data:
        return jsonify({"error_code": "PAYLOAD_INVALID", "message": "요청 본문에 'file_path' 필드가 필요합니다."}), 400
    
    file_path = data['file_path']

    try:
        pipeline = current_app.services['pipeline']
        storage_service = current_app.services['storage']
    except (AttributeError, KeyError):
        logging.error("서비스가 Flask 앱에 제대로 등록되지 않았습니다.")
        return jsonify({"status": "ERROR", "message": "서버 설정에 오류가 발생했습니다."}), 500

    # 반려동물 정보 조회 및 이미 인증되었는지 확인하는 로직은 동일합니다.
    pet_info = pet_service.get_pet_by_user_id(user_id)
    if not pet_info:
        return jsonify({"error_code": "PET_NOT_FOUND", "message": "비문을 등록할 반려동물 정보가 없습니다."}), 404

    if pet_info.get('is_verified', False):
        return jsonify({"error_code": "ALREADY_VERIFIED", "message": "이미 비문 인증이 완료된 반려동물입니다."}), 409

    # [삭제] request.files에서 직접 이미지를 읽는 부분을 삭제합니다.
    # if 'image' not in request.files: ...
    # image_file = request.files['image']
    # image_bytes = image_file.read()

    try:
        # [수정] 파이프라인 호출 시 storage_service와 file_path를 전달합니다.
        result = pipeline.process_image(storage_service=storage_service, file_path=file_path)
        status = result.get("status")

        if status == "SUCCESS":
            pet_id = pet_info['pet_id']
            
            # [수정] 이미지가 Storage에 있으므로, 해당 blob을 public으로 만들고 URL을 가져옵니다.
            blob = storage_service.bucket.blob(file_path)
            blob.make_public()
            image_url = blob.public_url
            
            update_data = {
                "is_verified": True,
                "nose_print_url": image_url,
                "faiss_id": result['faiss_id']
            }
            updated_pet = pet_service.update_pet(pet_id, update_data)
            
            # DB 업데이트 후 Faiss 인덱스를 업데이트하는 로직은 동일합니다.
            try:
                pipeline.add_vector_to_index(result['vector'])
            except Exception as e:
                logging.error(f"Faiss 인덱스 업데이트 실패: {e}. DB와 정합성 문제가 발생할 수 있습니다.")
                pass

            return jsonify({
                "status": "SUCCESS",
                "message": "비문이 성공적으로 등록 및 인증되었습니다.",
                "pet": PetSchema().dump(updated_pet)
            }), 200

        # [수정] DUPLICATE 발생 시 응답 포맷을 API 명세서와 일치시킵니다.
        elif status == "DUPLICATE":
            # 필요하다면, conflicting_pet 정보를 여기서 조회하여 추가할 수 있습니다.
            return jsonify({
                "error_code": "DUPLICATE_NOSE_PRINT",
                "message": "이미 다른 반려동물의 비문으로 등록된 사진입니다."
                # "conflicting_pet": {"pet_id": "...", "pet_name": "..."}
            }), 409

        # INVALID_IMAGE 등 나머지 상태 처리 로직은 거의 동일합니다.
        elif status == "INVALID_IMAGE":
            return jsonify({"status": "INVALID_IMAGE", "message": "코를 명확하게 식별할 수 없습니다. 더 선명하거나 가까이에서 찍은 사진을 등록해주세요."}), 400
            
        else:
            # ML 파이프라인 내부에서 발생한 에러 또는 예기치 않은 상태
            error_message = result.get("message", "알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            logging.error(f"ML 파이프라인에서 예기치 않은 상태 반환: {status}, 메시지: {error_message}")
            return jsonify({"status": "ERROR", "message": error_message}), 500

    except Exception as e:
        logging.error(f"비문 등록 중 예외 발생: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": "알 수 없는 서버 오류가 발생했습니다."}), 500