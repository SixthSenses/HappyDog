# run.py

from app import create_app
import os

# create_app 함수가 내부에서 'FLASK_ENV'를 직접 읽으므로
# 이 부분은 더 이상 필요하지 않습니다.
# env = os.getenv('FLASK_ENV', 'development') 
app = create_app()

if __name__ == '__main__':
    app.run(
        host=app.config.get('HOST'),
        port=app.config.get('PORT'),
        debug=app.config.get('DEBUG', False)
    )