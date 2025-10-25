# app/api/notifications/services.py
"""
알림 프레젠테이션 로직을 담당하는 서비스 클래스.
NotificationService와 협력하여 클라이언트 응답 형식으로 변환합니다.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple

from .handlers import NotificationHandlerFactory


class NotificationPresentationService:
    """
    알림 프레젠테이션 로직을 담당하는 서비스.
    알림 데이터를 클라이언트가 요구하는 형식으로 변환합니다.
    """
    
    def __init__(self, handler_factory=None):
        """Initialize presentation service with optional handler factory.
        
        Args:
            handler_factory: Optional NotificationHandlerFactory instance (creates default if None)
        """
        self.handler_factory = handler_factory if handler_factory is not None else NotificationHandlerFactory()
    
    def format_notifications(self, notifications: List[Dict[str, Any]], 
                           format_type: str = 'mobile', 
                           language: str = 'ko') -> List[Dict[str, Any]]:
        """
        알림 목록을 클라이언트 형식으로 변환합니다.
        
        Args:
            notifications: 원본 알림 데이터 목록
            format_type: 포맷 타입 ('mobile', 'web' 등)
            language: 언어 설정
        
        Returns:
            변환된 알림 목록
        """
        formatted_notifications = []
        
        for notification in notifications:
            try:
                formatted = self.format_single_notification(notification, format_type, language)
                formatted_notifications.append(formatted)
            except Exception as e:
                logging.error(f"알림 포맷팅 오류 (ID: {notification.get('notification_id')}): {e}", 
                            exc_info=True)
                # 오류가 발생한 알림은 기본 포맷으로 처리
                formatted_notifications.append(self._get_fallback_format(notification))
        
        return formatted_notifications
    
    def format_single_notification(self, notification: Dict[str, Any], 
                                 format_type: str = 'mobile', 
                                 language: str = 'ko') -> Dict[str, Any]:
        """
        단일 알림을 클라이언트 형식으로 변환합니다.
        
        Args:
            notification: 원본 알림 데이터
            format_type: 포맷 타입
            language: 언어 설정
        
        Returns:
            변환된 알림 데이터
        """
        notification_type = notification.get('type')
        if not notification_type:
            return self._get_fallback_format(notification)
        
        try:
            handler = self.handler_factory.get_handler(notification_type)
            formatted = handler.format_notification(notification, format_type, language)
            
            # 포맷 타입별 추가 처리 (기존 방식과의 호환성 유지)
            if format_type == 'web':
                formatted = self._apply_web_format(formatted)
            elif format_type == 'mobile':
                formatted = self._apply_mobile_format(formatted)
            
            return formatted
            
        except Exception as e:
            logging.error(f"핸들러 처리 오류 (type: {notification_type}): {e}", exc_info=True)
            return self._get_fallback_format(notification)
    
    def get_formatted_notifications(self, notification_service, user_id: str, 
                                  limit: int = 20, cursor: Optional[str] = None,
                                  format_type: str = 'mobile', 
                                  language: str = 'ko') -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        사용자의 포맷된 알림 목록을 조회합니다.
        
        Args:
            notification_service: NotificationService 인스턴스
            user_id: 사용자 ID
            limit: 조회할 알림 수
            cursor: 페이지네이션 커서
            format_type: 포맷 타입
            language: 언어 설정
        
        Returns:
            (포맷된 알림 목록, 다음 커서)
        """
        notifications, next_cursor = notification_service.list_notifications(
            user_id, limit=limit, cursor=cursor
        )
        
        formatted_notifications = self.format_notifications(notifications, format_type, language)
        
        return formatted_notifications, next_cursor
    
    def _apply_mobile_format(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """모바일 형식 추가 처리"""
        # 모바일에서는 메시지 길이 제한
        message = notification.get('message', '')
        if len(message) > 100:
            notification['message'] = message[:97] + '...'
        
        return notification
    
    def _apply_web_format(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """웹 형식 추가 처리"""
        # 웹에서는 더 긴 메시지 허용
        return notification
    
    def _get_fallback_format(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """오류 발생 시 사용할 기본 포맷"""
        return {
            'id': notification.get('notification_id'),
            'type': notification.get('type', 'UNKNOWN'),
            'title': '알림',
            'message': notification.get('target_summary', 'HappyDog 알림'),
            'created_at': notification.get('created_at'),
            'deeplink': 'app://home',
            'read': notification.get('is_read', False)
        }
    
    def register_custom_handler(self, notification_type: str, handler_class: type):
        """커스텀 핸들러를 등록합니다."""
        self.handler_factory.register_handler(notification_type, handler_class)
    
    def get_supported_types(self) -> List[str]:
        """지원되는 알림 타입 목록을 반환합니다."""
        return self.handler_factory.get_supported_types()


class NotificationConfigService:
    """
    알림 설정 및 구성을 관리하는 서비스.
    다양한 포맷 타입과 클라이언트별 설정을 처리합니다.
    """
    
    def __init__(self):
        self.format_configs = {
            'mobile': {
                'max_message_length': 100,
                'show_deeplink': True,
                'include_sender_avatar': False
            },
            'web': {
                'max_message_length': 200,
                'show_deeplink': True,
                'include_sender_avatar': True
            }
        }
    
    def get_format_config(self, format_type: str) -> Dict[str, Any]:
        """포맷 타입별 설정을 반환합니다."""
        return self.format_configs.get(format_type, self.format_configs['mobile'])
    
    def update_format_config(self, format_type: str, config: Dict[str, Any]):
        """포맷 타입별 설정을 업데이트합니다."""
        if format_type in self.format_configs:
            self.format_configs[format_type].update(config)
        else:
            self.format_configs[format_type] = config
