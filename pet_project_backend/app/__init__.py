from flask import Flask
from app.core.config import config_by_name
import firebase_admin
from firebase_admin import credentials

def create_app(config_name: str = 'development'):
    """
    환경에 맞는 설정을 적용하여 Flask 앱을 생성하는 팩토리 함수입니다.
    """
    app = Flask(__name__)
    
    app.config.from_object(config_by_name[config_name])
    app.json.ensure_ascii = False

    if not firebase_admin._apps:
        cred_path = app.config['FIREBASE_CREDENTIALS_PATH']
        if not cred_path:
            raise ValueError("Firebase credentials path is not set in the config.")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    
    from app.api.pets.routes import pets_bp
    from app.api.auth.routes import auth_bp
    
    app.register_blueprint(pets_bp, url_prefix='/api/pets')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    return app