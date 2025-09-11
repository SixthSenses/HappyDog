# app/api/notifications/schemas.py
"""
알림 API에 대한 Marshmallow 스키마 정의.
요청 검증 및 응답 시리얼라이제이션을 담당합니다.
"""
from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class NotificationListRequestSchema(Schema):
    """알림 목록 조회 요청 스키마"""
    
    limit = fields.Integer(
        load_default=20,
        validate=validate.Range(min=1, max=100),
        metadata={'description': '조회할 알림 수 (1-100)'}
    )
    
    cursor = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.Length(min=1),
        metadata={'description': '페이지네이션 커서'}
    )
    
    format = fields.String(
        load_default='mobile',
        validate=validate.OneOf(['mobile', 'web']),
        metadata={'description': '응답 포맷 타입'}
    )


class NotificationItemSchema(Schema):
    """단일 알림 응답 스키마"""
    
    id = fields.String(required=True, metadata={'description': '알림 ID'})
    type = fields.String(required=True, metadata={'description': '알림 타입'})
    title = fields.String(required=True, metadata={'description': '알림 제목'})
    message = fields.String(required=True, metadata={'description': '알림 메시지'})
    created_at = fields.String(required=True, metadata={'description': '생성 시간 (ISO 형식)'})
    deeplink = fields.String(required=True, metadata={'description': '딥링크 URL'})
    read = fields.Boolean(required=True, metadata={'description': '읽음 여부'})


class NotificationListResponseSchema(Schema):
    """알림 목록 응답 스키마"""
    
    items = fields.List(
        fields.Nested(NotificationItemSchema),
        required=True,
        metadata={'description': '알림 목록'}
    )
    
    meta = fields.Dict(
        required=True,
        metadata={'description': '메타데이터'}
    )
    
    class Meta:
        # meta 필드의 구조 정의
        meta_schema = {
            'next_cursor': fields.String(allow_none=True),
            'has_more': fields.Boolean()
        }


class NotificationAckRequestSchema(Schema):
    """알림 읽음 처리 요청 스키마"""
    pass  # URL 파라미터로만 처리


class NotificationUnreadCountResponseSchema(Schema):
    """미읽은 알림 수 응답 스키마"""
    
    unread_count = fields.Integer(
        required=True,
        validate=validate.Range(min=0),
        metadata={'description': '미읽은 알림 수'}
    )


class ErrorResponseSchema(Schema):
    """오류 응답 스키마"""
    
    error_code = fields.String(required=True, metadata={'description': '오류 코드'})
    message = fields.String(required=True, metadata={'description': '오류 메시지'})
    details = fields.Dict(load_default=None, allow_none=True, metadata={'description': '추가 오류 정보'})


# 스키마 인스턴스들
notification_list_request_schema = NotificationListRequestSchema()
notification_item_schema = NotificationItemSchema()
notification_list_response_schema = NotificationListResponseSchema()
notification_ack_request_schema = NotificationAckRequestSchema()
notification_unread_count_response_schema = NotificationUnreadCountResponseSchema()
error_response_schema = ErrorResponseSchema()
