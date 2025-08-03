import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from marshmallow import ValidationError

from app.api.auth.schemas import SocialLoginSchema
from app.services.google_auth_service import GoogleAuthService
from .services import auth_service
auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/social', methods=['POST'])
def social_login():
    """소셜 로그인 및 회원가입을 처리하는 엔드포인트입니다. (실제 연동 버전)"""
    try:
        schema = SocialLoginSchema()
        validated_data = schema.load(request.get_json())
        
        # --- Mock 서비스 대신 실제 GoogleAuthService 사용 ---
        # 앱 설정에서 클라이언트 시크릿 파일 경로를 가져옵니다.
        client_secrets_path = current_app.config['GOOGLE_CLIENT_SECRETS_PATH']
        if not client_secrets_path:
            raise ValueError("GOOGLE_CLIENT_SECRETS_PATH is not configured.")

        # 실제 서비스의 메서드를 호출하여 인증 코드를 사용자 정보와 교환합니다.
        google_user_info = GoogleAuthService.exchange_code_for_user_info(
            auth_code=validated_data['auth_code'],
            client_secrets_path=client_secrets_path
        )
        # ---------------------------------------------------

        if not google_user_info:
            return jsonify({"error_code": "INVALID_AUTH_CODE", "message": "유효하지 않은 인증 코드이거나 사용자 정보 조회에 실패했습니다."}), 401

        user, is_new_user = auth_service.get_or_create_user_by_google(google_user_info)
        
        identity = user.user_id
        access_token = create_access_token(identity=identity)
        refresh_token = create_refresh_token(identity=identity)

        return jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "is_new_user": is_new_user
        }), 200
    except Exception as e:
        logging.error(f"An unexpected error occurred during social login: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "서버 내부 오류가 발생했습니다."}), 500