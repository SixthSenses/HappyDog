# app/api/pets/routes.py
import uuid
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.pets.schemas import PetSchema, PetUpdateSchema, EyeAnalysisResponseSchema
from app.models.pet import Pet, PetGender, ActivityLevel, DietType

pets_bp = Blueprint('pets_bp', __name__)

@pets_bp.route('/', methods=['POST'])
@jwt_required()
def register_pet():
    pet_service = current_app.services['pets']
    
    user_id = get_jwt_identity()
    
    # 서비스 로직을 호출하여 이미 반려동물이 있는지 확인
    if pet_service.get_pet_by_user_id(user_id):
        return jsonify({"error_code": "PET_ALREADY_EXISTS", "message": "이미 등록된 반려동물이 있습니다."}), 409

    try:
        # 스키마를 통해 요청 데이터 유효성 검사
        pet_data = PetSchema().load(request.get_json())
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400

    try:
        # 데이터 모델 객체 생성
        new_pet = Pet(
            pet_id=str(uuid.uuid4()),
            user_id=user_id,
            name=pet_data['name'],
            gender=PetGender(pet_data['gender']),
            birthdate=pet_data['birthdate'],
            breed=pet_data['breed'],
            fur_color=pet_data['fur_color'],
            health_concerns=pet_data.get('health_concerns', []),
            # 새로운 펫케어 필드들
            activity_level=ActivityLevel(pet_data['activity_level']) if pet_data.get('activity_level') else None,
            diet_type=DietType(pet_data['diet_type']) if pet_data.get('diet_type') else None,
            is_neutered=pet_data.get('is_neutered'),
            current_weight=pet_data.get('current_weight'),
            care_settings=pet_data.get('care_settings')
        )
        # 서비스 로직을 통해 반려동물 생성
        created_pet = pet_service.create_pet(new_pet)
        # 성공 응답 반환
        return jsonify(PetSchema().dump(created_pet)), 201
    except Exception as e:
        logging.error(f"반려동물 등록 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "PET_CREATION_FAILED", "message": "반려동물 등록 중 오류가 발생했습니다."}), 500

@pets_bp.route('/<string:pet_id>', methods=['GET'])
@jwt_required()
def get_my_pet():
    """
    현재 로그인된 사용자의 반려동물 정보를 조회합니다.
    """
    pet_service = current_app.services['pets']
    user_id = get_jwt_identity()
    
    try:
        pet_info = pet_service.get_pet_by_user_id(user_id)
        if not pet_info:
            return jsonify({"error_code": "PET_NOT_FOUND", "message": "등록된 반려동물이 없습니다."}), 404
        
        return jsonify(PetSchema().dump(pet_info)), 200
    except Exception as e:
        logging.error(f"반려동물 정보 조회 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "PET_FETCH_FAILED", "message": "반려동물 정보를 가져오는 중 오류가 발생했습니다."}), 500

@pets_bp.route('/<string:pet_id>', methods=['PATCH'])
@jwt_required()
def update_pet(pet_id: str):
    pet_service = current_app.services['pets']
    """
    특정 반려동물의 정보를 수정합니다.
    """
    user_id = get_jwt_identity()
    try:
        # 1. 소유권 확인 (서비스 계층에 위임)
        pet_info = pet_service.get_pet_by_id_and_owner(pet_id, user_id)
        if not pet_info:
            return jsonify({"error_code": "FORBIDDEN_OR_NOT_FOUND", "message": "수정 권한이 없거나 반려동물을 찾을 수 없습니다."}), 403
        
        # 2. 요청 데이터 유효성 검사
        update_data = PetUpdateSchema().load(request.get_json())
        
        # 3. 정보 업데이트 (서비스 계층에 위임)
        updated_pet = pet_service.update_pet(pet_id, update_data)
        
        return jsonify(PetSchema().dump(updated_pet)), 200
        
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"반려동물 정보 수정 중 오류 발생 (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "PET_UPDATE_FAILED", "message": "정보 수정 중 오류가 발생했습니다."}), 500


@pets_bp.route('/<string:pet_id>/nose-print', methods=['POST'])
@jwt_required()
def register_nose_print(pet_id: str):
    pet_service = current_app.services['pets']
    """
    특정 반려동물의 비문을 분석하고 등록/인증합니다.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    file_path = data.get('file_path')

    if not file_path:
        return jsonify({"error_code": "PAYLOAD_INVALID", "message": "'file_path'가 필요합니다."}), 400
    
    try:
        # 서비스 계층에 비문 분석 및 등록 로직 위임 (소유권 확인 포함)
        result = pet_service.register_nose_print_for_pet(pet_id, user_id, file_path)
        
        # 서비스 계층에서 반환된 결과에 따라 응답 처리
        if result['status'] == "SUCCESS":
            return jsonify(result), 200
        elif result['status'] == "ALREADY_VERIFIED":
             return jsonify(result), 409
        elif result['status'] == "DUPLICATE":
             return jsonify(result), 409
        elif result['status'] == "INVALID_IMAGE":
             return jsonify(result), 400
        else: # ERROR
             return jsonify(result), 500

    except PermissionError as e:
         return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except FileNotFoundError as e:
         return jsonify({"error_code": "PET_NOT_FOUND", "message": str(e)}), 404
    except Exception as e:
        logging.error(f"비문 등록 중 예외 발생 (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": "알 수 없는 서버 오류가 발생했습니다."}), 500


@pets_bp.route('/<string:pet_id>/eye-analysis', methods=['POST'])
@jwt_required()
def request_eye_analysis(pet_id: str):
    pet_service = current_app.services['pets']
    """
    특정 반려동물의 안구 이미지를 분석하고 결과를 저장합니다.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    file_path = data.get('file_path')

    if not file_path:
        return jsonify({"error_code": "PAYLOAD_INVALID", "message": "'file_path'가 필요합니다."}), 400
        
    try:
        # 서비스 계층에 안구 분석 및 결과 저장 로직 위임 (소유권 확인 포함)
        analysis_result = pet_service.analyze_eye_image_for_pet(user_id, pet_id, file_path)
        
        # 스키마를 통해 응답 포맷팅
        response_data = EyeAnalysisResponseSchema().dump(analysis_result)
        return jsonify(response_data), 200
        
    except PermissionError as e:
         return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except FileNotFoundError as e:
         return jsonify({"error_code": "PET_NOT_FOUND", "message": str(e)}), 404
    except RuntimeError as e: # GCS 다운로드 또는 Firestore 저장 실패 등
        logging.error(f"안구 분석 실패 (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "ANALYSIS_FAILED", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"안구 분석 중 예외 발생 (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "알 수 없는 서버 오류가 발생했습니다."}), 500

@pets_bp.route('/<string:pet_id>/care-settings', methods=['PATCH'])
@jwt_required()
def update_care_settings(pet_id: str):
    """
    반려동물의 펫케어 설정을 업데이트합니다.
    
    Path Parameters:
        - pet_id (str): 반려동물 ID
        
    Request Body:
        - care_settings (dict): 설정 정보
          예: {"food_increment": 10, "water_increment": 50, "activity_increment": 15}
    """
    try:
        pet_service = current_app.services['pets']
        user_id = get_jwt_identity()
        
        # 펫 소유권 확인
        pet_info = pet_service.get_pet_by_id_and_owner(pet_id, user_id)
        if not pet_info:
            return jsonify({
                "error_code": "PET_NOT_FOUND",
                "message": "반려동물을 찾을 수 없거나 접근 권한이 없습니다."
            }), 404
        
        # 요청 데이터 검증
        request_data = request.get_json()
        if not request_data or 'care_settings' not in request_data:
            return jsonify({
                "error_code": "MISSING_CARE_SETTINGS",
                "message": "care_settings 필드가 필요합니다."
            }), 400
        
        care_settings = request_data['care_settings']
        if not isinstance(care_settings, dict):
            return jsonify({
                "error_code": "INVALID_CARE_SETTINGS",
                "message": "care_settings는 객체 형태여야 합니다."
            }), 400
        
        # 설정 업데이트
        update_data = {'care_settings': care_settings}
        updated_pet = pet_service.update_pet(pet_id, update_data)
        
        if not updated_pet:
            return jsonify({
                "error_code": "UPDATE_FAILED",
                "message": "펫케어 설정 업데이트에 실패했습니다."
            }), 500
        
        logging.info(f"펫케어 설정 업데이트 완료 (pet_id: {pet_id})")
        return jsonify({
            "message": "펫케어 설정이 성공적으로 업데이트되었습니다.",
            "care_settings": updated_pet.get('care_settings')
        }), 200
        
    except Exception as e:
        logging.error(f"펫케어 설정 업데이트 중 오류 발생 (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "CARE_SETTINGS_UPDATE_FAILED",
            "message": "펫케어 설정 업데이트 중 오류가 발생했습니다."
        }), 500