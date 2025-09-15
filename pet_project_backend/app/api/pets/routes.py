# app/api/pets/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from .schemas import (
    PetRegistrationSchema,
    PetProfileResponseSchema,
    PetUpdateSchema,
    BiometricAnalysisRequestSchema,
    EyeAnalysisResponseSchema,
    PetViewBasedResponseSchema,
    NosePrintRegistrationResponseSchema
)
from .presenters import PetPresenter
from .policy import PetAccessPolicy
from app.utils.error_catalog import build_error

pets_bp = Blueprint('pets_bp', __name__)

@pets_bp.route('/', methods=['POST'])
@jwt_required()
def register_pet():
    """반려동물 등록

    새로운 반려동물을 시스템에 등록합니다. 현재 사용자당 하나의 반려동물만 등록할 수 있습니다.

    RequestSchema: PetRegistrationSchema
    ResponseSchema[201]: PetProfileResponseSchema
    """
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    try:
        validated_data = PetRegistrationSchema().load(request.get_json())
        new_pet = pet_service.register_pet(user_id, validated_data)
        # Pet 객체를 딕셔너리로 변환하여 스키마에 전달
        pet_dict = pet_service._pet_to_dict(new_pet)
        return jsonify(PetProfileResponseSchema().dump(pet_dict)), 201
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except ValueError as e:
        status, body = build_error('IDEMPOTENCY_CONFLICT', message=str(e))  # 정책 위반 → 409
        return jsonify(body), status
    except Exception as e:
        logging.error(f"Pet registration API error: {e}", exc_info=True)
        status, body = build_error('RECORD_CREATION_FAILED', message=str(e))
        return jsonify(body), status

