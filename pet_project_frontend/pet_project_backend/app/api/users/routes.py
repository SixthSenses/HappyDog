# app/api/users/routes.py
import logging
from flask import Blueprint, request, jsonify, Response,current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError


from app.api.users.schemas import UserPublicResponseSchema, FCMTokenSchema

users_bp = Blueprint('users_bp', __name__)

@users_bp.route('/<string:user_id>', methods=['GET'])
@jwt_required(optional=True)
def get_user_profile(user_id: str):
    user_service = current_app.services['users']
    """특정 사용자의 공개 프로필 정보(게시물 수 포함)를 조회합니다."""
    try:
        # 서비스 함수 이름을 get_user_profile로 변경
        user_profile = user_service.get_user_profile(user_id)
        if not user_profile:
            return jsonify({"error_code": "USER_NOT_FOUND", "message": "사용자를 찾을 수 없습니다."}), 404
        
        return jsonify(UserPublicResponseSchema().dump(user_profile)), 200
    except Exception as e:
        logging.error(f"사용자 프로필 조회 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "PROFILE_FETCH_FAILED", "message": "프로필 조회 중 오류가 발생했습니다."}), 500


@users_bp.route('/me/profile-image', methods=['PATCH'])
@jwt_required()
def update_my_profile_image():
    user_service = current_app.services['users']
    """
    현재 로그인된 사용자의 프로필 이미지를 업데이트합니다.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    file_path = data.get('file_path')

    if not file_path:
        return jsonify({"error_code": "INVALID_PAYLOAD", "message": "'file_path' 필드가 필요합니다."}), 400
    
    try:
        updated_user = user_service.update_user_profile_image(user_id, file_path)
        if not updated_user:
             return jsonify({"error_code": "USER_NOT_FOUND", "message": "사용자를 찾을 수 없습니다."}), 404
        
        # 전체 사용자 정보 대신 업데이트된 URL만 반환하거나, 혹은 공개 스키마를 사용할 수 있습니다.
        return jsonify(UserPublicResponseSchema().dump(updated_user)), 200
    except Exception as e:
        logging.error(f"프로필 이미지 업데이트 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "프로필 이미지 업데이트 중 서버 오류가 발생했습니다."}), 500


@users_bp.route('/me', methods=['DELETE'])
@jwt_required()
def delete_my_account():
    user_service = current_app.services['users']
    """
    현재 로그인된 사용자 본인의 계정을 영구적으로 삭제합니다.
    """
    user_id = get_jwt_identity()
    try:
        user_service.delete_user_account(user_id)
        # 성공 시에는 본문(body) 없이 204 상태 코드만 반환하는 것이 RESTful API 표준
        return Response(status=204)
    except Exception as e:
        logging.error(f"회원 탈퇴 처리 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "ACCOUNT_DELETION_FAILED", "message": "회원 탈퇴 처리 중 서버 오류가 발생했습니다."}), 500


@users_bp.route('/me/fcm-token', methods=['POST'])
@jwt_required()
def register_fcm_token():
    user_service = current_app.services['users']
    """
    클라이언트의 FCM 토큰을 등록/업데이트합니다.
    """
    user_id = get_jwt_identity()
    try:
        data = FCMTokenSchema().load(request.get_json())
        user_service.update_fcm_token(user_id, data['fcm_token'])
        return jsonify({"message": "FCM 토큰이 성공적으로 업데이트되었습니다."}), 200
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"FCM 토큰 업데이트 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "UPDATE_FAILED", "message": "FCM 토큰 업데이트 중 서버 오류가 발생했습니다."}), 500