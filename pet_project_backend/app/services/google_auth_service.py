# 파일 경로: app/services/google_auth_service.py 

import logging
import requests
import jwt
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleAuthRequest

class GoogleAuthService:
    """실제 Google OAuth 2.0 통신을 담당하는 서비스 클래스입니다."""
    # --- 'httpso' -> 'https'로 수정 ---
    _user_info_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    
    @staticmethod
    def get_user_info_from_tokens(access_token: str, id_token: str) -> dict:
        """
        Access Token과 ID Token을 직접 받아서 사용자 정보를 가져옵니다.
        """
        try:
            # 디버깅을 위한 토큰 정보 로깅 (토큰의 일부만)
            logging.info(f"Access token 길이: {len(access_token) if access_token else 0}")
            logging.info(f"ID token 길이: {len(id_token) if id_token else 0}")
            logging.info(f"Access token 시작: {access_token[:20] if access_token else 'None'}...")
            
            # 1. Access Token을 사용하여 사용자 정보를 요청합니다.
            headers = {"Authorization": f"Bearer {access_token}"}
            logging.info(f"요청 URL: {GoogleAuthService._user_info_url}")
            logging.info(f"요청 헤더: {headers}")
            
            response = requests.get(
                GoogleAuthService._user_info_url,
                headers=headers
            )
            
            logging.info(f"응답 상태 코드: {response.status_code}")
            logging.info(f"응답 헤더: {dict(response.headers)}")
            logging.info(f"응답 내용: {response.text}")
            
            response.raise_for_status()
            user_info = response.json()
            
            # 2. ID Token에서 추가 정보를 추출합니다 (선택사항)
            try:
                # ID Token을 디코딩하여 추가 정보 확인
                decoded_token = jwt.decode(id_token, options={"verify_signature": False})
                logging.info(f"ID Token 디코딩 성공: {decoded_token.get('email', 'no email')}")
                # 필요한 경우 ID Token의 정보를 user_info에 추가
                user_info['id_token_data'] = {
                    'iss': decoded_token.get('iss'),
                    'aud': decoded_token.get('aud'),
                    'exp': decoded_token.get('exp')
                }
            except Exception as e:
                logging.warning(f"ID Token 디코딩 실패 (무시됨): {e}")
            
            logging.info(f"최종 사용자 정보: {user_info}")
            return user_info

        except Exception as e:
            logging.error(f"Google OAuth token validation failed: {e}", exc_info=True)
            return None
    
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