from flask import Blueprint, request, jsonify, current_app
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google_auth_oauthlib.flow import Flow
import os

from . import services as auth_services
from app.core.security import create_access_token, create_refresh_token
from app.schemas.user_schema import UserSchema

auth_bp = Blueprint('auth', __name__)
user_schema = UserSchema()

@auth_bp.route('/social', methods=['POST'])
def social_login():
    """
    클라이언트(앱)로부터 받은 소셜 인증 코드를 검증하고,
    로그인 또는 회원가입 처리 후 JWT 토큰을 발급합니다.
    """
    data = request.get_json()
    provider = data.get('provider')
    auth_code = data.get('auth_code')

    if not provider or not auth_code:
        return jsonify({"error_code": "INVALID_INPUT", "message": "Provider and auth code are required."}), 400

    if provider == 'google':
        try:
            client_secrets_file = current_app.config['GOOGLE_CLIENT_SECRETS_PATH']
            if not os.path.exists(client_secrets_file):
                 raise FileNotFoundError("Google client secrets file not found.")

            # 앱(클라이언트)에서 전달된 인증 코드를 토큰으로 교환합니다.
            flow = Flow.from_client_secrets_file(
                client_secrets_file=client_secrets_file,
                scopes=None,
                redirect_uri='postmessage' # 모바일/웹 클라이언트용 코드 교환 시 사용
            )
            flow.fetch_token(code=auth_code)
            credentials = flow.credentials
            
            # 발급받은 ID 토큰을 검증하여 사용자 정보를 가져옵니다.
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, 
                google_requests.Request(), 
                credentials.client_id
            )

            # 서비스 계층을 호출하여 사용자를 DB에서 찾거나 생성합니다.
            user, is_new_user = auth_services.get_or_create_user_from_google(id_info)

            # 서비스 전용 JWT를 생성합니다.
            jwt_payload = {'user_id': user.id, 'email': user.email}
            access_token = create_access_token(data=jwt_payload)
            refresh_token = create_refresh_token(data=jwt_payload)
            
            return jsonify({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "is_new_user": is_new_user
            }), 200

        except Exception as e:
            # 프로덕션 환경에서는 상세 에러를 로그로 남기는 것이 좋습니다.
            print(f"An error occurred during Google authentication: {e}")
            return jsonify({"error_code": "AUTHENTICATION_FAILED", "message": "Google authentication failed."}), 401
    
    return jsonify({"error_code": "UNSUPPORTED_PROVIDER", "message": "Unsupported provider."}), 400