@pets_bp.route('/<string:pet_id>', methods=['GET'])
@jwt_required()
def get_pet_profile(pet_id: str):
    """반려동물 프로필 조회 (소유자 전용)

    소유자만 접근할 수 있는 반려동물의 전체 프로필 정보를 조회합니다. 비공개 정보까지 포함됩니다.

    ResponseSchema[200]: PetProfileResponseSchema
    """
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    try:
        pet = pet_service.get_pet_profile(pet_id, user_id)
        # Pet 객체를 딕셔너리로 변환하여 스키마에 전달
        pet_dict = pet_service._pet_to_dict(pet)
        return jsonify(PetProfileResponseSchema().dump(pet_dict)), 200
    except PermissionError as e:
        # 권한 없거나 존재하지 않을 때 통합 NOT_FOUND 메시지 회피 위해 권한/존재 분리 필요시 추가
        status, body = build_error('FORBIDDEN', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"Get pet profile API error (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED', message="프로필 조회 중 오류가 발생했습니다.")
        return jsonify(body), status

@pets_bp.route('/<string:pet_id>', methods=['PATCH'])
@jwt_required()
def update_pet_profile(pet_id: str):
    """반려동물 프로필 수정

    소유자만 접근할 수 있는 반려동물의 프로필 정보를 부분 업데이트합니다. 필요한 필드만 수정할 수 있습니다.

    RequestSchema: PetUpdateSchema
    ResponseSchema[200]: PetProfileResponseSchema
    """
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    try:
        update_data = PetUpdateSchema().load(request.get_json())
        updated_pet = pet_service.update_pet_profile(pet_id, user_id, update_data)
        # Pet 객체를 딕셔너리로 변환하여 스키마에 전달
        pet_dict = pet_service._pet_to_dict(updated_pet)
        return jsonify(PetProfileResponseSchema().dump(pet_dict)), 200
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except (PermissionError, ValueError) as e:
        status, body = build_error('FORBIDDEN', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"Update pet profile API error (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED', message="프로필 수정 중 오류가 발생했습니다.")
        return jsonify(body), status


@pets_bp.route('/<string:pet_id>/nose-print', methods=['POST'])
@jwt_required()
def register_nose_print(pet_id: str):
    """반려동물 비문 등록/인증

    특정 반려동물의 비문(코) 이미지를 분석하여 등록/인증 처리합니다.

    RequestSchema: BiometricAnalysisRequestSchema
    ResponseSchema[200]: NosePrintRegistrationResponseSchema
    """
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    biometric_service = current_app.services.get('pet_biometrics')
    try:
        # 레거시 호환 처리: 이전 클라이언트에서 nose_image_url 사용 가능
        raw = request.get_json() or {}
        if 'file_path' not in raw:
            legacy = raw.get('nose_image_url') or raw.get('image_url')
            if legacy:
                raw['file_path'] = legacy
        data = BiometricAnalysisRequestSchema().load(raw)
        if not biometric_service:
            status, body = build_error('SERVICE_UNAVAILABLE')
            return jsonify(body), status
        pet_obj = pet_service.get_pet_profile(pet_id, user_id)
        current_verified = getattr(pet_obj, 'is_verified', False)
        result_obj = biometric_service.register_nose_print_for_pet(
            pet_id=pet_id,
            user_id=user_id,
            file_path=data['file_path'],
            pet_verification_status=current_verified
        )
        if not result_obj.success:
            code = result_obj.error_code or 'BIO_PROCESSING_FAILED'
            # 상세 메타데이터(예: distance, status) 전달 (디버깅/UX 개선)
            details = {'pet_id': pet_id}
            if result_obj.metadata:
                details.update({k: v for k, v in result_obj.metadata.items() if k not in details})
            status, body = build_error(code, message=result_obj.error_message, details=details)
            return jsonify(body), status
        result = {
            'success': True,
            'confidence': result_obj.confidence,
            'features': result_obj.features,
            'analysis_id': result_obj.analysis_id,
            'metadata': result_obj.metadata,
            'status': (result_obj.metadata or {}).get('status', 'SUCCESS')
        }
        return jsonify(result), 200
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except PermissionError as e:
        status, body = build_error('FORBIDDEN', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"Nose print registration API error: {e}", exc_info=True)
        status, body = build_error('BIO_PROCESSING_FAILED')
        return jsonify(body), status

@pets_bp.route('/<string:pet_id>/eye-analysis', methods=['POST'])
@jwt_required()
def request_eye_analysis(pet_id: str):
    """반려동물 안구 이미지 분석

    특정 반려동물의 안구 이미지를 분석합니다.

    RequestSchema: BiometricAnalysisRequestSchema
    ResponseSchema[200]: EyeAnalysisResponseSchema
    """
    user_id = get_jwt_identity()
    pet_service = current_app.services['pets']
    biometric_service = current_app.services.get('pet_biometrics')
    try:
        # 레거시 호환 처리: 이전 클라이언트에서 eye_image_url 사용 가능
        raw = request.get_json() or {}
        if 'file_path' not in raw:
            legacy = raw.get('eye_image_url') or raw.get('image_url')
            if legacy:
                raw['file_path'] = legacy
        data = BiometricAnalysisRequestSchema().load(raw)
        if not biometric_service:
            status, body = build_error('SERVICE_UNAVAILABLE')
            return jsonify(body), status
        pet_service.get_pet_profile(pet_id, user_id)
        result_obj = biometric_service.analyze_eye_image_for_pet(user_id, pet_id, data['file_path'])
        if not result_obj.success:
            code = result_obj.error_code or 'BIO_PROCESSING_FAILED'
            status, body = build_error(code, message=result_obj.error_message, details={'pet_id': pet_id})
            return jsonify(body), status
        response_dict = {
            'analysis_id': result_obj.analysis_id,
            'disease_name': (result_obj.features or {}).get('disease_name'),
            'probability': (result_obj.features or {}).get('probability'),
            'image_url': (result_obj.features or {}).get('image_url')
        }
        return jsonify(EyeAnalysisResponseSchema().dump(response_dict)), 200
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except PermissionError as e:
        status, body = build_error('FORBIDDEN', message=str(e))
        return jsonify(body), status
    except RuntimeError as e:
        logging.error(f"Eye analysis failed (pet_id: {pet_id}): {e}", exc_info=True)
        status, body = build_error('BIO_PROCESSING_FAILED', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"Eye analysis API error: {e}", exc_info=True)
        status, body = build_error('BIO_PROCESSING_FAILED')
        return jsonify(body), status


@pets_bp.route('/profile', methods=['GET'])
@jwt_required(optional=True)
def get_pet_profile_by_view():
    """뷰 기반 반려동물 프로필 조회

    용도(view)에 맞게 필터링된 반려동물 프로필을 조회합니다. 정책은 PetAccessPolicy로 관리됩니다.

    ResponseSchema[200]: PetViewBasedResponseSchema
    """
    current_user_id = get_jwt_identity()
    target_user_id = request.args.get('user_id', current_user_id)
    view = request.args.get('view', 'mypage')

    policy = PetAccessPolicy()
    try:
        policy.ensure_view_permission(current_user_id, target_user_id, view)
    except ValueError:
        status, body = build_error('VALIDATION_ERROR', message="view는 mypage, petcare, social 중 하나여야 합니다.")
        return jsonify(body), status
    except PermissionError as e:
        code = str(e)
        if code == 'AUTHENTICATION_REQUIRED':
            # 카탈로그에 해당 코드가 없으므로 VALIDATION_ERROR로 매핑 + 커스텀 메시지 (optional auth 상황)
            status, body = build_error('VALIDATION_ERROR', message="인증이 필요합니다.")
            return jsonify(body), status
        status, body = build_error('FORBIDDEN', message="접근이 허용되지 않습니다.")
        return jsonify(body), status

    pet_service = current_app.services['pets']
    try:
        pet_profile = pet_service.get_user_pet_profile(target_user_id)
        if not pet_profile:
            status, body = build_error('NOT_FOUND', message="등록된 반려동물이 없습니다.")
            return jsonify(body), status

        user_stats = current_app.services.get('user_stats')
        response_data = PetPresenter.build_view_response(
            pet_profile, view, user_stats_service=user_stats, target_user_id=target_user_id
        )
        # Marshmallow schema for consistency
        return jsonify(PetViewBasedResponseSchema().dump(response_data)), 200
    except Exception as e:
        logging.error(f"Pet profile API error (target_user_id: {target_user_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED', message="서버 오류가 발생했습니다.")
        return jsonify(body), status