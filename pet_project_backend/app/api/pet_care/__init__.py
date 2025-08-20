# app/api/pet_care/__init__.py
"""
펫케어 관련 API 블루프린트

RESTful 자원 중심 설계의 v2 API만 제공합니다.
"""

# v2 API - RESTful 자원 중심 설계  
from .main import pet_care_v2_bp

__all__ = ['pet_care_v2_bp']