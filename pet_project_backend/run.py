# run.py
from dotenv import load_dotenv
import os
from app import create_app
basedir = os.path.abspath(os.path.dirname(__file__))
# 2. 해당 디렉터리 안에 있는 '.env' 파일의 정확한 경로를 지정합니다.
dotenv_path = os.path.join(basedir, '.env')
# 3. 지정된 경로의 .env 파일을 로드합니다.
load_dotenv(dotenv_path=dotenv_path)

print(f"--- .env 파일 로드 테스트 ---")
print(f"FLASK_ENV 변수 값: {os.getenv('FLASK_ENV')}")
print(f"TEST_FIREBASE_CREDENTIALS_PATH 변수 값: {os.getenv('TEST_FIREBASE_CREDENTIALS_PATH')}")
print(f"--------------------------")



app = create_app()

if __name__ == '__main__':
    host = os.getenv('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_RUN_PORT', 5000))
    debug = app.config.get('DEBUG', False)
    app.run(host=host, port=port, debug=debug)