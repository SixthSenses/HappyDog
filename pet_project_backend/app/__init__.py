# app/__init__.py

import os
import logging
from flask import Flask, jsonify
from dotenv import load_dotenv
from marshmallow import ValidationError
from flask_jwt_extended import JWTManager
import firebase_admin
from firebase_admin import credentials

# 애플리케이션의 다른 모듈들이 로드되기 전에 환경 변수를 로드합니다.
load_dotenv()

# --- 프로젝트의 핵심 컴포넌트들을 임포트합니다. ---
from app.core.config import config_by_name

# [수정] 새로 만든 uploads 블루프린트를 임포트합니다.
from app.api.auth.routes import auth_bp
from app.api.mypage.routes import mypage_bp
from app.api.uploads.routes import uploads_bp 

from app.api.auth.services import auth_service
from app.api.mypage.services import pet_service
from app.services.storage_service import StorageService
from nose_lib.pipelines.nose_print_pipeline import NosePrintPipeline

def create_app():
    """
    Flask 애플리케이션 팩토리 함수.
    서버 시작 시 필요한 모든 초기화와 설정을 담당합니다.
    """
    
    config_name = os.getenv('FLASK_ENV', 'development')
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    app.json.ensure_ascii = False

    # --- 필수 환경 변수 검증 ---
    required_configs = [
        'JWT_SECRET_KEY', 
        'FIREBASE_CREDENTIALS_PATH',
        'FIREBASE_STORAGE_BUCKET'
    ]
    for config_key in required_configs:
        if not app.config.get(config_key):
            raise ValueError(f"필수 설정값이 없습니다: '{config_key}'. .env 파일을 확인해주세요.")
    
    # --- JWT 초기화 ---
    JWTManager(app)

    # --- Firebase Admin SDK 초기화 ---
    # 앱 인스턴스가 여러 개 생성되는 것을 방지하기 위해 `if not firebase_admin._apps:` 체크를 합니다.
    if not firebase_admin._apps:
        cred_path = app.config['FIREBASE_CREDENTIALS_PATH']
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"Firebase 인증 파일을 찾을 수 없습니다: {cred_path}")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            'storageBucket': app.config['FIREBASE_STORAGE_BUCKET']
        })

    # --- 서비스 인스턴스 생성 및 등록 ---
    # API 요청 처리 시 재사용할 서비스 객체들을 앱 컨텍스트(app.services)에 저장합니다.
    # 이렇게 하면 앱 시작 시점에 한 번만 생성되어 메모리 효율성이 높아집니다.
    app.services = {}

    # ML 파이프라인 초기화: 무거운 모델을 메모리에 미리 로드하여 API 응답 속도를 향상시킵니다.
    yolo_path = os.getenv('YOLO_WEIGHTS_PATH')
    config_path = os.getenv('ML_CONFIG_PATH')
    extractor_path = os.getenv('EXTRACTOR_WEIGHTS_PATH')
    faiss_path = os.getenv('FAISS_INDEX_PATH')
    
    if not all([yolo_path, config_path, extractor_path, faiss_path]):
        raise ValueError("ML 모델 경로 환경변수가 모두 설정되지 않았습니다. (.env 파일 확인)")

    pipeline_instance = NosePrintPipeline(
        yolo_weights_path=yolo_path,
        config_path=config_path,
        extractor_weights_path=extractor_path,
        faiss_index_path=faiss_path
    )
    app.services['pipeline'] = pipeline_instance

    # Storage 서비스 초기화 및 등록
    storage_instance = StorageService()
    storage_instance.init_app(app)
    app.services['storage'] = storage_instance
    
    # 기존 서비스(DB 연결 등) 초기화
    auth_service.init_app()
    pet_service.init_app()
    
    # --- 로깅 설정 ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')

    # --- Blueprint 등록 ---
    # 각 기능별 API 엔드포인트에 url_prefix를 명확하게 지정하여 API 주소를 구조화합니다.
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(mypage_bp, url_prefix='/api/mypage')
    
    # [수정] 새로 만든 uploads 블루프린트를 '/api/uploads' 경로에 등록합니다.
    app.register_blueprint(uploads_bp, url_prefix='/api/uploads')

    # --- 공통 에러 핸들러 등록 ---
    # Marshmallow 스키마 유효성 검사 실패 시 일관된 형식의 400 에러를 반환합니다.
    @app.errorhandler(ValidationError)
    def handle_marshmallow_validation(err):
        response = {
            "error_code": "VALIDATION_ERROR",
            "message": "입력값 유효성 검사에 실패했습니다.",
            "details": err.messages
        }
        return jsonify(response), 400

    logging.info("Flask 앱 생성 및 모든 컴포넌트 초기화 완료.")
    return app
