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

from app.api.auth.schemas import (
    SocialLoginSchema,
    LogoutRequestSchema,
    AuthTokensResponseSchema,
    AuthLogoutResponseSchema,
    AuthorizationUrlResponseSchema,
)
from app.utils.error_catalog import build_error
from app.services.google_auth_service import GoogleAuthService
from app.utils.api_documentation import CommonErrors, AuthErrors
# Removed direct import - use DI container pattern
# from .services import auth_service
from google_auth_oauthlib.flow import Flow
from app.middleware.idempotency_middleware import idempotent_endpoint

auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/google/authorize', methods=['GET'])
def google_authorize():
    """Google OAuth 인증 URL을 생성하거나 선택적으로 바로 리다이렉트합니다.

    query parameters:
      - redirect=true|1: 생성된 URL로 302 리다이렉트, 아니면 JSON 반환

    ResponseSchema[200]: AuthorizationUrlResponseSchema
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
        status, body = build_error('FETCH_FAILED', message="인증 URL 생성 중 오류가 발생했습니다.")
        return jsonify(body), status

@auth_bp.route('/social', methods=['POST'])
@idempotent_endpoint(apply_when_methods=('POST',))
def social_login():
    """소셜 로그인 및 신규 사용자 자동 가입 처리.

    RequestSchema: SocialLoginSchema
    ResponseSchema[200]: AuthTokensResponseSchema
    """
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
            status, body = build_error('FORBIDDEN', message="유효하지 않은 인증 코드이거나 사용자 정보 조회에 실패했습니다.")
            return jsonify(body), status

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
        status, body = build_error('FETCH_FAILED', message="서버 내부 오류가 발생했습니다.")
        return jsonify(body), status


# 브라우저 콜백용: GET /api/auth/social?code=...
@auth_bp.route('/social', methods=['GET'])
def social_login_callback():
    """OAuth 동의 후 리디렉션 콜백.

    query parameters:
      - code: Google OAuth authorization code

    ResponseSchema[200]: AuthTokensResponseSchema
    """
    try:
        code = request.args.get('code')
        if not code:
            status, body = build_error('VALIDATION_ERROR', message="code 파라미터가 필요합니다.")
            return jsonify(body), status

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
            status, body = build_error('FORBIDDEN', message="유효하지 않은 인증 코드이거나 사용자 정보 조회에 실패했습니다.")
            return jsonify(body), status

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
        status, body = build_error('FETCH_FAILED', message="서버 내부 오류가 발생했습니다.")
        return jsonify(body), status


# --- 토큰 재발급 엔드포인트 ---
@auth_bp.route('/token/refresh', methods=['POST'])
@jwt_required(refresh=True)  # Refresh Token만 허용
def refresh_token():
    """유효한 Refresh Token으로 새로운 Access Token 재발급.

    RequestSchema: EmptyRequestSchema
    ResponseSchema[200]: AuthTokensRefreshResponseSchema
    """
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
    """로그아웃 처리 및 Access/Refresh 토큰 블랙리스트 등록.

    RequestSchema: LogoutRequestSchema
    ResponseSchema[200]: AuthLogoutResponseSchema
    """
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
        status, body = build_error('VALIDATION_ERROR', details=e.messages)
        return jsonify(body), status
    except jwt.PyJWTError as e:
        logging.error(f"JWT 해독 오류 발생: {e}", exc_info=True)
        status, body = build_error('FORBIDDEN', message="유효하지 않은 토큰입니다.")
        return jsonify(body), status
    except Exception as e:
        logging.error(f"로그아웃 처리 중 오류 발생: {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED', message="로그아웃 처리 중 오류가 발생했습니다.")
        return jsonify(body), status