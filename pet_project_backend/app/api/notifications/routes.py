import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from .schemas import notification_list_request_schema, error_response_schema
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, NotificationErrors, ExternalServiceErrors, RequestExamples, ResponseExamples
)
from app.utils.error_catalog import build_error

notifications_bp = Blueprint('notifications_bp', __name__)


@notifications_bp.route('', methods=['GET'])
@jwt_required()
@api_doc(
    summary="알림 목록 조회",
    description="사용자의 알림 목록을 페이지네이션으로 조회합니다. 포맷(mobile/web)과 커서 기반 페이지네이션을 지원합니다.",
    tags=["notifications"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    NotificationErrors.INVALID_FORMAT,
    ExternalServiceErrors.FIREBASE_CONNECTION_ERROR,
    CommonErrors.INTERNAL_SERVER_ERROR
)
@response_examples(
    {
        "name": "successful_response",
        "summary": "성공적인 알림 목록 조회",
        "value": {
            "items": [
                {
                    "id": "notif_001",
                    "type": "COMMENT",
                    "title": "새로운 댓글",
                    "message": "테스트유저님이 댓글을 남겼습니다",
                    "created_at": "2023-12-10T12:00:00Z",
                    "deeplink": "app://posts/post_123",
                    "read": False
                }
            ],
            "meta": {
                "next_cursor": "cursor_123",
                "has_more": True
            }
        }
    }
)
def list_notifications():
    """
    GET /api/notifications?limit&cursor&format
    페이로드: { id, type, title, message, created_at, deeplink, read }
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
@api_doc(
    summary="알림 확인 처리",
    description="특정 알림을 확인 상태로 변경합니다. 확인된 알림은 미확인 알림 수에 포함되지 않습니다.",
    tags=["notifications"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    NotificationErrors.NOTIFICATION_NOT_FOUND,
    NotificationErrors.ACK_FAILED
)
@response_examples({
    "name": "ack_success",
    "summary": "알림 확인 처리 성공",
    "description": "알림이 성공적으로 확인 상태로 변경됨",
    "value": {"status": "ok"}
})
def ack_notification(notification_id: str):
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
@api_doc(
    summary="미확인 알림 수 조회",
    description="사용자의 미확인 알림 개수를 조회합니다.",
    tags=["notifications"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    NotificationErrors.FETCH_FAILED
)
@response_examples({
    "name": "unread_count",
    "summary": "미확인 알림 수",
    "description": "사용자의 미확인 알림 개수",
    "value": {"unread_count": 5}
})
def get_unread_count():
    service = current_app.services['notifications']
    user_id = get_jwt_identity()
    try:
        count = service.get_unread_count(user_id)
        return jsonify({'unread_count': count}), 200
    except Exception as e:
        logging.error(f"미확인 알림 카운트 조회 오류: {e}", exc_info=True)
        return jsonify({'error_code': 'FETCH_FAILED', 'message': '카운트 조회 중 오류가 발생했습니다.'}), 500
