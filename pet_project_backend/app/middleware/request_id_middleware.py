import uuid
from flask import g, request

def install_request_id(app):
    @app.before_request
    def _assign_request_id():
        rid = request.headers.get('X-Request-Id') or str(uuid.uuid4())
        g.request_id = rid

    @app.after_request
    def _inject_response_header(resp):
        if hasattr(g, 'request_id'):
            resp.headers['X-Request-Id'] = g.request_id
        return resp
