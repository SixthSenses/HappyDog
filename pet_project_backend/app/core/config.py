# app/core/config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # [추가] Flask 실행 관련 설정
    HOST = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_RUN_PORT', 5000))

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'EkEl')
    GOOGLE_CLIENT_SECRETS_PATH = os.getenv('GOOGLE_CLIENT_SECRETS_PATH')

class DevelopmentConfig(Config):
    DEBUG = True
    FIREBASE_CREDENTIALS_PATH = os.getenv('DEV_FIREBASE_CREDENTIALS_PATH')

class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    FIREBASE_CREDENTIALS_PATH = os.getenv('TEST_FIREBASE_CREDENTIALS_PATH')

config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig
)