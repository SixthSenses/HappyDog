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
from app.api.pets.routes import pets_bp
from app.api.posts.routes import posts_bp
from app.api.comments.routes import comments_bp
from app.api.cartoon_jobs.routes import cartoon_jobs_bp
# - 서비스 모듈
from app.services import storage_service as storage_service_module
from app.services import notification_service as notification_service_module
from app.services import openai_service as openai_service_module
from app.api.auth import services as auth_service_module
from app.api.users import services as user_service_module
from app.api.pets import services as pet_service_module
from app.api.posts import services as post_service_module
from app.api.comments import services as comment_service_module
from app.api.cartoon_jobs import services as cartoon_job_service_module
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
    # 5. 서비스 인스턴스 생성 및 'app.services'에 저장
    # =====================================================================================
    app.services = {}

    # 5-1. 독립적인 공용 서비스 및 ML 모델 생성
    storage_instance = storage_service_module.StorageService()
    storage_instance.init_app(app)
    app.services['storage'] = storage_instance
    
    app.services['notifications'] = notification_service_module.NotificationService()
    
    # OpenAI 서비스 초기화
    openai_instance = openai_service_module.OpenAIService()
    openai_instance.init_app(app)
    app.services['openai'] = openai_instance

    app.services['nose_pipeline'] = NosePrintPipeline(
        yolo_weights_path=os.getenv('YOLO_WEIGHTS_PATH'),
        config_path=os.getenv('ML_CONFIG_PATH'),
        extractor_weights_path=os.getenv('EXTRACTOR_WEIGHTS_PATH'),
        faiss_index_path=os.getenv('FAISS_INDEX_PATH')
    )
    
    app.services['eye_analyzer'] = EyeAnalyzer()

    # 5-2. 기능별 서비스 생성 (의존성 주입)
    auth_service_module.auth_service.init_app(app) # 인증 서비스는 기존 방식 유지
    
    post_service_instance = post_service_module.PostService()
    app.services['posts'] = post_service_instance
    
    app.services['users'] = user_service_module.UserService(
        storage_service=app.services['storage'],
        post_service=app.services['posts']
    )
    
    app.services['pets'] = pet_service_module.PetService(
        storage_service=app.services['storage'],
        nose_pipeline=app.services['nose_pipeline'],
        eye_analyzer=app.services['eye_analyzer']
    )
    
    app.services['comments'] = comment_service_module.CommentService()
    app.services['cartoon_jobs'] = cartoon_job_service_module.CartoonJobService(
        post_service=app.services['posts'],
        notification_service=app.services['notifications']
    )


    # =====================================================================================
    # 6. 블루프린트 등록
    # =====================================================================================
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(uploads_bp, url_prefix='/api/uploads')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(pets_bp, url_prefix='/api/pets')
    app.register_blueprint(posts_bp, url_prefix='/api/posts')
    app.register_blueprint(comments_bp, url_prefix='/api/comments')
    app.register_blueprint(cartoon_jobs_bp, url_prefix='/api/cartoon-jobs')

    # 디버그용 라우트 목록 확인 엔드포인트
    @app.route('/debug/routes')
    def list_routes():
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'rule': str(rule)
            })
        return {'routes': routes}

    # =====================================================================================
    # 7. 전역 에러 핸들러 설정
    # =====================================================================================
    @app.errorhandler(ValidationError)
    def handle_marshmallow_validation(err):
        response = {"error_code": "VALIDATION_ERROR", "details": err.messages}
        return jsonify(response), 400

    @app.errorhandler(Exception)
    def handle_generic_exception(err):
        logging.error(f"처리되지 않은 예외 발생: {err}", exc_info=True)
        response = {"error_code": "INTERNAL_SERVER_ERROR", "message": "서버 내부 오류가 발생했습니다."}
        return jsonify(response), 500

    # =====================================================================================
    # 8. 로깅 및 앱 반환
    # =====================================================================================
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    logging.info("Flask 앱 생성 및 모든 컴포넌트 초기화 완료. (Production Ready)")
    
    return app