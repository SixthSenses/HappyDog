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
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, BreedErrors, RequestExamples, ResponseExamples
)

logger = logging.getLogger(__name__)

breeds_bp = Blueprint('breeds_bp', __name__)

# 서비스 인스턴스는 앱 팩토리에서 주입받을 예정
def get_breed_service():
    """현재 앱에서 BreedService 인스턴스를 가져옵니다."""
    return current_app.services.get('breeds')

@breeds_bp.route('/', methods=['GET'])
@api_doc(
    summary="품종 목록 조회",
    description="모든 품종 목록을 조회합니다. 페이지네이션과 요약 정보 옵션을 지원합니다.",
    tags=["breeds"]
)
@error_responses(
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples(RequestExamples.PAGINATION_QUERY)
@response_examples({
    "name": "breeds_list",
    "summary": "품종 목록 응답",
    "description": "페이지네이션된 품종 목록",
    "value": {
        "breeds": [
            {
                "breed_id": "golden_retriever",
                "name": "골든 리트리버",
                "origin": "스코틀랜드",
                "size": "대형"
            }
        ],
        "total_count": 150
    }
})
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
        
        breed_service = get_breed_service()
        
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
@api_doc(
    summary="특정 품종 정보 조회",
    description="품종명으로 특정 품종의 상세 정보를 조회합니다. 한글 품종명도 지원합니다.",
    tags=["breeds"]
)
@error_responses(
    BreedErrors.BREED_NOT_FOUND,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "breed_detail",
    "summary": "품종 상세 정보",
    "description": "특정 품종의 상세 정보",
    "value": {
        "breed_id": "golden_retriever",
        "name": "골든 리트리버",
        "origin": "스코틀랜드",
        "size": "대형",
        "temperament": "친화적, 지능적, 활발함",
        "life_expectancy": "10-12년"
    }
})
def get_breed_by_name(breed_name: str):
    """
    특정 품종 정보를 조회합니다.
    
    Path Parameters:
        - breed_name (str): 품종명 (URL 인코딩된 상태)
    """
    try:
        breed_service = get_breed_service()
        
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
@api_doc(
    summary="품종 검색",
    description="품종명으로 검색하여 일치하는 품종들을 찾습니다. 부분 일치 검색을 지원합니다.",
    tags=["breeds"]
)
@error_responses(
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples({
    "name": "breed_search_query",
    "summary": "품종 검색 쿼리",
    "description": "품종 검색을 위한 쿼리 파라미터",
    "value": {"q": "리트리버", "limit": 10, "offset": 0}
})
@response_examples({
    "name": "breed_search_results",
    "summary": "품종 검색 결과",
    "description": "검색 쿼리와 일치하는 품종 목록",
    "value": {
        "breeds": [
            {"breed_id": "golden_retriever", "name": "골든 리트리버"},
            {"breed_id": "labrador_retriever", "name": "라브라도 리트리버"}
        ],
        "total_count": 2
    }
})
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
        
        breed_service = get_breed_service()
        
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
@api_doc(
    summary="품종 존재 여부 확인",
    description="특정 품종이 데이터베이스에 존재하는지 확인합니다.",
    tags=["breeds"]
)
@error_responses(
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples({
    "name": "breed_exists_check",
    "summary": "품종 존재 여부 응답",
    "description": "품종 존재 여부 확인 결과",
    "value": {
        "breed_name": "골든 리트리버",
        "exists": True
    }
})
def check_breed_exists(breed_name: str):
    """
    특정 품종이 존재하는지 확인합니다.
    
    Path Parameters:
        - breed_name (str): 품종명 (URL 인코딩된 상태)
    """
    try:
        breed_service = get_breed_service()
        
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
