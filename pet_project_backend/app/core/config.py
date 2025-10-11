# app/core/config.py

import os # 'os' 모듈: 운영체제와 상호작용하는 기능을 제공합니다. 여기서는 환경 변수를 읽기 위해 사용합니다.

class Config:
        """모든 환경 설정의 기반이 되는 공통 설정 클래스입니다.

        NOTE:
            FIREBASE_CREDENTIALS_PATH 환경 변수 명이 코드/문서 간 혼동되어
            DEV_FIREBASE_CREDENTIALS_PATH / TEST_FIREBASE_CREDENTIALS_PATH 만 설정된 경우
            create_app 단계에서 None 으로 남아 Firestore 초기화가 silent skip 되는 문제가 있었음.
            여기서 기본 키(FIREBASE_CREDENTIALS_PATH)를 우선 사용하고, 환경별 fallback 을 적용해 혼동을 제거한다.
        """
        JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
        GOOGLE_CLIENT_SECRETS_PATH = os.getenv('GOOGLE_CLIENT_SECRETS_PATH')
        GOOGLE_OAUTH_REDIRECT_URI = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', 'https://developers.google.com/oauthplayground')

        FIREBASE_STORAGE_BUCKET = os.getenv('FIREBASE_STORAGE_BUCKET')
        # 기본 경로 (가장 명확한 키)
        FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH')

        # OpenAI API 설정
        OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
class DevelopmentConfig(Config):
    """개발 환경 설정.
    FIREBASE_CREDENTIALS_PATH 가 직접 주어지지 않았다면 DEV_FIREBASE_CREDENTIALS_PATH 로 fallback.
    """
    DEBUG = True
    FIREBASE_CREDENTIALS_PATH = Config.FIREBASE_CREDENTIALS_PATH or os.getenv('DEV_FIREBASE_CREDENTIALS_PATH')

class TestingConfig(Config):
    """테스트 환경 설정.
    FIREBASE_CREDENTIALS_PATH 가 직접 주어지지 않았다면 TEST_FIREBASE_CREDENTIALS_PATH 로 fallback.
    """
    TESTING = True
    DEBUG = False
    FIREBASE_CREDENTIALS_PATH = Config.FIREBASE_CREDENTIALS_PATH or os.getenv('TEST_FIREBASE_CREDENTIALS_PATH')

# config_by_name: 문자열 키('development', 'testing')와 해당 환경의 설정 클래스를 매핑하는 딕셔너리입니다.
# 이 딕셔너리는 app/__init__.py의 create_app 함수에서 FLASK_ENV 값에 따라 적절한 설정을 동적으로 선택하는 데 사용됩니다.
config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig
)