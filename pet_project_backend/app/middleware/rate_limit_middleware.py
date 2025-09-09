# app/middleware/rate_limit_middleware.py
"""Enhanced Rate Limiting Middleware (Sprint C)
==============================================
Phase 1: Per-user rate limiting with observability
Phase 2: Write limits enforcement
Phase 3: Read limits enforcement
"""
import time
import threading
import logging
from flask import request, jsonify, g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.utils import metrics

logger = logging.getLogger(__name__)

# Token bucket implementation for rate limiting
class _TokenBucket:
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate_per_sec
        self.timestamp = time.time()
        self.lock = threading.Lock()

    def consume(self, amount=1) -> tuple[bool, int, int]:
        """
        Attempt to consume tokens from the bucket.
        
        Returns:
            tuple: (allowed, remaining_tokens, reset_in_seconds)
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.timestamp
            refill = elapsed * self.refill_rate
            if refill > 0:
                self.tokens = min(self.capacity, self.tokens + refill)
                self.timestamp = now
            
            remaining = int(self.tokens) if self.tokens > 0 else 0
            refill_needed = self.capacity - self.tokens
            reset_in = int(refill_needed / self.refill_rate) if self.refill_rate > 0 else 60
            
            if self.tokens >= amount:
                self.tokens -= amount
                return True, remaining - 1, reset_in
            return False, 0, reset_in


# Rate limit configuration
class RateLimitConfig:
    def __init__(self):
        # Default limits
        self.per_ip_read = 300  # per minute
        self.per_ip_write = 100  # per minute
        self.per_user_read = 600  # per minute
        self.per_user_write = 200  # per minute
        
        # Phase control
        self.phase = 1  # 1: observe, 2: enforce write, 3: enforce all
        
    def get_limits(self, is_authenticated: bool, is_write: bool) -> tuple[int, int]:
        """Get capacity and window for given context."""
        if is_authenticated:
            capacity = self.per_user_write if is_write else self.per_user_read
        else:
            capacity = self.per_ip_write if is_write else self.per_ip_read
        window = 60  # 1 minute window
        return capacity, window
    
    def should_enforce(self, is_write: bool) -> bool:
        """Check if rate limit should be enforced based on phase."""
        if self.phase == 1:
            return False  # Observe only
        elif self.phase == 2:
            return is_write  # Enforce write only
        else:  # phase 3
            return True  # Enforce all


# Global state
_buckets = {}
_global_lock = threading.Lock()
_config = RateLimitConfig()


def get_rate_limit_key(request) -> tuple[str, bool]:
    """
    Get rate limit key and authentication status.
    
    Returns:
        tuple: (key, is_authenticated)
    """
    try:
        # Try to get JWT identity
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            return f"user:{user_id}", True
    except Exception:
        pass
    
    # Fall back to IP
    ip = request.remote_addr or 'unknown'
    return f"ip:{ip}", False


def is_write_operation(request) -> bool:
    """Check if request is a write operation."""
    return request.method in ('POST', 'PUT', 'PATCH', 'DELETE')


def calculate_dynamic_retry_after(bucket: _TokenBucket, is_write: bool) -> int:
    """
    Calculate dynamic Retry-After value.
    
    Args:
        bucket: Token bucket instance
        is_write: Whether this is a write operation
    
    Returns:
        Retry-After value in seconds
    """
    # Base retry time
    base_retry = 1
    
    # Add penalty for write operations
    if is_write:
        base_retry += 2
    
    # Add progressive penalty based on token deficit
    deficit_ratio = max(0, -bucket.tokens) / bucket.capacity if bucket.capacity > 0 else 0
    penalty = int(deficit_ratio * 10)
    
    return min(base_retry + penalty, 60)  # Cap at 60 seconds


def install_rate_limit(app, config: RateLimitConfig = None):
    """
    Install rate limiting middleware.
    
    Args:
        app: Flask application instance
        config: Rate limit configuration (optional)
    """
    global _config
    if config:
        _config = config
    
    @app.before_request
    def _rate_limit_before():
        # Get rate limit key and context
        key, is_authenticated = get_rate_limit_key(request)
        is_write = is_write_operation(request)
        
        # Get limits based on context
        capacity, window = _config.get_limits(is_authenticated, is_write)
        rate = capacity / window
        
        # Get or create bucket
        with _global_lock:
            bucket = _buckets.get(key)
            if not bucket:
                bucket = _TokenBucket(capacity, rate)
                _buckets[key] = bucket
        
        # Consume token
        allowed, remaining, reset_in = bucket.consume()
        
        # Store context for after_request
        g._rate_limit_ctx = {
            'key': key,
            'limit': capacity,
            'remaining': remaining,
            'reset': int(time.time()) + max(reset_in, 0),
            'is_authenticated': is_authenticated,
            'is_write': is_write,
            'allowed': allowed,
            'bucket': bucket
        }
        
        # Log metrics (Phase 1: always log)
        if not allowed:
            logger.warning(f"Rate limit exceeded: key={key}, type={'write' if is_write else 'read'}")
            metrics.increment('rate_limit_exceeded', op='write' if is_write else 'read', phase=_config.phase, auth='user' if is_authenticated else 'ip')
        
        # Enforce if needed
        if not allowed and _config.should_enforce(is_write):
            try:
                from app.utils.error_catalog import build_error
                status, body = build_error('RATE_LIMIT_EXCEEDED')
            except Exception:
                status, body = 429, {
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "category": "RATE_LIMIT",
                    "retriable": True,
                    "message": "요청이 너무 많습니다."
                }
            
            # Add rate limit details to response
            body['details'] = {
                'limit': capacity,
                'window': f"{window}s",
                'retry_after': calculate_dynamic_retry_after(bucket, is_write)
            }
            
            resp = jsonify(body)
            resp.status_code = status
            
            # Set headers
            rl = g._rate_limit_ctx
            resp.headers['X-RateLimit-Limit'] = str(rl['limit'])
            resp.headers['X-RateLimit-Remaining'] = '0'
            resp.headers['X-RateLimit-Reset'] = str(rl['reset'])
            resp.headers['Retry-After'] = str(calculate_dynamic_retry_after(bucket, is_write))
            
            # User-specific headers (Sprint C)
            if is_authenticated:
                resp.headers['X-RateLimit-Scope'] = 'user'
                resp.headers['X-RateLimit-Type'] = 'write' if is_write else 'read'
            
            return resp

    @app.after_request
    def _rate_limit_after(resp):
        ctx = getattr(g, '_rate_limit_ctx', None)
        if ctx:
            # Always add rate limit headers
            resp.headers['X-RateLimit-Limit'] = str(ctx['limit'])
            resp.headers['X-RateLimit-Remaining'] = str(ctx['remaining'])
            resp.headers['X-RateLimit-Reset'] = str(ctx['reset'])
            
            # Add scope header for authenticated users
            if ctx['is_authenticated']:
                resp.headers['X-RateLimit-Scope'] = 'user'
            else:
                resp.headers['X-RateLimit-Scope'] = 'ip'
            
            # Add operation type header
            resp.headers['X-RateLimit-Type'] = 'write' if ctx['is_write'] else 'read'
            
            # Phase indicator (for debugging)
            resp.headers['X-RateLimit-Phase'] = str(_config.phase)
        
        # Expose phase metric (hit count)
        if ctx:
            metrics.increment('rate_limit_request', op='write' if ctx['is_write'] else 'read', phase=_config.phase, auth='user' if ctx['is_authenticated'] else 'ip')
        return resp


# Utility function to clear buckets (for testing)
def clear_rate_limit_buckets():
    """Clear all rate limit buckets."""
    global _buckets
    with _global_lock:
        _buckets.clear()
    logger.info("Rate limit buckets cleared")


# Utility function to set phase
def set_rate_limit_phase(phase: int):
    """
    Set rate limit enforcement phase.
    
    Args:
        phase: 1 (observe), 2 (enforce write), or 3 (enforce all)
    """
    global _config
    if phase not in (1, 2, 3):
        raise ValueError("Phase must be 1, 2, or 3")
    _config.phase = phase
    logger.info(f"Rate limit phase set to {phase}")