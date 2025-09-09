import time
import threading
from flask import request, jsonify, g

# 간단한 인메모리 레이트 리미터 (프로덕션: Redis/Cloud Memorystore 등 사용 권장)
# SPEC_TODO(레이트 리미터 외부 저장소 연동 + 사용자별 정책)

class _TokenBucket:
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate_per_sec
        self.timestamp = time.time()
        self.lock = threading.Lock()

    def consume(self, amount=1) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.timestamp
            refill = elapsed * self.refill_rate
            if refill > 0:
                self.tokens = min(self.capacity, self.tokens + refill)
                self.timestamp = now
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False

_buckets = {}
_global_lock = threading.Lock()

def install_rate_limit(app, capacity=100, window_seconds=60):
    rate = capacity / window_seconds

    @app.before_request
    def _rate_limit_before():
        ip = request.remote_addr or 'unknown'
        with _global_lock:
            bucket = _buckets.get(ip)
            if not bucket:
                bucket = _TokenBucket(capacity, rate)
                _buckets[ip] = bucket
        allowed = bucket.consume()
        remaining = int(bucket.tokens) if bucket.tokens > 0 else 0
        refill_needed = (bucket.capacity - bucket.tokens)
        reset_in = int(refill_needed / bucket.refill_rate) if bucket.refill_rate > 0 else window_seconds
        g._rate_limit_ctx = {
            'limit': capacity,
            'remaining': remaining,
            'reset': int(time.time()) + max(reset_in, 0)
        }
        if not allowed:
            try:
                from app.utils.error_catalog import build_error
                status, body = build_error('RATE_LIMIT_EXCEEDED')
            except Exception:
                status, body = 429, {"error_code": "RATE_LIMIT_EXCEEDED", "message": "요청이 너무 많습니다."}
            resp = jsonify(body)
            rl = g._rate_limit_ctx
            resp.headers['X-RateLimit-Limit'] = str(rl['limit'])
            resp.headers['X-RateLimit-Remaining'] = '0'
            resp.headers['X-RateLimit-Reset'] = str(rl['reset'])
            resp.headers['Retry-After'] = '1'
            return resp, status

    @app.after_request
    def _rate_limit_after(resp):
        ctx = getattr(g, '_rate_limit_ctx', None)
        if ctx:
            resp.headers['X-RateLimit-Limit'] = str(ctx['limit'])
            resp.headers['X-RateLimit-Remaining'] = str(ctx['remaining'])
            resp.headers['X-RateLimit-Reset'] = str(ctx['reset'])
        return resp
