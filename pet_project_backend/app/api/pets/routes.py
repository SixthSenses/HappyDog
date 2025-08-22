# app/api/pets/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from .schemas import (
    PetRegistrationSchema, PetProfileResponseSchema, 
    BiometricAnalysisRequestSchema, EyeAnalysisResponseSchema
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
        new_pet_profile = pet_service.register_pet(user_id, validated_data)
        return jsonify(PetProfileResponseSchema().dump(new_pet_profile)), 201
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"Pet registration API error: {e}", exc_info=True)
        return jsonify({"error_code": "PET_REGISTRATION_FAILED", "message": str(e)}), 500

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