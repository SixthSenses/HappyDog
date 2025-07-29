from flask import Blueprint, request, jsonify, redirect, current_app
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os

from . import services as auth_services
from app.core.security import create_access_token, create_refresh_token

auth_bp = Blueprint('auth', __name__)

def get_google_flow():
    client_secrets_file = current_app.config['GOOGLE_CLIENT_SECRETS_PATH']
    if not os.path.exists(client_secrets_file):
        raise FileNotFoundError(f"Google client secrets file not found at: {client_secrets_file}")

    return Flow.from_client_secrets_file(
        client_secrets_file=client_secrets_file,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ]
    )

@auth_bp.route('/login/google')
def google_login():
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    return redirect(authorization_url)

@auth_bp.route('/login/google/callback')
def google_callback():
    flow = get_google_flow()
    try:
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        id_info = id_token.verify_oauth2_token(
            credentials.id_token, google_requests.Request(), credentials.client_id)

        user = auth_services.get_or_create_user_from_google(id_info)

        jwt_payload = {'user_id': user.id, 'email': user.email}
        access_token = create_access_token(data=jwt_payload)
        refresh_token = create_refresh_token(data=jwt_payload)
        
        return jsonify({
            "message": "Login successful",
            "access_token": access_token,
            "refresh_token": refresh_token
        }), 200

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "Authentication failed"}), 401