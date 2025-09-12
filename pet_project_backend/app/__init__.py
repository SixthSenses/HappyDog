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
import importlib
import logging
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify
from marshmallow import ValidationError
from flask_jwt_extended import JWTManager
import firebase_admin
from firebase_admin import credentials
from app.core.firestore import initialize_firestore, get_db

# - 설정
from app.core.config import config_by_name

# - API 블루프린트
from app.api.auth.routes import auth_bp
from app.api.auth.services import AuthService
from app.api.uploads.routes import uploads_bp
from app.api.users.routes import users_bp
from app.api.posts.routes import posts_bp
from app.api.comments.routes import comments_bp
from app.api.cartoon_jobs.routes import cartoon_jobs_bp
from app.api.breeds.routes import breeds_bp
from app.api.pets.routes import pets_bp
from app.api.pet_care.settings.routes import pet_care_settings_bp
from app.api.pet_care.records.routes import pet_care_records_bp
from app.api.notifications.routes import notifications_bp

# - 서비스 모듈
from app.services import storage_service as storage_service_module
from app.services import notification_service as notification_service_module
from app.services import openai_service as openai_service_module
from app.services.openai_service_stub import OpenAIServiceStub
from app.api.auth import services as auth_service_module
from app.api.users.services import UserProfileService, UserStatsService, UserService
from app.api.posts.services import PostService, PostLikeService, PostEventService, PostStorageService
from app.api.comments.services import CommentService, CommentMentionService, CommentEventService, CommentNotificationService
from app.api.cartoon_jobs.services import CartoonJobService, CartoonJobProcessor, CartoonJobEventService, CartoonJobIntegrationService
from app.api.breeds.services import BreedService
from app.api.pets.services.pet_profile_service import PetProfileService
from app.api.pets.services.pet_biometric_service import PetBiometricService
from app.api.pet_care.settings.services import PetCareSettingService
from app.api.pet_care.records.record_integration_service import PetCareRecordIntegration
from app.api.pet_care.records.services import PetCareRecordService
from app.services.idempotency_service import IdempotencyService
from app.middleware.request_id_middleware import install_request_id
from app.middleware.rate_limit_middleware import install_rate_limit
from app.utils import metrics as metrics_module
from app.utils.path_utils import resolve_ml_paths, as_bool

# - ML 모델 파이프라인 (지연 임포트: 환경에 없으면 건너뜀)
NosePrintPipeline = None
EyeAnalyzer = None

def _init_core_services(app, skip_ml: bool = False, docs_mode: bool = False):
    """
    Initialize core services with no dependencies or minimal dependencies.
    These services are foundational and used by other services.
    """
    # Storage service - foundational for file operations
    try:
        storage_instance = storage_service_module.StorageService()
        storage_instance.init_app(app)
        app.services['storage'] = storage_instance
        logging.info("Storage service initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize storage service: {e}")
        raise
    
    # OpenAI service - external API integration
    if docs_mode:
        app.services['openai'] = OpenAIServiceStub()
        app.services['openai'].init_app(app)
    else:
        try:
            openai_instance = openai_service_module.OpenAIService()
            openai_instance.init_app(app)
            app.services['openai'] = openai_instance
            logging.info("OpenAI service initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize OpenAI service: {e}")
            raise

    # Notification service - foundational for async messaging (DI with Firestore)
    app.services['notifications'] = notification_service_module.NotificationService(app.firestore_client)
    
    # Notification presentation service
    from app.api.notifications.services import NotificationPresentationService
    app.services['notification_presentation'] = NotificationPresentationService()
    
    # Utility services with no dependencies
    app.services['idempotency'] = IdempotencyService(app.firestore_client)
    app.services['breeds'] = BreedService(app.firestore_client)
    
    # Auth service - foundational for security (DI with Firestore)
    app.services['auth'] = AuthService(app.firestore_client)
    app.services['auth'].init_app(app)
    logging.info("Auth service initialized successfully in DI container")
    
    # ML Pipeline services - optional external components
    if not skip_ml:
        _init_ml_services(app)
    else:
        app.services['nose_pipeline'] = None
        app.services['eye_analyzer'] = None
        logging.info("DOCS_MODE: ML pipelines skipped")

