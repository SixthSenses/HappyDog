import os
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv  # 맨 위 import 목록에 있는지 확인
from marshmallow import ValidationError
from flask_jwt_extended import JWTManager
import firebase_admin
from firebase_admin import credentials

# --- 수정된 부분 ---
# 모든 모듈이 import 되기 전에 가장 먼저 .env 파일을 로드합니다.
load_dotenv()
# --------------------

from app.core.config import config_by_name
from app.api.auth.routes import auth_bp, auth_service
from app.api.mypage.routes import mypage_bp, pet_service 
# ----------------------------------------------------

def create_app():
    """
    .env 파일의 FLASK_ENV 값에 따라 자동으로 설정을 적용하여 
    Flask 앱을 생성하는 팩토리 함수입니다.
    """
    
    config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    app.json.ensure_ascii = False

    # --- 필수 설정값 검증 로직 ---
    required_configs = ['JWT_SECRET_KEY', 'FIREBASE_CREDENTIALS_PATH']
    for config_key in required_configs:
        if not app.config.get(config_key):
            raise ValueError(f"Required configuration '{config_key}' is not set. Please check your .env file.")
    # ----------------------------

    JWTManager(app)

    if not firebase_admin._apps:
        cred_path = app.config['FIREBASE_CREDENTIALS_PATH']
        if not os.path.exists(cred_path):
            raise ValueError(f"Firebase credentials path not found: {cred_path}")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

    # --- 수정된 부분 2: 서비스 객체 초기화 ---
    # Firebase 앱 초기화가 끝난 이 시점에서, 서비스 객체들의 init_app 메서드를 호출하여
    # 안전하게 DB 연결을 완료합니다.
    auth_service.init_app()
    pet_service.init_app()
    # ----------------------------------------
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')

    # Blueprint 등록
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(mypage_bp, url_prefix='/api/mypage')

    @app.errorhandler(ValidationError)
    def handle_marshmallow_validation(err):
        response = {
            "error_code": "VALIDATION_ERROR",
            "message": "입력값 유효성 검사에 실패했습니다.",
            "details": err.messages
        }
        return jsonify(response), 400

    return app