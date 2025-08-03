# 파일 경로: app/services/google_auth_service.py 

import logging
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleAuthRequest

class GoogleAuthService:
    """실제 Google OAuth 2.0 통신을 담당하는 서비스 클래스입니다."""
    # --- 'httpso' -> 'https'로 수정 ---
    _user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    
    @staticmethod
    def exchange_code_for_user_info(auth_code: str, client_secrets_path: str) -> dict:
        """
        인증 코드를 Access Token으로 교환하고, 이를 사용해 사용자 정보를 가져옵니다.
        """
        try:
            # 1. OAuth 2.0 Flow 객체를 생성합니다.
            flow = Flow.from_client_secrets_file(
                client_secrets_path,
                scopes=[
                    # --- 'httpso' -> 'https'로 수정 ---
                    "https://www.googleapis.com/auth/userinfo.profile",
                    "https://www.googleapis.com/auth/userinfo.email",
                    "openid"
                ]
            )
            
            # --- 'httpso' -> 'https'로 수정 ---
            flow.redirect_uri = "https://developers.google.com/oauthplayground"

            # 2. 인증 코드를 사용해 Access Token 및 Refresh Token으로 교환합니다.
            flow.fetch_token(code=auth_code)

            # 3. 획득한 인증 정보(credentials)를 가져옵니다.
            credentials = flow.credentials

            # 4. Access Token을 사용하여 사용자 정보를 요청합니다.
            response = requests.get(
                GoogleAuthService._user_info_url,
                headers={"Authorization": f"Bearer {credentials.token}"}
            )
            
            response.raise_for_status()
            
            return response.json()

        except Exception as e:
            logging.error(f"Google OAuth failed: {e}", exc_info=True)
            raise e