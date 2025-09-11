from functools import wraps
from flask import request, current_app, jsonify
from marshmallow import ValidationError
from app.utils.error_catalog import build_error

# 적용 대상: 멱등이 요구되는 POST/PATCH 업서트 계열

def idempotent_endpoint(apply_when_methods=('POST', 'PUT', 'PATCH')):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if request.method not in apply_when_methods:
                return fn(*args, **kwargs)
            key = request.headers.get('X-Idempotency-Key')
            if not key:
                return fn(*args, **kwargs)
            service = current_app.services.get('idempotency')
            if not service:
                return fn(*args, **kwargs)
            body_json = None
            if request.is_json:
                try:
                    body_json = request.get_json()
                except Exception:
                    # body 파싱 실패 시 일반 처리로
                    return fn(*args, **kwargs)

            def handler():
                resp = fn(*args, **kwargs)
                # Flask view 반환 형태 다양성 처리
                # 기대: (Response|dict, status) 혹은 Response
                if isinstance(resp, tuple):
                    body, status = resp[0], resp[1]
                else:
                    body, status = resp, 200
                # Flask Response라면 get_json() 지원 시 파싱 시도
                if callable(getattr(body, 'get_json', None)):
                    try:
                        body_data = body.get_json()
                    except Exception:
                        body_data = {}
                elif isinstance(body, dict):
                    body_data = body
                else:
                    body_data = {}
                return body_data, status

            try:
                response_body, status_code, reused = service.execute(
                    key=key,
                    method=request.method,
                    path=request.path,
                    request_body=body_json,
                    handler=handler
                )
            except ValidationError as ve:
                status, body = build_error('VALIDATION_ERROR', details=ve.messages)
                return jsonify(body), status
            except Exception as e:
                from werkzeug.exceptions import Conflict
                if isinstance(e, Conflict):
                    status, body = build_error('IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY', details={"path": request.path})
                    return jsonify(body), status
                status, body = build_error('FETCH_FAILED', message="멱등 처리 중 오류")
                return jsonify(body), status

            resp = jsonify(response_body)
            resp.status_code = status_code
            if reused:
                # Sprint A: 신규 표준 헤더(Idempotent-Replay) + 과도기 legacy 병행
                resp.headers['Idempotent-Replay'] = 'true'
                resp.headers['Idempotency-Replay'] = 'true'  # deprecate later
            resp.headers['Idempotency-Key'] = key
            return resp
        return wrapper
    return decorator
