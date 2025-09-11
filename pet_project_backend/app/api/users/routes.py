# app/api/users/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.users.schemas import (
    UserPublicResponseSchema,
    FCMTokenSchema,
    NotificationPreferencesSchema,
)
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, UserErrors
)
from app.utils.error_catalog import build_error

users_bp = Blueprint('users_bp', __name__)

@users_bp.route('/<string:user_id>/public', methods=['GET'])
@jwt_required(optional=True)
@api_doc(
    summary="[DEPRECATED] 사용자 공개 정보 조회",
    description="[DEPRECATED] 이 엔드포인트는 더 이상 사용되지 않습니다. 대신 GET /api/pets/profile?view=social&user_id={user_id}를 사용하세요.",
    tags=["users"]
)
@error_responses(
    UserErrors.USER_NOT_FOUND,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "user_public_info_deprecated",
    "summary": "[DEPRECATED] 사용자 공개 정보",
    "description": "이 응답 형식은 더 이상 사용되지 않습니다. Pet profile API를 사용하세요.",
    "value": {
        "user_id": "user_123",
        "nickname": "사용자",
        # profile_image_url은 Pet 정보에서 가져오도록 변경됨
        "post_count": 25
    }
})
def get_user_public_info(user_id: str):
    """[DEPRECATED] 다른 사용자의 공개 프로필 정보를 조회합니다."""
    # 로그에 deprecation 경고 기록
    import warnings
    warnings.warn("GET /api/users/{user_id}/public is deprecated. Use GET /api/pets/profile?view=social&user_id={user_id} instead.", DeprecationWarning, stacklevel=2)
    logging.warning(f"DEPRECATED API called: GET /api/users/{user_id}/public. Client should migrate to Pet profile API.")
    
    user_service = current_app.services['users']
    try:
        user_info = user_service.get_user_public_info(user_id)
        return jsonify(user_info), 200
    except FileNotFoundError:
        status, body = build_error('USER_NOT_FOUND')
        return jsonify(body), status
    except Exception as e:
        logging.error(f"사용자 공개 정보 조회 오류 (user_id: {user_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED')
        return jsonify(body), status

@users_bp.route('/me', methods=['GET'])
@jwt_required()
@api_doc(
    summary="내 기본 정보 조회",
    description="현재 로그인한 사용자의 기본 정보를 조회합니다.",
    tags=["users"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "my_info",
    "summary": "내 기본 정보",
    "description": "현재 사용자의 기본 정보",
    "value": {
        "user_id": "user_123",
        "nickname": "내닉네임",
        "email": "user@example.com"
        # profile_image_url은 Pet 정보에서 가져오도록 변경됨
    }
})
def get_my_info():
    """현재 로그인한 사용자의 기본 정보를 조회합니다."""
    user_profile_service = current_app.services['user_profile']
    try:
        current_user_id = get_jwt_identity()
        user_info = user_profile_service.get_user_profile(current_user_id)
        
        if not user_info:
            status, body = build_error('USER_NOT_FOUND')
            return jsonify(body), status
            
        # Return only safe fields for my info
        response_data = {
            'user_id': current_user_id,
            'nickname': user_info.get('nickname'),
            'email': user_info.get('email'),
            'has_pet': user_info.get('has_pet', False),
            'pet_id': user_info.get('pet_id')
        }
        
        return jsonify(response_data), 200
    except Exception as e:
        logging.error(f"내 정보 조회 오류: {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED')
        return jsonify(body), status

@users_bp.route('/me/summary', methods=['GET'])
@jwt_required()
@api_doc(
    summary="내 통합 요약 정보 조회",
    description="사용자 정보, 반려동물 정보, 펫케어 설정을 통합한 요약 정보를 조회합니다. 프로필 페이지와 마이페이지에서 사용합니다.",
    tags=["users"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "my_summary",
    "summary": "내 통합 요약 정보",
    "description": "사용자, 반려동물, 펫케어 설정의 통합 정보",
    "value": {
        "user": {
            "user_id": "user_123",
            "nickname": "내닉네임",
            # profile_image_url은 Pet 정보에서 가져오도록 변경됨
            "post_count": 25
        },
        "pet": {
            "pet_id": "pet_456",
            "name": "맥스",
            "breed": "골든 리트리버",
            "profile_image_url": "https://example.com/pet.jpg",
            "is_verified": True
        },
        "pet_care_settings": {
            "daily_meal_count": 2,
            "target_daily_meal_count": 3,
            "target_daily_activity_minutes": 120,
            "target_weight": 26.5
        }
    }
})
def get_my_summary():
    """사용자, 반려동물, 펫케어 설정의 통합 요약 정보를 조회합니다."""
    try:
        current_user_id = get_jwt_identity()
        
        # 각 서비스에서 정보 조회
        user_profile_service = current_app.services['user_profile']
        pets_service = current_app.services['pets']
        settings_service = current_app.services.get('pet_care_settings')
        
        # 사용자 정보
        user_info = user_profile_service.get_user_profile(current_user_id)
        
        if not user_info:
            status, body = build_error('USER_NOT_FOUND')
            return jsonify(body), status
        
        # 반려동물 정보 (단일 반려동물 전제)
        pet_info = pets_service.get_user_pet(current_user_id)
        
        # 펫케어 설정 정보
        settings_info = None
        if settings_service and pet_info:
            try:
                settings_info = settings_service.get_settings(pet_info['pet_id'])
            except FileNotFoundError:
                settings_info = None
        
        result = {
            "user": user_info,
            "pet": pet_info,
            "pet_care_settings": settings_info
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"통합 요약 정보 조회 오류: {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED')
        return jsonify(body), status

@users_bp.route('/me/notification-preferences', methods=['GET'])
@jwt_required()
@api_doc(
    summary="알림 설정 조회",
    description="현재 사용자의 알림 설정을 조회합니다.",
    tags=["users"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "notification_preferences",
    "summary": "알림 설정",
    "description": "사용자의 알림 설정 정보",
    "value": {
        "push_enabled": True,
        "email_enabled": False,
        "marketing_enabled": True
    }
})
def get_notification_preferences():
    """현재 사용자의 알림 설정을 조회합니다."""
    user_profile_service = current_app.services['user_profile']
    try:
        current_user_id = get_jwt_identity()
        preferences = user_profile_service.get_notification_preferences(current_user_id)
        return jsonify(NotificationPreferencesSchema().dump(preferences)), 200
    except Exception as e:
        logging.error(f"알림 설정 조회 오류: {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED')
        return jsonify(body), status

@users_bp.route('/me/notification-preferences', methods=['PUT'])
@jwt_required()
@api_doc(
    summary="알림 설정 수정",
    description="현재 사용자의 알림 설정을 수정합니다.",
    tags=["users"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "update_notification_preferences",
    "summary": "알림 설정 수정",
    "description": "알림 설정 변경 요청",
    "value": {
        "push_enabled": False,
        "email_enabled": True,
        "marketing_enabled": False
    }
})
def update_notification_preferences():
    """현재 사용자의 알림 설정을 수정합니다."""
    user_profile_service = current_app.services['user_profile']
    try:
        current_user_id = get_jwt_identity()
        preferences_data = NotificationPreferencesSchema().load(request.get_json() or {})
        
        updated_preferences = user_profile_service.update_notification_preferences(current_user_id, preferences_data)
        return jsonify(NotificationPreferencesSchema().dump(updated_preferences)), 200
        
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except Exception as e:
        logging.error(f"알림 설정 수정 오류: {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED')
        return jsonify(body), status

@users_bp.route('/me/fcm-token', methods=['PUT'])
@jwt_required()
@api_doc(
    summary="FCM 토큰 업데이트",
    description="푸시 알림을 위한 FCM 토큰을 업데이트합니다.",
    tags=["users"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "update_fcm_token",
    "summary": "FCM 토큰 업데이트",
    "description": "새로운 FCM 토큰 설정",
    "value": {
        "fcm_token": "new_fcm_token_123"
    }
})
def update_fcm_token():
    """현재 사용자의 FCM 토큰을 업데이트합니다."""
    user_profile_service = current_app.services['user_profile']
    try:
        current_user_id = get_jwt_identity()
        token_data = FCMTokenSchema().load(request.get_json() or {})
        
        user_profile_service.update_fcm_token(current_user_id, token_data['fcm_token'])
        return jsonify({"message": "FCM 토큰이 업데이트되었습니다."}), 200
        
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except Exception as e:
        logging.error(f"FCM 토큰 업데이트 오류: {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED')
        return jsonify(body), status
