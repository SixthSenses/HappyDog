# app/api/breeds/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from urllib.parse import unquote

from .schemas import (
    BreedSchema, BreedListSchema, BreedSummaryListSchema, 
    BreedSearchSchema, ErrorResponseSchema
)
from .services import BreedService

logger = logging.getLogger(__name__)

breeds_bp = Blueprint('breeds_bp', __name__)

# 서비스 인스턴스 생성
breed_service = BreedService()

@breeds_bp.route('/', methods=['GET'])
def get_all_breeds():
    """
    모든 품종 목록을 조회합니다.
    
    Query Parameters:
        - limit (int, optional): 조회할 최대 개수
        - offset (int, optional): 건너뛸 개수 (기본값: 0)
        - summary (bool, optional): 요약 정보만 조회할지 여부 (기본값: false)
    """
    try:
        # 쿼리 파라미터 파싱
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', default=0, type=int)
        summary_only = request.args.get('summary', default='false').lower() == 'true'
        
        # 파라미터 유효성 검사
        if offset < 0:
            return jsonify({
                "error_code": "INVALID_PARAMETER",
                "message": "offset은 0 이상이어야 합니다."
            }), 400
        
        if limit is not None and limit <= 0:
            return jsonify({
                "error_code": "INVALID_PARAMETER", 
                "message": "limit은 1 이상이어야 합니다."
            }), 400
        
        # 요약 정보만 요청된 경우
        if summary_only:
            breeds_summary = breed_service.get_breeds_summary(limit)
            result = {
                'breeds': breeds_summary,
                'total_count': len(breeds_summary)
            }
            return jsonify(BreedSummaryListSchema().dump(result)), 200
        
        # 전체 정보 조회
        breeds, total_count = breed_service.get_all_breeds(limit, offset)
        
        result = {
            'breeds': breeds,
            'total_count': total_count
        }
        
        logger.info(f"품종 목록 조회 성공: {len(breeds)}개 반환")
        return jsonify(BreedListSchema().dump(result)), 200
        
    except Exception as e:
        logger.error(f"품종 목록 조회 실패: {e}", exc_info=True)
        return jsonify({
            "error_code": "BREED_FETCH_FAILED",
            "message": "품종 목록을 조회하는 중 오류가 발생했습니다."
        }), 500

@breeds_bp.route('/<breed_name>', methods=['GET'])
def get_breed_by_name(breed_name: str):
    """
    특정 품종 정보를 조회합니다.
    
    Path Parameters:
        - breed_name (str): 품종명 (URL 인코딩된 상태)
    """
    try:
        # URL 디코딩 (한글 품종명 처리)
        decoded_breed_name = unquote(breed_name)
        
        # 품종 정보 조회
        breed_data = breed_service.get_breed_by_name(decoded_breed_name)
        
        if not breed_data:
            return jsonify({
                "error_code": "BREED_NOT_FOUND",
                "message": f"품종을 찾을 수 없습니다: {decoded_breed_name}"
            }), 404
        
        logger.info(f"품종 정보 조회 성공: {decoded_breed_name}")
        return jsonify(BreedSchema().dump(breed_data)), 200
        
    except Exception as e:
        logger.error(f"품종 정보 조회 실패 ({breed_name}): {e}", exc_info=True)
        return jsonify({
            "error_code": "BREED_FETCH_FAILED",
            "message": f"품종 정보를 조회하는 중 오류가 발생했습니다: {breed_name}"
        }), 500

@breeds_bp.route('/search', methods=['GET'])
def search_breeds():
    """
    품종명으로 검색합니다.
    
    Query Parameters:
        - q (str, required): 검색 쿼리
        - limit (int, optional): 조회할 최대 개수 (기본값: 50)
        - offset (int, optional): 건너뛸 개수 (기본값: 0)
    """
    try:
        # 쿼리 파라미터 파싱
        query = request.args.get('q', '').strip()
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)
        
        # 필수 파라미터 검증
        if not query:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "검색 쿼리(q)가 필요합니다."
            }), 400
        
        # 파라미터 유효성 검사
        if len(query) > 100:
            return jsonify({
                "error_code": "INVALID_PARAMETER",
                "message": "검색 쿼리는 100자를 초과할 수 없습니다."
            }), 400
        
        if offset < 0 or limit <= 0 or limit > 100:
            return jsonify({
                "error_code": "INVALID_PARAMETER",
                "message": "offset은 0 이상, limit은 1-100 사이여야 합니다."
            }), 400
        
        # 품종 검색 실행
        breeds, total_count = breed_service.search_breeds(query, limit, offset)
        
        result = {
            'breeds': breeds,
            'total_count': total_count
        }
        
        logger.info(f"품종 검색 성공: '{query}' -> {len(breeds)}개 반환")
        return jsonify(BreedListSchema().dump(result)), 200
        
    except Exception as e:
        logger.error(f"품종 검색 실패: {e}", exc_info=True)
        return jsonify({
            "error_code": "BREED_SEARCH_FAILED",
            "message": "품종 검색 중 오류가 발생했습니다."
        }), 500

@breeds_bp.route('/exists/<breed_name>', methods=['GET'])
def check_breed_exists(breed_name: str):
    """
    특정 품종이 존재하는지 확인합니다.
    
    Path Parameters:
        - breed_name (str): 품종명 (URL 인코딩된 상태)
    """
    try:
        # URL 디코딩
        decoded_breed_name = unquote(breed_name)
        
        # 품종 존재 여부 확인
        exists = breed_service.breed_exists(decoded_breed_name)
        
        result = {
            'breed_name': decoded_breed_name,
            'exists': exists
        }
        
        logger.info(f"품종 존재 확인: {decoded_breed_name} -> {exists}")
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"품종 존재 확인 실패 ({breed_name}): {e}", exc_info=True)
        return jsonify({
            "error_code": "BREED_CHECK_FAILED",
            "message": f"품종 존재 확인 중 오류가 발생했습니다: {breed_name}"
        }), 500

@breeds_bp.route('/statistics', methods=['GET'])
def get_breed_statistics():
    """
    품종 데이터베이스 통계 정보를 조회합니다.
    """
    try:
        stats = breed_service.get_statistics()
        
        logger.info("품종 통계 정보 조회 성공")
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"품종 통계 정보 조회 실패: {e}", exc_info=True)
        return jsonify({
            "error_code": "STATS_FETCH_FAILED",
            "message": "통계 정보를 조회하는 중 오류가 발생했습니다."
        }), 500

@breeds_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Marshmallow 유효성 검사 오류 처리"""
    return jsonify({
        "error_code": "VALIDATION_ERROR",
        "message": "요청 데이터가 유효하지 않습니다.",
        "details": error.messages
    }), 400

@breeds_bp.errorhandler(404)
def handle_not_found(error):
    """404 오류 처리"""
    return jsonify({
        "error_code": "NOT_FOUND",
        "message": "요청한 리소스를 찾을 수 없습니다."
    }), 404

@breeds_bp.errorhandler(500)
def handle_internal_error(error):
    """500 오류 처리"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "error_code": "INTERNAL_SERVER_ERROR",
        "message": "서버 내부 오류가 발생했습니다."
    }), 500
