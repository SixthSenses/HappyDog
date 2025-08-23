# app/api/pets/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from .schemas import (
    PetRegistrationSchema,
    PetProfileResponseSchema,
    PetPublicProfileResponseSchema,
    PetUpdateSchema,
    BiometricAnalysisRequestSchema,
    EyeAnalysisResponseSchema
)

pets_bp = Blueprint('pets_bp', __name__)

@pets_bp.route('/', methods=['POST'])
@jwt_required()
def register_pet():
    """최초 반려동물 등록(Onboarding) API."""
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    try:
        validated_data = PetRegistrationSchema().load(request.get_json())
        new_pet = pet_service.register_pet(user_id, validated_data)
        # Pet 객체를 딕셔너리로 변환하여 스키마에 전달
        pet_dict = pet_service._pet_to_dict(new_pet)
        return jsonify(PetProfileResponseSchema().dump(pet_dict)), 201
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"Pet registration API error: {e}", exc_info=True)
        return jsonify({"error_code": "PET_REGISTRATION_FAILED", "message": str(e)}), 500

@pets_bp.route('/<string:pet_id>', methods=['GET'])
@jwt_required()
def get_pet_profile(pet_id: str):
    """[소유자 전용] 특정 반려동물의 전체 프로필 정보를 조회합니다."""
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    try:
        pet = pet_service.get_pet_profile(pet_id, user_id)
        # Pet 객체를 딕셔너리로 변환하여 스키마에 전달
        pet_dict = pet_service._pet_to_dict(pet)
        return jsonify(PetProfileResponseSchema().dump(pet_dict)), 200
    except PermissionError as e:
        return jsonify({"error_code": "FORBIDDEN_OR_NOT_FOUND", "message": str(e)}), 403
    except Exception as e:
        logging.error(f"Get pet profile API error (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "FETCH_FAILED", "message": "프로필 조회 중 오류가 발생했습니다."}), 500

@pets_bp.route('/<string:pet_id>', methods=['PATCH'])
@jwt_required()
def update_pet_profile(pet_id: str):
    """[소유자 전용] 특정 반려동물의 프로필 정보를 수정합니다 (부분 업데이트)."""
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    try:
        update_data = PetUpdateSchema().load(request.get_json())
        updated_pet = pet_service.update_pet_profile(pet_id, user_id, update_data)
        # Pet 객체를 딕셔너리로 변환하여 스키마에 전달
        pet_dict = pet_service._pet_to_dict(updated_pet)
        return jsonify(PetProfileResponseSchema().dump(pet_dict)), 200
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except (PermissionError, ValueError) as e:
        return jsonify({"error_code": "UPDATE_FAILED_FORBIDDEN", "message": str(e)}), 403
    except Exception as e:
        logging.error(f"Update pet profile API error (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "프로필 수정 중 오류가 발생했습니다."}), 500

@pets_bp.route('/public-profile/<string:pet_id>', methods=['GET'])
@jwt_required()
def get_public_pet_profile(pet_id: str):
    """[공개용] 멍스타그램 등에서 사용할 반려동물의 공개 프로필 정보를 조회합니다."""
    pet_service = current_app.services['pets']
    try:
        public_profile = pet_service.get_public_pet_profile(pet_id)
        return jsonify(PetPublicProfileResponseSchema().dump(public_profile)), 200
    except FileNotFoundError as e:
        return jsonify({"error_code": "PET_NOT_FOUND", "message": str(e)}), 404
    except Exception as e:
        logging.error(f"Get public pet profile API error (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "FETCH_FAILED", "message": "공개 프로필 조회 중 오류가 발생했습니다."}), 500

@pets_bp.route('/<string:pet_id>/nose-print', methods=['POST'])
@jwt_required()
def register_nose_print(pet_id: str):
    """특정 반려동물의 비문 분석 및 등록/인증 API."""
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    try:
        data = BiometricAnalysisRequestSchema().load(request.get_json())
        result = pet_service.register_nose_print_for_pet(pet_id, user_id, data['file_path'])
        
        status_code_map = {"SUCCESS": 200, "ALREADY_VERIFIED": 409, "DUPLICATE": 409, "INVALID_IMAGE": 400, "ERROR": 500}
        return jsonify(result), status_code_map.get(result.get("status"), 500)
        
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except PermissionError as e:
        return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except Exception as e:
        logging.error(f"Nose print registration API error: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": "알 수 없는 서버 오류가 발생했습니다."}), 500

@pets_bp.route('/<string:pet_id>/eye-analysis', methods=['POST'])
@jwt_required()
def request_eye_analysis(pet_id: str):
    """특정 반려동물의 안구 이미지 분석 API."""
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    try:
        data = BiometricAnalysisRequestSchema().load(request.get_json())
        analysis_result = pet_service.analyze_eye_image_for_pet(user_id, pet_id, data['file_path'])
        return jsonify(EyeAnalysisResponseSchema().dump(analysis_result)), 200
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except PermissionError as e:
        return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except RuntimeError as e:
        logging.error(f"Eye analysis failed (pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"error_code": "ANALYSIS_FAILED", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Eye analysis API error: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "알 수 없는 서버 오류가 발생했습니다."}), 500