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
    EyeAnalysisResponseSchema,
    PetViewBasedResponseSchema
)
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, PetErrors, RequestExamples, ResponseExamples
)

pets_bp = Blueprint('pets_bp', __name__)

@pets_bp.route('/', methods=['POST'])
@jwt_required()
@api_doc(
    summary="반려동물 등록",
    description="새로운 반려동물을 시스템에 등록합니다. 현재 사용자당 하나의 반려동물만 등록할 수 있습니다.",
    tags=["pets"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    PetErrors.PET_LIMIT_REACHED,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "register_pet",
    "summary": "반려동물 등록 요청",
    "description": "반려동물 기본 정보를 포함한 등록 요청",
    "value": {
        "name": "맥스",
        "breed_id": "golden_retriever",
        "birth_date": "2020-05-15",
        "gender": "male",
        "weight": 25.5,
        "profile_image_url": "https://example.com/pet.jpg"
    }
})
@response_examples(ResponseExamples.SUCCESS_CREATED)
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
    except ValueError as e:
        # 단일 사용자-단일 반려동물 정책 위반
        return jsonify({"error_code": "PET_LIMIT_REACHED", "message": str(e)}), 409
    except Exception as e:
        logging.error(f"Pet registration API error: {e}", exc_info=True)
        return jsonify({"error_code": "PET_REGISTRATION_FAILED", "message": str(e)}), 500

@pets_bp.route('/<string:pet_id>', methods=['GET'])
@jwt_required()
@api_doc(
    summary="반려동물 프로필 조회 (소유자 전용)",
    description="소유자만 접근할 수 있는 반려동물의 전체 프로필 정보를 조회합니다. 비공개 정보까지 포함됩니다.",
    tags=["pets"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    PetErrors.PET_NOT_FOUND,
    PetErrors.PET_NOT_OWNED,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "pet_profile",
    "summary": "반려동물 프로필",
    "description": "반려동물의 상세 프로필 정보",
    "value": {
        "pet_id": "pet_123",
        "name": "맥스",
        "breed": "골든 리트리버",
        "birth_date": "2020-05-15",
        "age_months": 30,
        "gender": "male",
        "weight": 25.5,
        "profile_image_url": "https://example.com/pet.jpg"
    }
})
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
@api_doc(
    summary="반려동물 프로필 수정",
    description="소유자만 접근할 수 있는 반려동물의 프로필 정보를 부분 업데이트합니다. 필요한 필드만 수정할 수 있습니다.",
    tags=["pets"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    PetErrors.PET_NOT_OWNED,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "update_pet",
    "summary": "반려동물 정보 수정 요청",
    "description": "수정할 반려동물 정보 (부분 업데이트)",
    "value": {
        "name": "맥시",
        "weight": 26.0,
        "profile_image_url": "https://example.com/new_pet.jpg"
    }
})
@response_examples(ResponseExamples.SUCCESS_UPDATED)
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

