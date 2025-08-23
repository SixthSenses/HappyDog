# app/api/auth/routes.py

import logging
import jwt
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    decode_token
)
from marshmallow import ValidationError

from app.api.auth.schemas import SocialLoginSchema, LogoutRequestSchema
from app.services.google_auth_service import GoogleAuthService
from .services import auth_service

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/social', methods=['POST'])
def social_login():
    """소셜 로그인 및 회원가입을 처리하는 엔드포인트입니다."""
    try:
        validated_data = SocialLoginSchema().load(request.get_json())
        client_secrets_path = current_app.config['GOOGLE_CLIENT_SECRETS_PATH']
        if not client_secrets_path:
            raise ValueError("GOOGLE_CLIENT_SECRETS_PATH is not configured.")

        google_user_info = GoogleAuthService.exchange_code_for_user_info(
            auth_code=validated_data['auth_code'],
            client_secrets_path=client_secrets_path
        )

        if not google_user_info:
            return jsonify({"error_code": "INVALID_AUTH_CODE", "message": "유효하지 않은 인증 코드이거나 사용자 정보 조회에 실패했습니다."}), 401

        user, is_new_user = auth_service.get_or_create_user_by_google(google_user_info)
        
        identity = user.user_id
        access_token = create_access_token(identity=identity)
        refresh_token = create_refresh_token(identity=identity)

        return jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user.user_id,
            "is_new_user": is_new_user,
            "user_info": { # [개선] 신규/기존 유저 정보 함께 반환
                "user_id": user.user_id,
                "email": user.email,
                "nickname": user.nickname,
                "profile_image_url": user.profile_image_url
            }
        }), 200
    except Exception as e:
        logging.error(f"소셜 로그인 중 예외 발생: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "서버 내부 오류가 발생했습니다."}), 500


# --- 토큰 재발급 엔드포인트 ---
@auth_bp.route('/token/refresh', methods=['POST'])
@jwt_required(refresh=True) # Refresh Token만 허용하는 데코레이터
def refresh_token():
    """유효한 Refresh Token으로 새로운 Access Token을 발급합니다."""
    # @jwt_required(refresh=True) 데코레이터가 다음을 자동으로 검증합니다:
    # 1. 헤더에 토큰이 있는지
    # 2. 토큰 서명이 유효한지
    # 3. 토큰이 만료되지 않았는지
    # 4. 토큰 타입이 'refresh'인지
    # 5. 토큰이 Blocklist에 없는지 (우리가 등록한 콜백 함수 사용)
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id)
    return jsonify(access_token=new_access_token), 200


# --- 로그아웃 엔드포인트 ---
@auth_bp.route('/logout', methods=['POST'])
def logout():
    """로그아웃. 전달받은 Access/Refresh 토큰을 무효화 목록에 추가합니다."""
    try:
        data = LogoutRequestSchema().load(request.get_json())
        access_token_str = data['access_token']
        refresh_token_str = data['refresh_token']
        
        # 표준 JWT 라이브러리를 사용하여 토큰을 직접 해독합니다.
        # 이 방식은 CSRF 검사를 수행하지 않습니다.
        secret_key = current_app.config['JWT_SECRET_KEY']
        algorithm = current_app.config.get('JWT_ALGORITHM', 'HS256') # 설정이 없으면 기본값 HS256 사용

        # 만료된 토큰도 해독할 수 있도록 'verify_exp=False' 옵션을 추가합니다.
        decoded_access = jwt.decode(access_token_str, secret_key, algorithms=[algorithm], options={"verify_exp": False})
        decoded_refresh = jwt.decode(refresh_token_str, secret_key, algorithms=[algorithm], options={"verify_exp": False})

        access_jti = decoded_access['jti']
        access_exp = decoded_access['exp']
        refresh_jti = decoded_refresh['jti']
        refresh_exp = decoded_refresh['exp']

        auth_service.logout_user(access_jti, access_exp, refresh_jti, refresh_exp)

        return jsonify({"message": "로그아웃 되었습니다."}), 200

    except ValidationError as e:
         return jsonify({"error_code": "VALIDATION_ERROR", "details": e.messages}), 400
    except jwt.PyJWTError as e:
        # JWT 해독 자체에서 오류가 발생한 경우 (예: 토큰 형식이 잘못됨)
        logging.error(f"JWT 해독 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "INVALID_TOKEN", "message": "유효하지 않은 토큰입니다."}), 422
    except Exception as e:
        logging.error(f"로그아웃 처리 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "LOGOUT_FAILED", "message": "로그아웃 처리 중 오류가 발생했습니다."}), 500