# app/api/auth/routes.py

import logging
import jwt
from flask import Blueprint, request, jsonify, current_app, redirect
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
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, AuthErrors, ExternalServiceErrors, RequestExamples, ResponseExamples
)
# Removed direct import - use DI container pattern
# from .services import auth_service
from google_auth_oauthlib.flow import Flow

auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/google/authorize', methods=['GET'])
@api_doc(
    summary="Google OAuth 인증 URL 생성",
    description="Google OAuth 인증을 위한 URL을 생성하거나 즉시 리다이렉트합니다. redirect 파라미터가 true이면 생성된 URL로 바로 302 리다이렉트하고, 아니면 JSON으로 authorization_url을 반환합니다.",
    tags=["auth"]
)
@error_responses(
    AuthErrors.MISSING_CLIENT_SECRETS,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "authorization_url_response",
    "summary": "인증 URL 응답",
    "description": "Google OAuth 인증 URL과 관련 정보",
    "value": {
        "authorization_url": "https://accounts.google.com/oauth/authorize?...",
        "redirect_uri": "http://localhost:5000/api/auth/social",
        "state": "state_value"
    }
})
def google_authorize():
    """Google OAuth 인증 URL을 생성하거나 즉시 리다이렉트합니다.

    query:
      - redirect=true|1 이면 생성된 URL로 바로 302 리다이렉트
      - 아니면 JSON으로 authorization_url 반환
    """
    try:
        client_secrets_path = current_app.config['GOOGLE_CLIENT_SECRETS_PATH']
        if not client_secrets_path:
            raise ValueError("GOOGLE_CLIENT_SECRETS_PATH is not configured.")
        redirect_uri = current_app.config.get('GOOGLE_OAUTH_REDIRECT_URI')

        flow = Flow.from_client_secrets_file(
            client_secrets_path,
            scopes=[
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/userinfo.email",
                "openid",
            ],
        )
        flow.redirect_uri = redirect_uri

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
        )

        if str(request.args.get('redirect', '')).lower() in ('1', 'true', 'yes'):
            return redirect(authorization_url)

        return jsonify({
            "authorization_url": authorization_url,
            "redirect_uri": redirect_uri,
            "state": state
        }), 200
    except Exception as e:
        logging.error(f"인증 URL 생성 중 오류: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "인증 URL 생성 중 오류가 발생했습니다."}), 500

@auth_bp.route('/social', methods=['POST'])
@api_doc(
    summary="소셜 로그인",
    description="Google OAuth 코드를 사용하여 소셜 로그인 및 회원가입을 처리합니다. 기존 사용자는 로그인하고, 신규 사용자는 자동으로 계정이 생성됩니다.",
    tags=["auth"]
)
@error_responses(
    CommonErrors.VALIDATION_ERROR,
    AuthErrors.INVALID_SOCIAL_TOKEN,
    AuthErrors.MISSING_CLIENT_SECRETS,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "social_login_request",
    "summary": "소셜 로그인 요청",
    "description": "Google OAuth 인증 코드를 포함한 로그인 요청",
    "value": {"auth_code": "4/0AdQt8qh..."}
})
@response_examples({
    "name": "social_login_success",
    "summary": "성공적인 소셜 로그인",
    "description": "JWT 토큰과 사용자 정보를 포함한 로그인 성공 응답",
    "value": {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
        "user_id": "user_123",
        "is_new_user": True,
        "user_info": {
            "user_id": "user_123",
            "email": "user@example.com",
            "nickname": "사용자"
        }
    }
})
def social_login():
    """소셜 로그인 및 회원가입을 처리하는 엔드포인트입니다."""
    try:
        validated_data = SocialLoginSchema().load(request.get_json())
        client_secrets_path = current_app.config['GOOGLE_CLIENT_SECRETS_PATH']
        if not client_secrets_path:
            raise ValueError("GOOGLE_CLIENT_SECRETS_PATH is not configured.")
        redirect_uri = current_app.config.get('GOOGLE_OAUTH_REDIRECT_URI')

        google_user_info = GoogleAuthService.exchange_code_for_user_info(
            auth_code=validated_data['auth_code'],
            client_secrets_path=client_secrets_path,
            redirect_uri=redirect_uri
        )

        if not google_user_info:
            return jsonify({"error_code": "INVALID_AUTH_CODE", "message": "유효하지 않은 인증 코드이거나 사용자 정보 조회에 실패했습니다."}), 401

        # Use DI container pattern for consistent service access
        auth_service = current_app.services['auth']
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
                "nickname": user.nickname
            }
        }), 200
    except Exception as e:
        logging.error(f"소셜 로그인 중 예외 발생: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "서버 내부 오류가 발생했습니다."}), 500


# 브라우저 콜백용: GET /api/auth/social?code=...
@auth_bp.route('/social', methods=['GET'])
@api_doc(
    summary="소셜 로그인 콜백",
    description="Google OAuth 동의 후 리디렉션되는 콜백 엔드포인트입니다. 쿼리스트링의 code로 토큰 교환을 수행합니다.",
    tags=["auth"]
)
@error_responses(
    CommonErrors.VALIDATION_ERROR,
    AuthErrors.INVALID_SOCIAL_TOKEN,
    AuthErrors.MISSING_CLIENT_SECRETS,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "callback_success",
    "summary": "콜백 처리 성공",
    "description": "OAuth 콜백 처리 후 JWT 토큰과 사용자 정보 반환",
    "value": {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
        "user_id": "user_123",
        "is_new_user": False,
        "user_info": {
            "user_id": "user_123",
            "email": "user@example.com",
            "nickname": "사용자"
        }
    }
})
def social_login_callback():
    """OAuth 동의 후 리디렉션되는 콜백. 쿼리스트링의 code로 토큰 교환 수행."""
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({"error_code": "INVALID_REQUEST", "message": "code 파라미터가 필요합니다."}), 400

        client_secrets_path = current_app.config['GOOGLE_CLIENT_SECRETS_PATH']
        if not client_secrets_path:
            raise ValueError("GOOGLE_CLIENT_SECRETS_PATH is not configured.")
        redirect_uri = current_app.config.get('GOOGLE_OAUTH_REDIRECT_URI')

        google_user_info = GoogleAuthService.exchange_code_for_user_info(
            auth_code=code,
            client_secrets_path=client_secrets_path,
            redirect_uri=redirect_uri
        )

        if not google_user_info:
            return jsonify({"error_code": "INVALID_AUTH_CODE", "message": "유효하지 않은 인증 코드이거나 사용자 정보 조회에 실패했습니다."}), 401

        # Use DI container pattern for consistent service access
        auth_service = current_app.services['auth']
        user, is_new_user = auth_service.get_or_create_user_by_google(google_user_info)

        identity = user.user_id
        access_token = create_access_token(identity=identity)
        refresh_token = create_refresh_token(identity=identity)

        return jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user.user_id,
            "is_new_user": is_new_user,
            "user_info": {
                "user_id": user.user_id,
                "email": user.email,
                "nickname": user.nickname
            }
        }), 200
    except Exception as e:
        logging.error(f"소셜 로그인 콜백 처리 중 예외 발생: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "서버 내부 오류가 발생했습니다."}), 500


# --- 토큰 재발급 엔드포인트 ---
@auth_bp.route('/token/refresh', methods=['POST'])
@jwt_required(refresh=True) # Refresh Token만 허용하는 데코레이터
@api_doc(
    summary="액세스 토큰 재발급",
    description="유효한 Refresh Token으로 새로운 Access Token을 발급합니다. Authorization 헤더에 Bearer refresh_token을 포함해야 합니다.",
    tags=["auth"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    AuthErrors.TOKEN_REFRESH_FAILED
)
@response_examples({
    "name": "token_refresh_success",
    "summary": "토큰 재발급 성공",
    "description": "새로운 액세스 토큰이 성공적으로 발급됨",
    "value": {"access_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."}
})
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
@api_doc(
    summary="로그아웃",
    description="사용자를 로그아웃하고 전달받은 Access/Refresh 토큰을 무효화 목록에 추가합니다.",
    tags=["auth"]
)
@error_responses(
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.INVALID_JWT,
    AuthErrors.LOGOUT_FAILED,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "logout_request",
    "summary": "로그아웃 요청",
    "description": "무효화할 액세스 토큰과 리프레시 토큰",
    "value": {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
    }
})
@response_examples({
    "name": "logout_success",
    "summary": "로그아웃 성공",
    "description": "성공적인 로그아웃 처리",
    "value": {"message": "로그아웃 되었습니다."}
})
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

        # Use DI container pattern for consistent service access
        auth_service = current_app.services['auth']
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