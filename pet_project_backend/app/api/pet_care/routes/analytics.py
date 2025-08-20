# app/api/pet_care/routes/analytics.py
"""
펫케어 분석 및 통계 자원 관리 라우트

자원: /api/pets/{pet_id}/care/analytics
- 트렌드 분석, 그래프 데이터, 통계 리포트 제공
- 사용자의 펫케어 패턴과 인사이트를 시각화하기 위한 데이터
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.utils.datetime_utils import DateTimeUtils
from ..schemas import GraphDataSchema, ErrorResponseSchema

logger = logging.getLogger(__name__)

# 분석/통계 전용 블루프린트
analytics_bp = Blueprint('analytics', __name__)

def get_analytics_service():
    """분석 서비스를 가져옵니다."""
    return current_app.services.get('analytics')

def get_pet_care_service():
    """기존 펫케어 서비스를 가져옵니다 (호환성)."""
    return current_app.services.get('pet_care')

# ================== 분석 및 통계 API ==================

@analytics_bp.route('/trends', methods=['GET'])
@jwt_required()
def get_trends(pet_id: str):
    """
    펫케어 데이터의 트렌드를 분석합니다.
    
    Query Parameters:
        metric (required): 분석할 지표 (weight, calories, water, activity)
        period (required): 분석 기간 (weekly, monthly, yearly)
        
    Response:
        200: 트렌드 분석 데이터
        400: 잘못된 파라미터
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 파라미터 검증
        metric = request.args.get('metric')
        period = request.args.get('period')
        
        if not metric:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "지표 파라미터(metric)가 필요합니다."
            }), 400
        
        if not period:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "기간 파라미터(period)가 필요합니다."
            }), 400
        
        valid_metrics = ['weight', 'calories', 'water', 'activity']
        valid_periods = ['weekly', 'monthly', 'yearly']
        
        if metric not in valid_metrics:
            return jsonify({
                "error_code": "INVALID_METRIC",
                "message": f"유효하지 않은 지표입니다. 사용 가능한 지표: {', '.join(valid_metrics)}"
            }), 400
        
        if period not in valid_periods:
            return jsonify({
                "error_code": "INVALID_PERIOD",
                "message": f"유효하지 않은 기간입니다. 사용 가능한 기간: {', '.join(valid_periods)}"
            }), 400
        
        # 트렌드 데이터 조회 (기존 그래프 데이터 활용)
        trend_data = pet_care_service.get_graph_data(pet_id, user_id, metric, period)
        
        # 트렌드 분석 결과에 추가 인사이트 포함
        analysis_result = {
            **trend_data,
            'insights': _generate_trend_insights(trend_data, metric),
            'recommendations': _generate_trend_recommendations(trend_data, metric)
        }
        
        logger.info(f"트렌드 분석 성공: {pet_id} - {metric} {period}")
        return jsonify(analysis_result), 200
        
    except PermissionError as e:
        logger.warning(f"트렌드 분석 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"트렌드 분석 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "TREND_ANALYSIS_FAILED",
            "message": "트렌드 분석 중 오류가 발생했습니다."
        }), 500

