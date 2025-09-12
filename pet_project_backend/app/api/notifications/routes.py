import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from .schemas import (
    notification_list_request_schema,
    NotificationListResponseSchema,
    NotificationUnreadCountResponseSchema,
)
from app.utils.error_catalog import build_error

notifications_bp = Blueprint('notifications_bp', __name__)


@notifications_bp.route('', methods=['GET'])
@jwt_required()
def list_notifications():
    """알림 목록 조회

    사용자의 알림 목록을 페이지네이션으로 조회합니다. 포맷(mobile/web)과 커서 기반 페이지네이션을 지원합니다.

    RequestSchema: NotificationListRequestSchema (query params)
    ResponseSchema[200]: NotificationListResponseSchema
    """
    try:
        # 요청 검증
        try:
            args = notification_list_request_schema.load(request.args)
        except ValidationError as err:
            return jsonify({
                'error_code': 'INVALID_PARAMETER',
                'message': '요청 파라미터가 올바르지 않습니다.',
                'details': err.messages
            }), 400
        
        # 서비스 인스턴스 가져오기
        notification_service = current_app.services['notifications']
        presentation_service = current_app.services['notification_presentation']
        
        # 요청 파라미터 추출
        user_id = get_jwt_identity()
        limit = args['limit']
        cursor = args['cursor']
        format_type = args['format']
        
        # 프레젠테이션 서비스를 통해 포맷된 알림 조회
        formatted_notifications, next_cursor = presentation_service.get_formatted_notifications(
            notification_service, user_id, limit=limit, cursor=cursor, format_type=format_type
        )

        return jsonify({
            'items': formatted_notifications,
            'meta': {
                'next_cursor': next_cursor,
                'has_more': bool(next_cursor)
            }
        }), 200
        
    except Exception as e:
        logging.error(f"알림 목록 조회 오류: {e}", exc_info=True)
        return jsonify({
            'error_code': 'FETCH_FAILED', 
            'message': '알림 조회 중 오류가 발생했습니다.'
        }), 500


@notifications_bp.route('/<string:notification_id>/ack', methods=['POST'])
@jwt_required()
def ack_notification(notification_id: str):
    """알림 확인 처리

    특정 알림을 확인 상태로 변경합니다. 확인된 알림은 미확인 알림 수에 포함되지 않습니다.

    RequestSchema: EmptyRequestSchema
    ResponseSchema[200]: NotificationAckResponseSchema
    """
    service = current_app.services['notifications']
    user_id = get_jwt_identity()
    try:
        ok = service.ack_notification(user_id, notification_id)
        if not ok:
            # 정확한 구분: 존재하지 않거나 권한 없음 -> 우선 NOT_FOUND (정보 누출 방지)
            status, body = build_error('NOT_FOUND', message='알림이 없거나 권한이 없습니다.')
            return jsonify(body), status
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logging.error(f"알림 확인 처리 오류: {e}", exc_info=True)
        status, body = build_error('ACK_FAILED', message='알림 확인 처리 중 오류가 발생했습니다.')
        return jsonify(body), status


@notifications_bp.route('/unread-count', methods=['GET'])
@jwt_required()
def get_unread_count():
    """미확인 알림 수 조회

    사용자의 미확인 알림 개수를 조회합니다.

    ResponseSchema[200]: NotificationUnreadCountResponseSchema
    """
    service = current_app.services['notifications']
    user_id = get_jwt_identity()
    try:
        count = service.get_unread_count(user_id)
        return jsonify({'unread_count': count}), 200
    except Exception as e:
        logging.error(f"미확인 알림 카운트 조회 오류: {e}", exc_info=True)
        return jsonify({'error_code': 'FETCH_FAILED', 'message': '카운트 조회 중 오류가 발생했습니다.'}), 500
