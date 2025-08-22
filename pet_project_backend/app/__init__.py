# app/__init__.py

# =====================================================================================
# 1. 환경 변수 로드 (가장 먼저 실행)
# =====================================================================================
from dotenv import load_dotenv
load_dotenv()

# =====================================================================================
# 2. 모듈 임포트 (Module Imports)
# =====================================================================================
import os
import logging
from flask import Flask, jsonify
from marshmallow import ValidationError
from flask_jwt_extended import JWTManager
import firebase_admin
from firebase_admin import credentials

# - 설정
from app.core.config import config_by_name

# - API 블루프린트
from app.api.auth.routes import auth_bp
from app.api.uploads.routes import uploads_bp
from app.api.users.routes import users_bp
from app.api.posts.routes import posts_bp
from app.api.comments.routes import comments_bp
from app.api.cartoon_jobs.routes import cartoon_jobs_bp
from app.api.breeds.routes import breeds_bp
from app.api.pets.routes import pets_bp
from app.api.pet_care.settings.routes import pet_care_settings_bp
from app.api.pet_care.records.routes import pet_care_records_bp

# - 서비스 모듈
from app.services import storage_service as storage_service_module
from app.services import notification_service as notification_service_module
from app.services import openai_service as openai_service_module
from app.api.auth import services as auth_service_module
from app.api.users import services as user_service_module
from app.api.posts import services as post_service_module
from app.api.comments import services as comment_service_module
from app.api.cartoon_jobs import services as cartoon_job_service_module
from app.api.breeds.services import BreedService
from app.api.pets.services import PetService
from app.api.pet_care.settings.services import PetCareSettingService
from app.api.pet_care.records.services import PetCareRecordService

# - ML 모델 파이프라인
from nose_lib.pipelines.nose_print_pipeline import NosePrintPipeline
from eyes_models.eyes_lib.inference import EyeAnalyzer

def create_app():
    """
    Flask 애플리케이션 팩토리 함수.
    """
    # =====================================================================================
    # 3. Flask 앱 생성 및 기본 설정
    # =====================================================================================
    config_name = os.getenv('FLASK_ENV', 'development')
    
    # 필수 환경 변수 검증
    # required_env_vars = [
    #     'FIREBASE_CREDENTIALS_PATH',
    #     'FIREBASE_STORAGE_BUCKET',
    #     'JWT_SECRET_KEY'
    # ]
    
    # missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    # if missing_vars:
    #     raise ValueError(f"필수 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
    
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    app.json.ensure_ascii = False

    # =====================================================================================
    # 4. 확장 기능 및 외부 서비스 초기화
    # =====================================================================================
    JWTManager(app)

    if not firebase_admin._apps:
        cred_path = app.config['FIREBASE_CREDENTIALS_PATH']
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"Firebase 인증 파일을 찾을 수 없습니다: {cred_path}")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            'storageBucket': app.config['FIREBASE_STORAGE_BUCKET']
        })

    # =====================================================================================
    # 5. 서비스 인스턴스 생성 및 'app.services'에 저장 (의존성 주입)
    # =====================================================================================
    app.services = {}

    # 5-1. 의존성이 없거나 다른 서비스의 기반이 되는 공용/핵심 서비스 먼저 생성
    try:
        storage_instance = storage_service_module.StorageService()
        storage_instance.init_app(app)
        app.services['storage'] = storage_instance
        logging.info("Storage service initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize storage service: {e}")
        raise
    
    try:
        openai_instance = openai_service_module.OpenAIService()
        openai_instance.init_app(app)
        app.services['openai'] = openai_instance
        logging.info("OpenAI service initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize OpenAI service: {e}")
        raise

    app.services['notifications'] = notification_service_module.NotificationService()
    app.services['breeds'] = BreedService()
    
    # ML 파이프라인 초기화 (선택적)
    try:
        app.services['nose_pipeline'] = NosePrintPipeline(
            yolo_weights_path=os.getenv('YOLO_WEIGHTS_PATH'),
            config_path=os.getenv('ML_CONFIG_PATH'),
            extractor_weights_path=os.getenv('EXTRACTOR_WEIGHTS_PATH'),
            faiss_index_path=os.getenv('FAISS_INDEX_PATH')
        )
        logging.info("Nose print pipeline initialized successfully")
    except Exception as e:
        logging.warning(f"Failed to initialize nose pipeline: {e}")
        app.services['nose_pipeline'] = None
    
    try:
        app.services['eye_analyzer'] = EyeAnalyzer()
        logging.info("Eye analyzer initialized successfully")
    except Exception as e:
        logging.warning(f"Failed to initialize eye analyzer: {e}")
        app.services['eye_analyzer'] = None

    # 5-2. 다른 서비스를 주입받아야 하는 도메인 서비스 생성
    # - pet_care 도메인
    app.services['pet_care_settings'] = PetCareSettingService(breed_service=app.services['breeds'])
    app.services['pet_care_records'] = PetCareRecordService()

    # - pets 도메인
    app.services['pets'] = PetService(
        pet_care_setting_service=app.services['pet_care_settings'],
        storage_service=app.services['storage'],
        nose_pipeline=app.services['nose_pipeline'],
        eye_analyzer=app.services['eye_analyzer']
    )
    logging.info("Pet service initialized successfully")
    
    # - 나머지 도메인
    post_service_instance = post_service_module.PostService()
    app.services['posts'] = post_service_instance
    app.services['comments'] = comment_service_module.CommentService()
    app.services['users'] = user_service_module.UserService(
        storage_service=app.services['storage'],
        post_service=app.services['posts']
    )
    app.services['cartoon_jobs'] = cartoon_job_service_module.CartoonJobService(
        post_service=app.services['posts'],
        notification_service=app.services['notifications']
    )
    
    # - 인증 서비스 (앱 컨텍스트 필요)
    auth_service_module.auth_service.init_app(app)

    # =====================================================================================
    # 6. 블루프린트 등록
    # =====================================================================================
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(uploads_bp, url_prefix='/api/uploads')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(posts_bp, url_prefix='/api/posts')
    app.register_blueprint(comments_bp, url_prefix='/api/comments')
    app.register_blueprint(cartoon_jobs_bp, url_prefix='/api/cartoon-jobs')
    app.register_blueprint(breeds_bp, url_prefix='/api/breeds')
    
    # - pets 및 pet_care 도메인 블루프린트 등록
    app.register_blueprint(pets_bp, url_prefix='/api/pets')
    app.register_blueprint(pet_care_settings_bp, url_prefix='/api/pet-care')
    app.register_blueprint(pet_care_records_bp, url_prefix='/api/pet-care')

    # =====================================================================================
    # 7. 전역 에러 핸들러 설정
    # =====================================================================================
    @app.errorhandler(ValidationError)
    def handle_marshmallow_validation(err):
        response = {"error_code": "VALIDATION_ERROR", "details": err.messages}
        return jsonify(response), 400

    @app.errorhandler(Exception)
    def handle_generic_exception(err):
        # 다른 핸들러에서 처리되지 않은 모든 예외를 여기서 처리
        logging.error(f"An unhandled exception occurred: {err}", exc_info=True)
        response = {"error_code": "INTERNAL_SERVER_ERROR", "message": "서버 내부에서 예상치 못한 오류가 발생했습니다."}
        return jsonify(response), 500

    # =====================================================================================
    # 8. 로깅 및 앱 반환
    # =====================================================================================
    if not app.debug:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    
    logging.info(f"Flask app created for '{config_name}' environment.")
    
    return app