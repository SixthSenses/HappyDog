# run.py
from dotenv import load_dotenv
import os
from app import create_app
load_dotenv()
app = create_app()

if __name__ == '__main__':
    host = os.getenv('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_RUN_PORT', 5000))
    debug = app.config.get('DEBUG', True)
    app.run(host=host, port=port, debug=debug)