def _init_ml_services(app):
    """Initialize ML services with robust cross-machine path resolution and optional skipping.

    Environment flags:
      SKIP_ML=1 -> skip heavy model init
      STRICT_ML_PATHS=1 -> raise if any required path missing; otherwise warn & skip that pipeline
    """
    if as_bool(os.getenv('SKIP_ML')):
        logging.info("SKIP_ML enabled: ML pipelines not initialized")
        app.services['nose_pipeline'] = None
        app.services['eye_analyzer'] = None
        return

    paths = resolve_ml_paths({})
    strict = as_bool(os.getenv('STRICT_ML_PATHS'))
    # Nose print pipeline initialization (optional)
    try:
        required_keys = ['YOLO_WEIGHTS_PATH','ML_CONFIG_PATH','EXTRACTOR_WEIGHTS_PATH','FAISS_INDEX_PATH']
        missing = [k for k in required_keys if not paths.get(k) or not os.path.exists(paths[k])]
        if missing:
            msg = f"Nose pipeline assets missing or unresolved: {missing}"
            if strict:
                raise FileNotFoundError(msg)
            logging.warning(msg + " (pipeline skipped)")
            app.services['nose_pipeline'] = None
        else:
            # Dynamic import only if assets present
            if NosePrintPipeline is None:
                _nose_module = importlib.import_module('nose_lib.pipelines.nose_print_pipeline')
                _NosePrintPipeline = getattr(_nose_module, 'NosePrintPipeline')
            else:
                _NosePrintPipeline = NosePrintPipeline
            app.services['nose_pipeline'] = _NosePrintPipeline(
                yolo_weights_path=paths['YOLO_WEIGHTS_PATH'],
                config_path=paths['ML_CONFIG_PATH'],
                extractor_weights_path=paths['EXTRACTOR_WEIGHTS_PATH'],
                faiss_index_path=paths['FAISS_INDEX_PATH']
            )
            logging.info("Nose print pipeline initialized successfully")
    except Exception as e:
        logging.warning(f"Failed to initialize nose pipeline: {e}")
        app.services['nose_pipeline'] = None
    
    # Eye analyzer initialization (optional)
    try:
        if EyeAnalyzer is None:
            _eye_module = importlib.import_module('eyes_models.eyes_lib.inference')
            _EyeAnalyzer = getattr(_eye_module, 'EyeAnalyzer')
        else:
            _EyeAnalyzer = EyeAnalyzer
        app.services['eye_analyzer'] = _EyeAnalyzer()
        logging.info("Eye analyzer initialized successfully")
    except Exception as e:
        logging.warning(f"Failed to initialize eye analyzer: {e}")
        app.services['eye_analyzer'] = None

