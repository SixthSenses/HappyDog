# app/core/config.py

import os # 'os' 모듈: 운영체제와 상호작용하는 기능을 제공합니다. 여기서는 환경 변수를 읽기 위해 사용합니다.

class Config:
    """모든 환경 설정의 기반이 되는 공통 설정 클래스입니다."""
    # os.getenv('KEY'): 환경 변수 'KEY'의 값을 문자열로 가져옵니다. .env 파일에 정의된 값을 읽어옵니다.
    # 이 키는 JWT 토큰을 암호화하고 서명하는 데 사용되어 토큰의 위변조를 방지합니다.
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    # Google OAuth 인증에 필요한 클라이언트 시크릿 파일의 경로를 환경 변수에서 가져옵니다.
    GOOGLE_CLIENT_SECRETS_PATH = os.getenv('GOOGLE_CLIENT_SECRETS_PATH')

    FIREBASE_STORAGE_BUCKET = os.getenv('FIREBASE_STORAGE_BUCKET')
class DevelopmentConfig(Config):
    """개발 환경을 위한 설정 클래스입니다. Config 클래스를 상속받아 공통 설정을 그대로 사용합니다."""
    # DEBUG = True: Flask의 디버그 모드를 활성화합니다. 코드가 변경될 때마다 서버가 자동으로 재시작되고, 에러 발생 시 웹 브라우저에 상세한 디버그 정보가 표시됩니다.
    DEBUG = True
    # 개발용 Firebase 데이터베이스에 연결하기 위한 서비스 계정 키 파일 경로를 환경 변수에서 가져옵니다.
    FIREBASE_CREDENTIALS_PATH = os.getenv('DEV_FIREBASE_CREDENTIALS_PATH')

class TestingConfig(Config):
    """테스트 환경을 위한 설정 클래스입니다."""
    # TESTING = True: Flask를 테스트 모드로 설정합니다. 예외 처리가 달라지는 등 테스트에 용이한 상태가 됩니다.
    TESTING = True
    DEBUG = False # 테스트 환경에서는 보통 디버그 모드를 끕니다.
    # 테스트용 Firebase 데이터베이스에 연결하기 위한 서비스 계정 키 파일 경로를 환경 변수에서 가져옵니다.
    FIREBASE_CREDENTIALS_PATH = os.getenv('TEST_FIREBASE_CREDENTIALS_PATH')

# config_by_name: 문자열 키('development', 'testing')와 해당 환경의 설정 클래스를 매핑하는 딕셔너리입니다.
# 이 딕셔너리는 app/__init__.py의 create_app 함수에서 FLASK_ENV 값에 따라 적절한 설정을 동적으로 선택하는 데 사용됩니다.
config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig
)