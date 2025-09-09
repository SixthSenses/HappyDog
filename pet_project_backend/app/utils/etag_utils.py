# app/utils/etag_utils.py
"""ETag 생성 및 검증 유틸리티 (Sprint C)
=========================================
HTTP 캐싱 지원을 위한 ETag 처리 모듈
"""
import hashlib
import json
import logging
from typing import Any, Dict, Optional
from flask import Request

logger = logging.getLogger(__name__)

# 인메모리 ETag 캐시 (프로덕션: Redis 권장)
_etag_cache: Dict[str, str] = {}


def generate_etag(data: Any, canonical: bool = True) -> str:
    """
    데이터로부터 ETag 값을 생성합니다.
    
    Args:
        data: ETag를 생성할 데이터 (dict, string, 등)
        canonical: JSON 정규화 여부 (dict의 경우)
    
    Returns:
        ETag 값 (따옴표 제외)
    """
    try:
        if isinstance(data, dict):
            if canonical:
                # Canonical JSON: 키 정렬, 공백 제거
                content = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            else:
                content = json.dumps(data, ensure_ascii=False)
        elif isinstance(data, str):
            content = data
        else:
            content = str(data)
        
        # SHA256 해시 생성
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        etag = hash_obj.hexdigest()[:16]  # 16자리만 사용 (충분한 엔트로피)
        
        return etag
        
    except Exception as e:
        logger.error(f"ETag 생성 실패: {e}")
        # 실패 시 기본값 반환
        return "default"


def check_if_none_match(request: Request, etag: str) -> bool:
    """
    요청의 If-None-Match 헤더와 ETag를 비교합니다.
    
    Args:
        request: Flask request 객체
        etag: 비교할 ETag 값
    
    Returns:
        True if 304 Not Modified 응답이 필요한 경우
    """
    try:
        if_none_match = request.headers.get('If-None-Match')
        if not if_none_match:
            return False
        
        # 따옴표 제거
        if_none_match = if_none_match.strip('"')
        etag = etag.strip('"')
        
        # 와일드카드(*) 또는 매칭
        if if_none_match == '*' or if_none_match == etag:
            return True
        
        # 복수 ETag 지원 (쉼표로 구분)
        if ',' in if_none_match:
            etags = [e.strip().strip('"') for e in if_none_match.split(',')]
            return etag in etags
        
        return False
        
    except Exception as e:
        logger.error(f"If-None-Match 체크 실패: {e}")
        return False


def invalidate_etag_cache(patterns: list) -> None:
    """
    특정 패턴과 매칭되는 ETag 캐시를 무효화합니다.
    
    Args:
        patterns: 무효화할 캐시 키 패턴 리스트
    """
    global _etag_cache
    
    try:
        keys_to_delete = []
        for pattern in patterns:
            for key in _etag_cache.keys():
                if pattern in key:
                    keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del _etag_cache[key]
            logger.debug(f"ETag 캐시 무효화: {key}")
        
    except Exception as e:
        logger.error(f"ETag 캐시 무효화 실패: {e}")


def cache_etag(key: str, etag: str, ttl: int = 300) -> None:
    """
    ETag를 캐시에 저장합니다.
    
    Args:
        key: 캐시 키
        etag: ETag 값
        ttl: TTL(초) - 현재는 무시됨 (Redis 구현 시 사용)
    """
    global _etag_cache
    _etag_cache[key] = etag


def get_cached_etag(key: str) -> Optional[str]:
    """
    캐시된 ETag를 조회합니다.
    
    Args:
        key: 캐시 키
    
    Returns:
        캐시된 ETag 값 또는 None
    """
    return _etag_cache.get(key)


def clear_etag_cache() -> None:
    """전체 ETag 캐시를 클리어합니다."""
    global _etag_cache
    _etag_cache.clear()
    logger.info("ETag 캐시 전체 클리어")