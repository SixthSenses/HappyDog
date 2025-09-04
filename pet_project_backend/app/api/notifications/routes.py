import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

notifications_bp = Blueprint('notifications_bp', __name__)


@notifications_bp.route('', methods=['GET'])
@jwt_required()
def list_notifications():
    """
    GET /api/notifications?limit&cursor
    페이로드: { id, type, title, message, created_at, deeplink, read }
    """
    service = current_app.services['notifications']
    user_id = get_jwt_identity()
    try:
        limit = int(request.args.get('limit', 20))
        cursor = request.args.get('cursor')
        items, next_cursor = service.list_notifications(user_id, limit=limit, cursor=cursor)

        def to_payload(n: dict):
            # 내부 필드에서 스펙에 맞춰 변환
            from app.models.notification import NotificationType
            type_value = n.get('type')
            # title/message/deeplink 구성은 서비스의 빌더를 재사용하기 어렵기 때문에 간단 매핑
            title = '알림'
            message = n.get('target_summary')
            deeplink = None
            try:
                # 타입에 맞춰 대략적인 타이틀 생성
                if type_value in [NotificationType.POST_LIKE.value, NotificationType.COMMENT_LIKE.value]:
                    title = '새로운 좋아요'
                elif type_value == NotificationType.COMMENT.value:
                    title = '새로운 댓글'
                elif type_value == NotificationType.MENTION.value:
                    title = '나를 언급했어요'
                elif type_value and type_value.startswith('CARTOON'):
                    title = '카툰 작업 알림'
                elif type_value and type_value.startswith('PET_CARE'):
                    title = '펫케어 알림'
                # deeplink 규칙 간단 반영
                if type_value and type_value.startswith('CARTOON'):
                    deeplink = f"app://cartoon-jobs/{n.get('target_id')}"
                elif type_value in (NotificationType.COMMENT.value, NotificationType.POST_LIKE.value, NotificationType.MENTION.value):
                    deeplink = f"app://posts/{n.get('target_id')}"
                elif type_value == NotificationType.COMMENT_LIKE.value:
                    deeplink = f"app://comments/{n.get('target_id')}"
                elif type_value and type_value.startswith('PET_CARE'):
                    # PET_CARE_* 규칙: petId/date/tab 포함, 기본값 적용
                    pet_id = n.get('pet_id') or n.get('recipient_id')  # 최소 식별 보조; 필요 시 알림 생성 시 pet_id 포함 추천
                    from datetime import datetime, timezone
                    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                    # record_type 힌트가 있으면 tab 반영, 기본 weight
                    tab = n.get('record_type') or 'weight'
                    deeplink = f"app://pet-care/dashboard?petId={pet_id}&date={today}&tab={tab}"
            except Exception:
                pass

            return {
                'id': n.get('notification_id'),
                'type': type_value,
                'title': title,
                'message': message,
                'created_at': n.get('created_at'),
                'deeplink': deeplink,
                'read': n.get('is_read', False)
            }

        return jsonify({
            'items': [to_payload(it) for it in items],
            'meta': {
                'next_cursor': next_cursor,
                'has_more': bool(next_cursor)
            }
        }), 200
    except Exception as e:
        logging.error(f"알림 목록 조회 오류: {e}", exc_info=True)
        return jsonify({'error_code': 'FETCH_FAILED', 'message': '알림 조회 중 오류가 발생했습니다.'}), 500


@notifications_bp.route('/<string:notification_id>/ack', methods=['POST'])
@jwt_required()
def ack_notification(notification_id: str):
    service = current_app.services['notifications']
    user_id = get_jwt_identity()
    try:
        ok = service.ack_notification(user_id, notification_id)
        if not ok:
            return jsonify({'error_code': 'NOT_FOUND_OR_FORBIDDEN', 'message': '알림이 없거나 권한이 없습니다.'}), 404
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logging.error(f"알림 확인 처리 오류: {e}", exc_info=True)
        return jsonify({'error_code': 'ACK_FAILED', 'message': '알림 확인 처리 중 오류가 발생했습니다.'}), 500


@notifications_bp.route('/unread-count', methods=['GET'])
@jwt_required()
def get_unread_count():
    service = current_app.services['notifications']
    user_id = get_jwt_identity()
    try:
        count = service.get_unread_count(user_id)
        return jsonify({'unread_count': count}), 200
    except Exception as e:
        logging.error(f"미확인 알림 카운트 조회 오류: {e}", exc_info=True)
        return jsonify({'error_code': 'FETCH_FAILED', 'message': '카운트 조회 중 오류가 발생했습니다.'}), 500
