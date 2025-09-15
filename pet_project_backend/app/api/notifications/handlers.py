"""
알림 타입별 처리 로직을 담당하는 핸들러 클래스들.
각 핸들러는 타입별 포맷팅, 메시지 생성, 딥링크 생성을 담당합니다.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.models.notification import NotificationType
from .config import NotificationConfig


class NotificationTypeHandler(ABC):
    """알림 타입별 핸들러의 베이스 클래스"""
    
    def __init__(self, notification_type: str = None):
        self.notification_type = notification_type
        self.config = NotificationConfig()
    
    @abstractmethod
    def get_title(self, language: str = 'ko') -> str:
        """알림 타이틀을 반환합니다."""
        pass
    
    @abstractmethod
    def get_body(self, sender_nickname: str, target_summary: Optional[str] = None, 
                 language: str = 'ko') -> str:
        """알림 본문을 반환합니다."""
        pass
    
    @abstractmethod
    def get_deeplink(self, target_id: str, **kwargs) -> str:
        """딥링크를 반환합니다."""
        pass
    
    def format_notification(self, notification_data: Dict[str, Any], 
                          format_type: str = 'mobile', language: str = 'ko') -> Dict[str, Any]:
        """알림 데이터를 클라이언트 응답 형식으로 변환합니다."""
        sender = notification_data.get('sender', {})
        sender_nickname = sender.get('nickname', '누군가')
        target_summary = notification_data.get('target_summary')
        target_id = notification_data.get('target_id')
        
        # 추가 파라미터 추출
        kwargs = {
            'pet_id': notification_data.get('pet_id'),
            'recipient_id': notification_data.get('recipient_id'),
            'record_type': notification_data.get('record_type')
        }
        
        # 포맷 설정 적용
        format_config = self.config.get_format_config(format_type)
        
        title = self.get_title(language)
        message = self.get_body(sender_nickname, target_summary, language)
        
        # 길이 제한 적용
        if len(title) > format_config.get('max_title_length', 100):
            title = title[:format_config.get('max_title_length', 100) - 3] + '...'
        
        if len(message) > format_config.get('max_message_length', 200):
            message = message[:format_config.get('max_message_length', 200) - 3] + '...'
        
        result = {
            'id': notification_data.get('notification_id'),
            'type': notification_data.get('type'),
            'title': title,
            'message': message,
            'created_at': notification_data.get('created_at'),
            'deeplink': self.get_deeplink(target_id, **kwargs),
            'read': notification_data.get('is_read', False)
        }
        
        # 포맷별 추가 필드
        if format_config.get('include_sender_avatar'):
            result['sender_avatar'] = sender.get('profile_image_url')
        
        return result


class TemplateBasedHandler(NotificationTypeHandler):
    """템플릿 기반 핸들러 - 설정에서 메시지를 가져옵니다."""
    
    def __init__(self, notification_type: str):
        super().__init__(notification_type)
        self.notification_type = notification_type
    
    def get_title(self, language: str = 'ko') -> str:
        return self.config.get_title_template(self.notification_type, language)
    
    def get_body(self, sender_nickname: str, target_summary: Optional[str] = None, 
                 language: str = 'ko') -> str:
        template = self.config.get_message_template(self.notification_type, language)
        return template.format(
            sender=sender_nickname,
            summary=target_summary or ''
        )
    
    def get_deeplink(self, target_id: str, **kwargs) -> str:
        """기본 딥링크 로직 - 하위 클래스에서 오버라이드 가능"""
        return f"app://home"


class CommentNotificationHandler(TemplateBasedHandler):
    """댓글 알림 핸들러"""
    
    def __init__(self):
        super().__init__('COMMENT')
    
    def get_deeplink(self, target_id: str, **kwargs) -> str:
        template = self.config.get_deeplink_template('post')
        return template.format(target_id=target_id)


class PostLikeNotificationHandler(TemplateBasedHandler):
    """게시물 좋아요 알림 핸들러"""
    
    def __init__(self):
        super().__init__('POST_LIKE')
    
    def get_deeplink(self, target_id: str, **kwargs) -> str:
        template = self.config.get_deeplink_template('post')
        return template.format(target_id=target_id)


class CommentLikeNotificationHandler(TemplateBasedHandler):
    """댓글 좋아요 알림 핸들러"""
    
    def __init__(self):
        super().__init__('COMMENT_LIKE')
    
    def get_deeplink(self, target_id: str, **kwargs) -> str:
        template = self.config.get_deeplink_template('comment')
        return template.format(target_id=target_id)


class MentionNotificationHandler(TemplateBasedHandler):
    """멘션 알림 핸들러"""
    
    def __init__(self):
        super().__init__('MENTION')
    
    def get_deeplink(self, target_id: str, **kwargs) -> str:
        template = self.config.get_deeplink_template('post')
        return template.format(target_id=target_id)


class CartoonNotificationHandler(TemplateBasedHandler):
    """카툰 관련 알림 핸들러 베이스"""
    
    def get_deeplink(self, target_id: str, **kwargs) -> str:
        template = self.config.get_deeplink_template('cartoon_job')
        return template.format(target_id=target_id)


class CartoonSuccessNotificationHandler(CartoonNotificationHandler):
    """카툰 생성 성공 알림 핸들러"""
    
    def __init__(self):
        super().__init__('CARTOON_SUCCESS')


class CartoonFailedNotificationHandler(CartoonNotificationHandler):
    """카툰 생성 실패 알림 핸들러"""
    
    def __init__(self):
        super().__init__('CARTOON_FAILED')


class CartoonProgressNotificationHandler(CartoonNotificationHandler):
    """카툰 진행 중 알림 핸들러"""
    
    def __init__(self):
        super().__init__('CARTOON_PROGRESS')


class CartoonCompletedNotificationHandler(CartoonNotificationHandler):
    """카툰 완료 알림 핸들러"""
    
    def __init__(self):
        super().__init__('CARTOON_COMPLETED')


class PetCareNotificationHandler(TemplateBasedHandler):
    """펫케어 관련 알림 핸들러 베이스"""
    
    def get_deeplink(self, target_id: str, **kwargs) -> str:
        template = self.config.get_deeplink_template('pet_care')
        pet_id = kwargs.get('pet_id') or kwargs.get('recipient_id')
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        record_type = kwargs.get('record_type') or 'weight'
        
        return template.format(
            pet_id=pet_id,
            date=today,
            tab=record_type
        )


class PetCareGoalReachedNotificationHandler(PetCareNotificationHandler):
    """펫케어 목표 달성 알림 핸들러"""
    
    def __init__(self):
        super().__init__('PET_CARE_GOAL_REACHED')


class PetCareDailySummaryNotificationHandler(PetCareNotificationHandler):
    """펫케어 일일 요약 알림 핸들러"""
    
    def __init__(self):
        super().__init__('PET_CARE_DAILY_SUMMARY')


class NotificationHandlerFactory:
    """알림 타입에 따른 핸들러를 제공하는 팩토리 클래스"""
    
    def __init__(self):
        self._handlers = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """기본 핸들러들을 등록합니다."""
        self._handlers.update({
            NotificationType.COMMENT.value: CommentNotificationHandler,
            NotificationType.POST_LIKE.value: PostLikeNotificationHandler,
            NotificationType.COMMENT_LIKE.value: CommentLikeNotificationHandler,
            NotificationType.MENTION.value: MentionNotificationHandler,
            NotificationType.CARTOON_SUCCESS.value: CartoonSuccessNotificationHandler,
            NotificationType.CARTOON_FAILED.value: CartoonFailedNotificationHandler,
            NotificationType.CARTOON_PROGRESS.value: CartoonProgressNotificationHandler,
            NotificationType.CARTOON_COMPLETED.value: CartoonCompletedNotificationHandler,
            NotificationType.PET_CARE_GOAL_REACHED.value: PetCareGoalReachedNotificationHandler,
            NotificationType.PET_CARE_DAILY_SUMMARY.value: PetCareDailySummaryNotificationHandler,
        })
    
    def get_handler(self, notification_type: str) -> NotificationTypeHandler:
        """알림 타입에 해당하는 핸들러를 반환합니다."""
        handler_class = self._handlers.get(notification_type)
        if not handler_class:
            # 기본 핸들러로 TemplateBasedHandler 사용
            return TemplateBasedHandler(notification_type)
        return handler_class()
    
    def register_handler(self, notification_type: str, handler_class: type):
        """새로운 알림 타입 핸들러를 등록합니다."""
        self._handlers[notification_type] = handler_class
    
    def get_supported_types(self) -> list:
        """지원되는 알림 타입 목록을 반환합니다."""
        return list(self._handlers.keys())
    
    def unregister_handler(self, notification_type: str):
        """핸들러 등록을 해제합니다."""
        if notification_type in self._handlers:
            del self._handlers[notification_type]
