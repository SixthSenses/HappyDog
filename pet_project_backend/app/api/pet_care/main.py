# app/api/pet_care/main.py
"""
펫케어 모듈 메인 진입점

RESTful API 자원 중심 설계로 완전히 재구성된 펫케어 모듈입니다.
이 파일은 모든 자원별 라우트를 통합하여 단일 블루프린트로 제공합니다.
"""

from flask import Blueprint

# 자원별 라우트 import
from .routes.daily_logs import daily_logs_bp
from .routes.individual_logs import individual_logs_bp
from .routes.analytics import analytics_bp
from .routes.recommendations import recommendations_bp
from .routes.quick_actions import quick_actions_bp

# 메인 펫케어 블루프린트 생성
pet_care_v2_bp = Blueprint('pet_care_v2', __name__, url_prefix='/api/pets/<pet_id>/care')

def register_pet_care_routes():
    """
    모든 펫케어 자원 라우트를 등록합니다.
    
    URL 구조:
    - /api/pets/{pet_id}/care/daily-logs/...          # 일일 종합 로그
    - /api/pets/{pet_id}/care/food-logs/...           # 개별 로그들
    - /api/pets/{pet_id}/care/analytics/...           # 분석/통계
    - /api/pets/{pet_id}/care/recommendations/...     # 권장량 관리
    - /api/pets/{pet_id}/care/quick-actions/...       # 빠른 액션
    """
    
    # 각 자원별 블루프린트를 메인 블루프린트에 등록
    pet_care_v2_bp.register_blueprint(daily_logs_bp, url_prefix='/daily-logs')
    pet_care_v2_bp.register_blueprint(individual_logs_bp, url_prefix='')  # 루트에 직접 매핑
    pet_care_v2_bp.register_blueprint(analytics_bp, url_prefix='/analytics')
    pet_care_v2_bp.register_blueprint(recommendations_bp, url_prefix='/recommendations')
    pet_care_v2_bp.register_blueprint(quick_actions_bp, url_prefix='/quick-actions')

# 라우트 등록 실행
register_pet_care_routes()

# API 정보 라우트 추가
@pet_care_v2_bp.route('/info', methods=['GET'])
def get_api_info():
    """
    펫케어 API 정보를 제공합니다.
    
    Response:
        200: API 구조 및 사용법 정보
    """
    return {
        "api_version": "2.0",
        "name": "Pet Care API",
        "description": "RESTful 자원 중심 펫케어 관리 API",
        "base_url": "/api/pets/{pet_id}/care",
        "resources": {
            "daily_logs": {
                "description": "일일 종합 펫케어 로그 관리",
                "endpoints": {
                    "GET /daily-logs?date=YYYY-MM-DD": "특정 날짜 로그 조회",
                    "POST /daily-logs": "일일 로그 생성/수정",
                    "GET /daily-logs/summary?month=YYYY-MM": "월별 요약"
                }
            },
            "individual_logs": {
                "description": "개별 로그 타입별 CRUD 관리",
                "log_types": [
                    "food-logs", "water-logs", "poop-logs", "activity-logs",
                    "weight-logs", "vomit-logs", "medication-logs", "symptoms-logs"
                ],
                "endpoints": {
                    "GET /{log_type}?date=YYYY-MM-DD": "로그 목록 조회",
                    "POST /{log_type}": "새 로그 추가",
                    "GET /{log_type}/{log_id}?date=YYYY-MM-DD": "특정 로그 조회",
                    "PUT /{log_type}/{log_id}?date=YYYY-MM-DD": "로그 수정",
                    "DELETE /{log_type}/{log_id}?date=YYYY-MM-DD": "로그 삭제"
                }
            },
            "analytics": {
                "description": "데이터 분석 및 통계",
                "endpoints": {
                    "GET /analytics/trends?metric=X&period=Y": "트렌드 분석",
                    "GET /analytics/graphs?type=X&range=Y": "그래프 데이터",
                    "GET /analytics/reports?period=X": "종합 리포트"
                }
            },
            "recommendations": {
                "description": "권장량 계산 및 관리",
                "endpoints": {
                    "GET /recommendations": "현재 권장량 조회",
                    "POST /recommendations/refresh": "권장량 수동 갱신",
                    "GET /recommendations/history": "권장량 변경 이력",
                    "GET /recommendations/settings": "펫케어 설정 조회",
                    "PUT /recommendations/settings": "펫케어 설정 수정"
                }
            },
            "quick_actions": {
                "description": "빠른 액션 및 편의 기능",
                "endpoints": {
                    "POST /quick-actions/add-calories": "빠른 칼로리 추가",
                    "POST /quick-actions/add-water": "빠른 물 추가",
                    "POST /quick-actions/add-activity": "빠른 활동 추가",
                    "POST /quick-actions/subtract-calories": "빠른 칼로리 감소",
                    "GET /quick-actions/presets": "빠른 액션 프리셋 조회"
                }
            }
        },
        "features": {
            "automatic_care_settings_update": "반려동물 정보 변경 시 자동 권장량 갱신",
            "consistent_restful_design": "모든 자원에 일관된 REST 패턴 적용",
            "comprehensive_analytics": "트렌드 분석 및 인사이트 제공",
            "quick_actions": "사용자 편의를 위한 빠른 기록 추가",
            "unified_datetime_handling": "통합 시간 관리 시스템 적용"
        },
        "status": {
            "version": "v2.0 (Production Ready)",
            "stability": "Stable",
            "support": "Full Support"
        }
    }

__all__ = ['pet_care_v2_bp']