@pets_bp.route('/<string:pet_id>/public', methods=['GET'])
@jwt_required(optional=True)
@api_doc(
    summary="[DEPRECATED] 반려동물 공개 프로필 조회",
    description="[DEPRECATED] 이 엔드포인트는 더 이상 사용되지 않습니다. 대신 GET /api/pets/profile?view=social&user_id={user_id}를 사용하세요.",
    tags=["pets"]
)
@error_responses(
    PetErrors.PET_NOT_FOUND,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "pet_public_profile_deprecated",
    "summary": "[DEPRECATED] 반려동물 공개 프로필",
    "description": "이 응답 형식은 더 이상 사용되지 않습니다. Pet profile API를 사용하세요.",
    "value": {
        "pet_id": "pet_123",
        "name": "맥스",
        "breed": "골든 리트리버",
        "gender": "male",
        "birthdate": "2020-05-15",
        "profile_image_url": "https://example.com/pet.jpg",
        "is_verified": True
    }
})
def get_pet_public_profile(pet_id: str):
    """[DEPRECATED] 멍스타그램 등에서 사용할 반려동물의 공개 프로필 정보를 조회합니다."""
    # 로그에 deprecation 경고 기록
    import warnings
    warnings.warn("GET /api/pets/{pet_id}/public is deprecated. Use GET /api/pets/profile?view=social&user_id={user_id} instead.", DeprecationWarning, stacklevel=2)
    logging.warning(f"DEPRECATED API called: GET /api/pets/{pet_id}/public. Client should migrate to Pet profile API.")
    
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
@api_doc(
    summary="비문 등록 및 인증",
    description="특정 반려동물의 비문 이미지를 분석하여 등록하거나 기존 비문과 비교하여 인증을 수행합니다.",
    tags=["pets"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    PetErrors.PET_NOT_OWNED,
    PetErrors.NOSE_PRINT_DUPLICATE,
    PetErrors.INVALID_IMAGE,
    PetErrors.ML_SERVICE_ERROR
)
@request_examples({
    "name": "nose_print_analysis",
    "summary": "비문 분석 요청",
    "description": "비문 이미지 분석을 위한 파일 경로",
    "value": {"file_path": "uploads/nose_prints/nose_123.jpg"}
})
@response_examples({
    "name": "nose_print_result",
    "summary": "비문 분석 결과",
    "description": "비문 등록 또는 인증 결과",
    "value": {
        "status": "SUCCESS",
        "message": "비문이 성공적으로 등록되었습니다.",
        "pet_id": "pet_123"
    }
})
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
@api_doc(
    summary="안구 이미지 분석",
    description="특정 반려동물의 안구 이미지를 분석하여 건강 상태나 특성을 확인합니다.",
    tags=["pets"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    PetErrors.PET_NOT_OWNED,
    PetErrors.INVALID_IMAGE,
    PetErrors.ML_SERVICE_ERROR,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "eye_analysis_request",
    "summary": "안구 분석 요청",
    "description": "안구 이미지 분석을 위한 파일 경로",
    "value": {"file_path": "uploads/eye_images/eye_123.jpg"}
})
@response_examples({
    "name": "eye_analysis_result",
    "summary": "안구 분석 결과",
    "description": "안구 이미지 분석 결과",
    "value": {
        "analysis_id": "analysis_123",
        "pet_id": "pet_123",
        "results": {
            "eye_health_score": 85,
            "detected_conditions": [],
            "recommendations": ["정기 검진 권장"]
        },
        "analyzed_at": "2023-12-10T12:00:00Z"
    }
})
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


@pets_bp.route('/profile', methods=['GET'])
@jwt_required(optional=True)
@api_doc(
    summary="반려동물 프로필 조회 (뷰 기반 필터링 + 다른 사용자 지원)",
    description="용도에 맞게 필터링된 반려동물 프로필을 조회합니다. 마이페이지, 펫케어, 멍스타그램 각각에 맞는 정보를 제공하며, user_id 파라미터로 다른 사용자의 반려동물도 조회 가능합니다.",
    tags=["pets"]
)
def get_pet_profile_by_view():
    """
    뷰 기반 필터링으로 반려동물 프로필을 조회합니다.
    
    Query Parameters:
    - view: mypage (마이페이지용), petcare (펫케어용), social (멍스타그램용)
    - user_id: (optional) 조회할 사용자 ID. 미제공시 현재 인증된 사용자
    """
    current_user_id = get_jwt_identity()  # 요청한 사용자
    target_user_id = request.args.get('user_id', current_user_id)  # 조회 대상 사용자
    view = request.args.get('view', 'mypage')
    
    if view not in ['mypage', 'petcare', 'social']:
        return jsonify({"error_code": "INVALID_VIEW", "message": "view는 mypage, petcare, social 중 하나여야 합니다."}), 400
    
    # Authorization checks
    if target_user_id != current_user_id:
        # 다른 사용자 프로필 조회시 제한사항 적용
        if not current_user_id:
            return jsonify({"error_code": "AUTHENTICATION_REQUIRED", "message": "다른 사용자의 프로필 조회시 인증이 필요합니다."}), 401
        
        if view in ['mypage', 'petcare']:
            return jsonify({"error_code": "PERMISSION_DENIED", "message": "다른 사용자의 개인 정보는 조회할 수 없습니다."}), 403
    
    pet_service = current_app.services['pets']
    
    try:
        # 대상 사용자의 Pet 정보 조회
        pet_profile = pet_service.get_user_pet_profile(target_user_id)
        if not pet_profile:
            return jsonify({"error_code": "PET_NOT_FOUND", "message": "등록된 반려동물이 없습니다."}), 404
        
        # view에 따른 필터링
        response_data = {
            "pet_id": pet_profile.pet_id,
            "name": pet_profile.name,
            "profile_image_url": pet_profile.profile_image_url,
            "is_verified": pet_profile.is_verified
        }
        
        if view in ['mypage', 'social']:
            # 마이페이지와 멍스타그램에 공통 정보
            response_data.update({
                "birthdate": pet_profile.birthdate.isoformat() if pet_profile.birthdate else None,
                "gender": pet_profile.gender.value if pet_profile.gender else None,
                "breed": pet_profile.breed
            })
        
        if view == 'social':
            # 멍스타그램 전용 정보 (나이 계산, 게시물 수)
            from datetime import date
            if pet_profile.birthdate:
                today = date.today()
                age_months = (today.year - pet_profile.birthdate.year) * 12 + (today.month - pet_profile.birthdate.month)
                response_data["age_months"] = age_months
            
            # 게시물 수 조회 (posts 서비스 사용)
            posts_service = current_app.services.get('posts')
            if posts_service:
                post_count = posts_service.get_user_post_count(target_user_id)
                response_data["post_count"] = post_count
            else:
                response_data["post_count"] = 0
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logging.error(f"Pet profile API error (target_user_id: {target_user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "서버 오류가 발생했습니다."}), 500