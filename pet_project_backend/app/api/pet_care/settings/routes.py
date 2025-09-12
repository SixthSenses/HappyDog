# app/api/pet_care/settings/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.api.pet_care.settings.schemas import PetCareSettingsSchema
from app.utils.error_catalog import build_error
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, PetCareErrors, RequestExamples, ResponseExamples
)

# 블루프린트 이름을 포함하여 네임스페이스 충돌 방지
pet_care_settings_bp = Blueprint('pet_care_settings_bp', __name__)

@pet_care_settings_bp.route('/<string:pet_id>/settings', methods=['GET'])
@jwt_required()
def get_pet_care_settings(pet_id: str):
    """펫케어 설정 조회

    특정 반려동물의 펫케어 설정 정보를 조회합니다. 체중 목표, 활동 목표 등의 관리 설정을 포함합니다.

    ResponseSchema[200]: PetCareSettingsSchema
    """
    service = current_app.services['pet_care_settings']
    try:
        settings = service.get_settings(pet_id)
        return jsonify(PetCareSettingsSchema().dump(settings)), 200
    except FileNotFoundError as e:
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"설정 조회 API 오류 (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED', message="설정 조회 중 오류 발생")
        return jsonify(body), status

@pet_care_settings_bp.route('/<string:pet_id>/settings', methods=['PUT'])
@jwt_required()
def update_pet_care_settings(pet_id: str):
    """펫케어 설정 수정

    특정 반려동물의 펫케어 설정 정보를 수정합니다. 부분 업데이트를 지원하여 필요한 필드만 수정할 수 있습니다.

    RequestSchema: PetCareSettingsSchema
    ResponseSchema[200]: PetCareSettingsSchema
    """
    service = current_app.services['pet_care_settings']
    try:
        update_data = PetCareSettingsSchema(partial=True).load(request.get_json())
        if not update_data:
            status, body = build_error('VALIDATION_ERROR', message="수정할 데이터가 없습니다.")
            return jsonify(body), status

        updated_settings = service.update_settings(pet_id, update_data)
        return jsonify(PetCareSettingsSchema().dump(updated_settings)), 200
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except FileNotFoundError as e:
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"설정 수정 API 오류 (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED', message="설정 수정 중 오류 발생")
        return jsonify(body), status