@analytics_bp.route('/graphs', methods=['GET'])
@jwt_required()
def get_graph_data(pet_id: str):
    """
    그래프 데이터를 조회합니다.
    
    Query Parameters:
        type (required): 그래프 타입 (calories, water, activity, weight)
        range (required): 데이터 범위 (7d, 30d, 90d, 1y)
        
    Response:
        200: 그래프 데이터
        400: 잘못된 파라미터
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 파라미터 검증
        graph_type = request.args.get('type')
        date_range = request.args.get('range')
        
        if not graph_type:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "그래프 타입(type) 파라미터가 필요합니다."
            }), 400
        
        if not date_range:
            return jsonify({
                "error_code": "MISSING_PARAMETER",
                "message": "데이터 범위(range) 파라미터가 필요합니다."
            }), 400
        
        # 파라미터 매핑
        type_mapping = {
            'calories': 'calories',
            'water': 'water',
            'activity': 'activity',
            'weight': 'weight'
        }
        
        range_mapping = {
            '7d': 'weekly',
            '30d': 'monthly', 
            '90d': 'monthly',
            '1y': 'yearly'
        }
        
        if graph_type not in type_mapping:
            return jsonify({
                "error_code": "INVALID_GRAPH_TYPE",
                "message": f"유효하지 않은 그래프 타입입니다. 사용 가능한 타입: {', '.join(type_mapping.keys())}"
            }), 400
        
        if date_range not in range_mapping:
            return jsonify({
                "error_code": "INVALID_DATE_RANGE",
                "message": f"유효하지 않은 날짜 범위입니다. 사용 가능한 범위: {', '.join(range_mapping.keys())}"
            }), 400
        
        # 그래프 데이터 조회
        metric = type_mapping[graph_type]
        period = range_mapping[date_range]
        
        graph_data = pet_care_service.get_graph_data(pet_id, user_id, metric, period)
        
        # 그래프 전용 추가 정보
        enhanced_data = {
            **graph_data,
            'graph_type': graph_type,
            'date_range': date_range,
            'chart_config': _get_chart_config(graph_type),
            'data_quality': _assess_data_quality(graph_data['data_points'])
        }
        
        logger.info(f"그래프 데이터 조회 성공: {pet_id} - {graph_type} {date_range}")
        return jsonify(GraphDataSchema().dump(enhanced_data)), 200
        
    except PermissionError as e:
        logger.warning(f"그래프 데이터 조회 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"그래프 데이터 조회 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "GRAPH_DATA_FETCH_FAILED",
            "message": "그래프 데이터 조회 중 오류가 발생했습니다."
        }), 500

@analytics_bp.route('/reports', methods=['GET'])
@jwt_required()
def get_comprehensive_report(pet_id: str):
    """
    종합 펫케어 리포트를 생성합니다.
    
    Query Parameters:
        period (optional): 리포트 기간 (weekly, monthly) - 기본값: monthly
        
    Response:
        200: 종합 리포트 데이터
    """
    try:
        user_id = get_jwt_identity()
        pet_care_service = get_pet_care_service()
        
        if not pet_care_service:
            return jsonify({
                "error_code": "SERVICE_UNAVAILABLE",
                "message": "펫케어 서비스를 사용할 수 없습니다."
            }), 503
        
        # 기간 파라미터
        period = request.args.get('period', 'monthly')
        
        if period not in ['weekly', 'monthly']:
            return jsonify({
                "error_code": "INVALID_PERIOD",
                "message": "유효하지 않은 기간입니다. weekly 또는 monthly를 사용하세요."
            }), 400
        
        # 종합 리포트 데이터 수집
        report_data = {
            'period': period,
            'generated_at': DateTimeUtils.now().isoformat(),
            'pet_id': pet_id,
        }
        
        # 각 지표별 데이터 수집
        metrics = ['calories', 'water', 'activity', 'weight']
        for metric in metrics:
            try:
                data = pet_care_service.get_graph_data(pet_id, user_id, metric, period)
                report_data[f'{metric}_data'] = data
            except Exception as e:
                logger.warning(f"리포트 {metric} 데이터 수집 실패: {e}")
                report_data[f'{metric}_data'] = None
        
        # 종합 인사이트 생성
        report_data['insights'] = _generate_comprehensive_insights(report_data)
        report_data['health_score'] = _calculate_health_score(report_data)
        report_data['action_items'] = _generate_action_items(report_data)
        
        logger.info(f"종합 리포트 생성 성공: {pet_id} - {period}")
        return jsonify(report_data), 200
        
    except PermissionError as e:
        logger.warning(f"리포트 생성 권한 오류: {user_id} -> {pet_id}")
        return jsonify({
            "error_code": "FORBIDDEN",
            "message": str(e)
        }), 403
    except Exception as e:
        logger.error(f"리포트 생성 실패 ({pet_id}): {e}", exc_info=True)
        return jsonify({
            "error_code": "REPORT_GENERATION_FAILED",
            "message": "리포트 생성 중 오류가 발생했습니다."
        }), 500

# ================== 헬퍼 함수들 ==================

def _generate_trend_insights(trend_data: dict, metric: str) -> list:
    """트렌드 데이터를 기반으로 인사이트를 생성합니다."""
    insights = []
    
    trend = trend_data.get('trend', 'stable')
    avg_value = trend_data.get('avg_value', 0)
    
    if trend == 'increasing':
        if metric == 'weight':
            insights.append("체중이 증가하는 추세입니다. 식단 관리를 검토해보세요.")
        elif metric == 'calories':
            insights.append("칼로리 섭취가 증가하고 있습니다.")
        elif metric == 'activity':
            insights.append("활동량이 증가하고 있어 좋은 신호입니다!")
            
    elif trend == 'decreasing':
        if metric == 'activity':
            insights.append("활동량이 감소하고 있습니다. 더 많은 운동이 필요할 수 있습니다.")
        elif metric == 'water':
            insights.append("수분 섭취가 줄어들고 있습니다. 충분한 음수를 권장합니다.")
    
    return insights

def _generate_trend_recommendations(trend_data: dict, metric: str) -> list:
    """트렌드 기반 권장사항을 생성합니다."""
    recommendations = []
    
    trend = trend_data.get('trend', 'stable')
    
    if metric == 'weight' and trend == 'increasing':
        recommendations.append("체중 관리를 위해 저칼로리 간식으로 바꿔보세요.")
        recommendations.append("수의사와 상담하여 적정 체중 관리 계획을 세우세요.")
    
    if metric == 'activity' and trend == 'decreasing':
        recommendations.append("매일 산책 시간을 늘려보세요.")
        recommendations.append("실내 놀이 활동을 추가해보세요.")
    
    return recommendations

def _get_chart_config(graph_type: str) -> dict:
    """그래프 타입별 차트 설정을 반환합니다."""
    configs = {
        'calories': {
            'color': '#FF6B6B',
            'unit': 'kcal',
            'chart_type': 'line'
        },
        'water': {
            'color': '#4ECDC4', 
            'unit': 'ml',
            'chart_type': 'bar'
        },
        'activity': {
            'color': '#45B7D1',
            'unit': 'minutes',
            'chart_type': 'line'
        },
        'weight': {
            'color': '#96CEB4',
            'unit': 'kg',
            'chart_type': 'line'
        }
    }
    
    return configs.get(graph_type, {})

def _assess_data_quality(data_points: list) -> dict:
    """데이터 품질을 평가합니다."""
    if not data_points:
        return {
            'score': 0,
            'status': 'no_data',
            'message': '데이터가 없습니다.'
        }
    
    total_points = len(data_points)
    non_zero_points = len([p for p in data_points if p.get('value', 0) > 0])
    
    if total_points == 0:
        score = 0
    else:
        score = (non_zero_points / total_points) * 100
    
    if score >= 80:
        status = 'excellent'
        message = '데이터 품질이 우수합니다.'
    elif score >= 60:
        status = 'good'
        message = '데이터 품질이 양호합니다.'
    elif score >= 40:
        status = 'fair'
        message = '더 많은 데이터 기록이 필요합니다.'
    else:
        status = 'poor'
        message = '데이터가 부족합니다. 꾸준한 기록을 권장합니다.'
    
    return {
        'score': round(score, 1),
        'status': status,
        'message': message,
        'total_points': total_points,
        'recorded_points': non_zero_points
    }

def _generate_comprehensive_insights(report_data: dict) -> list:
    """종합 리포트를 위한 인사이트를 생성합니다."""
    insights = []
    
    # 각 지표별 데이터 확인
    for metric in ['calories', 'water', 'activity', 'weight']:
        data = report_data.get(f'{metric}_data')
        if data and data.get('trend'):
            trend = data['trend']
            if trend != 'stable':
                insights.append(f"{metric} 데이터가 {trend} 추세를 보이고 있습니다.")
    
    if not insights:
        insights.append("전반적으로 안정적인 패턴을 보이고 있습니다.")
    
    return insights

def _calculate_health_score(report_data: dict) -> dict:
    """건강 점수를 계산합니다."""
    scores = []
    
    # 각 지표별 점수 계산 (간단한 로직)
    for metric in ['calories', 'water', 'activity', 'weight']:
        data = report_data.get(f'{metric}_data')
        if data:
            # 데이터 일관성을 기준으로 점수 계산
            data_points = data.get('data_points', [])
            if data_points:
                consistency = len([p for p in data_points if p.get('value', 0) > 0]) / len(data_points)
                scores.append(consistency * 100)
    
    if scores:
        overall_score = sum(scores) / len(scores)
    else:
        overall_score = 0
    
    if overall_score >= 80:
        grade = 'A'
        message = '우수한 관리 상태입니다!'
    elif overall_score >= 60:
        grade = 'B'
        message = '양호한 관리 상태입니다.'
    elif overall_score >= 40:
        grade = 'C'
        message = '관리를 개선할 여지가 있습니다.'
    else:
        grade = 'D'
        message = '더 세심한 관리가 필요합니다.'
    
    return {
        'score': round(overall_score, 1),
        'grade': grade,
        'message': message
    }

def _generate_action_items(report_data: dict) -> list:
    """실행 가능한 액션 아이템을 생성합니다."""
    actions = []
    
    # 건강 점수를 기반으로 액션 아이템 생성
    health_score = report_data.get('health_score', {})
    score = health_score.get('score', 0)
    
    if score < 60:
        actions.append("매일 펫케어 기록을 작성해보세요.")
        actions.append("규칙적인 식사 시간을 정해보세요.")
        actions.append("일정한 산책 루틴을 만들어보세요.")
    
    # 트렌드 기반 액션 아이템
    for metric in ['calories', 'water', 'activity', 'weight']:
        data = report_data.get(f'{metric}_data')
        if data and data.get('trend') == 'decreasing' and metric == 'activity':
            actions.append("활동량 증가를 위한 새로운 놀이를 시도해보세요.")
    
    if not actions:
        actions.append("현재 관리 패턴을 잘 유지하고 계십니다!")
    
    return actions

# ================== 에러 핸들러 ==================

@analytics_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    """Marshmallow 유효성 검사 오류 처리"""
    return jsonify({
        "error_code": "VALIDATION_ERROR",
        "message": "요청 데이터가 유효하지 않습니다.",
        "details": error.messages
    }), 400