def _init_dependent_services(app):
    """
    Initialize services that depend on core services.
    Must be called after _init_core_services().
    """
    # Pet Care Domain - depends on breeds and notifications
    app.services['pet_care_settings'] = PetCareSettingService(breed_service=app.services['breeds'], db_client=app.firestore_client)
    app.services['pet_care_records'] = PetCareRecordService(db_client=app.firestore_client)
    
    # Pet Care Integration Service - depends on multiple services
    app.services['pet_care_integration'] = PetCareRecordIntegration(
        crud_service=app.services['pet_care_records'],
        query_service=app.services['pet_care_records'],  # Same service for now
        cache_service=None,  # Cache service not implemented yet
        settings_service=app.services['pet_care_settings'],
        notification_service=app.services['notifications']
    )

    # Pets Domain - depends on storage, pet_care_settings, and ML services
    pet_profile_service = PetProfileService(
        pet_care_setting_service=app.services['pet_care_settings'],
        storage_service=app.services['storage'],
        db_client=app.firestore_client
    )
    
    pet_biometric_service = PetBiometricService(
        storage_service=app.services['storage'],
        nose_pipeline=app.services['nose_pipeline'],
        eye_analyzer=app.services['eye_analyzer'],
        db_client=app.firestore_client
    )
    
    # Use profile service as main pets service
    app.services['pets'] = pet_profile_service
    # Expose biometric service separately (profile service intentionally does not include ML concerns)
    app.services['pet_biometrics'] = pet_biometric_service
    logging.info("Pet service initialized successfully")
    
    # User Services - depends on storage
    app.services['user_profile'] = UserProfileService(app.services['storage'], db_client=app.firestore_client)
    app.services['user_stats'] = UserStatsService(app.firestore_client)
    app.services['users'] = UserService()  # Lightweight, no dependencies
    
    # Posts Domain - depends on storage (DI with Firestore)
    app.services['posts'] = PostService(app.firestore_client)
    app.services['post_likes'] = PostLikeService(app.firestore_client)
    app.services['post_events'] = PostEventService()
    app.services['post_storage'] = PostStorageService(app.services['storage'])
    
    # Initialize post services with app context
    app.services['post_events'].init_app(app)
    app.services['post_storage'].init_app(app)
    
    # Comments Domain - basic services first (DI with Firestore)
    app.services['comments'] = CommentService(app.firestore_client)
    app.services['comment_mentions'] = CommentMentionService(app.firestore_client)
    app.services['comment_events'] = CommentEventService()
    app.services['comment_notifications'] = CommentNotificationService()
    
    # Initialize comment event service with app context
    app.services['comment_events'].init_app(app)
    
    # Cartoon Jobs Domain - depends on posts and notifications
    app.services['cartoon_jobs'] = CartoonJobService(app.firestore_client)
    # docs_mode flag available in create_app scope; pass executor only when not docs_mode
    from flask import current_app as _ca  # safe local import if context exists
    exec_instance = None
    try:
        if not getattr(app, 'docs_mode_flag', False):
            exec_instance = ThreadPoolExecutor(max_workers=3)
    except Exception:
        exec_instance = ThreadPoolExecutor(max_workers=3)
    app.services['job_processor'] = CartoonJobProcessor(executor=exec_instance)
    app.services['job_events'] = CartoonJobEventService()
    app.services['job_integration'] = CartoonJobIntegrationService(
        post_service=app.services['posts'],
        notification_service=app.services['notifications']
    )
    
    # Initialize cartoon job services with app context
    app.services['cartoon_jobs'].init_app(app)
    app.services['job_processor'].init_app(app)
    app.services['job_events'].init_app(app)
    app.services['job_integration'].init_app(app)

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
    # Google OAuth Redirect URI 확인 로그 (Playground 테스트 편의)
    try:
        logging.info(f"Google OAuth Redirect URI: {app.config.get('GOOGLE_OAUTH_REDIRECT_URI')}")
    except Exception:
        pass

    # =====================================================================================
    # 4. 확장 기능 및 외부 서비스 초기화
    # =====================================================================================
    JWTManager(app)

    docs_mode = os.getenv('DOCS_MODE', '').lower() in ('1', 'true', 'yes')
    # store flag for later conditional service initialization (e.g., background executors)
    app.docs_mode_flag = docs_mode
    if docs_mode:
        logging.info("DOCS_MODE enabled: skipping heavy external initializations (Firebase, ML, network APIs)")

    if not docs_mode and not firebase_admin._apps:
        cred_path = app.config.get('FIREBASE_CREDENTIALS_PATH')
        bucket = app.config.get('FIREBASE_STORAGE_BUCKET')
        original = cred_path
        resolved = None
        if cred_path and not os.path.isabs(cred_path) and not os.path.exists(cred_path):
            backend_root = os.path.dirname(os.path.dirname(__file__))
            candidate = os.path.join(backend_root, cred_path)
            if os.path.exists(candidate):
                cred_path = candidate
        if cred_path and os.path.exists(cred_path):
            resolved = cred_path
        logging.info(f"Firebase init attempt: original_path='{original}' resolved_path='{resolved}' bucket='{bucket}'")
        if not resolved:
            logging.warning("Firebase credentials file not found; skipping firebase_admin.initialize_app (Firestore fallback may still work via ADC if configured).")
        else:
            try:
                cred = credentials.Certificate(resolved)
                firebase_admin.initialize_app(cred, {'storageBucket': bucket})
                logging.info("Firebase initialized successfully (firebase_admin.initialize_app)")
            except Exception as fe:
                logging.error(f"Firebase initialization failed type={type(fe).__name__}: {fe}", exc_info=True)

    # Central Firestore client initialization (Dependency Inversion: single source)
    app.firestore_client = initialize_firestore()
    if app.firestore_client is None:
        if docs_mode:
            logging.info("DOCS_MODE: Firestore client not initialized (None)")
        else:
            logging.warning("Firestore client not initialized (returned None)")
        app.config['FIRESTORE_AVAILABLE'] = False
    else:
        logging.info("Firestore client initialized (centralized)")
        app.config['FIRESTORE_AVAILABLE'] = True

    # =====================================================================================
    # 5. 서비스 인스턴스 생성 및 'app.services'에 저장 (의존성 주입)
    # =====================================================================================
    app.services = {}
    
    # Initialize services in dependency order to prevent circular dependencies
    _init_core_services(app, skip_ml=docs_mode, docs_mode=docs_mode)
    _init_dependent_services(app)
    
    # - 인증 서비스는 이미 DI 컨테이너에서 초기화됨 (auth service already initialized above)
    # auth_service_module.auth_service.init_app(app)  # ❌ Removed singleton pattern

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
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')

    # Health & metrics (lightweight JSON; Prometheus 미도입 상태)
    @app.route('/health', methods=['GET'])
    def health_check():
        """시스템 헬스 체크

        ResponseSchema[200]: HealthStatusResponseSchema
        """
        return {
            "status": "ok", 
            "counters": metrics_module.get_counters(),
            "firestore": "up" if app.config.get('FIRESTORE_AVAILABLE') else "down"
        }, 200

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
        try:
            from app.utils.error_catalog import build_error
            status, body = build_error('INTERNAL_ERROR')
            return jsonify(body), status
        except Exception:  # fallback in case catalog import fails early in startup
            fallback = {"error_code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다."}
            return jsonify(fallback), 500

    # =====================================================================================
    # 8. 로깅 및 앱 반환
    # 미들웨어 설치 (request_id, rate_limit)
    install_request_id(app)
    # Rate limit 미들웨어 설치(기본 구성 사용; 필요 시 RateLimitConfig으로 조정 가능)
    install_rate_limit(app)
    # =====================================================================================
    if not app.debug:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    
    logging.info(f"Flask app created for '{config_name}' environment.")
    
    return app