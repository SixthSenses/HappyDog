# app/api/notifications/config.py
"""
알림 도메인 설정 및 구성 관리.
다양한 포맷 타입과 클라이언트별 설정을 중앙화합니다.
"""
from typing import Dict, Any


class NotificationConfig:
    """알림 도메인의 중앙 설정 클래스"""
    
    # 포맷 타입별 설정
    FORMAT_CONFIGS = {
        'mobile': {
            'max_title_length': 50,
            'max_message_length': 100,
            'show_deeplink': True,
            'include_sender_avatar': False,
            'compact_mode': True
        },
        'web': {
            'max_title_length': 100,
            'max_message_length': 200,
            'show_deeplink': True,
            'include_sender_avatar': True,
            'compact_mode': False
        }
    }
    
    # 알림 타입별 기본 설정
    TYPE_CONFIGS = {
        'COMMENT': {
            'priority': 'normal',
            'requires_sender': True,
            'requires_summary': True
        },
        'POST_LIKE': {
            'priority': 'low',
            'requires_sender': True,
            'requires_summary': False
        },
        'COMMENT_LIKE': {
            'priority': 'low',
            'requires_sender': True,
            'requires_summary': True
        },
        'MENTION': {
            'priority': 'high',
            'requires_sender': True,
            'requires_summary': True
        },
        'CARTOON_SUCCESS': {
            'priority': 'normal',
            'requires_sender': False,
            'requires_summary': False
        },
        'CARTOON_FAILED': {
            'priority': 'high',
            'requires_sender': False,
            'requires_summary': False
        },
        'PET_CARE_GOAL_REACHED': {
            'priority': 'normal',
            'requires_sender': False,
            'requires_summary': False
        }
    }
    
    # 딥링크 템플릿
    DEEPLINK_TEMPLATES = {
        'post': 'app://posts/{target_id}',
        'comment': 'app://comments/{target_id}',
        'cartoon_job': 'app://cartoon-jobs/{target_id}',
        'pet_care': 'app://pet-care/dashboard?petId={pet_id}&date={date}&tab={tab}',
        'home': 'app://home'
    }
    
    # 메시지 템플릿 (다국어 지원 준비)
    MESSAGE_TEMPLATES = {
        'ko': {
            'COMMENT': '{sender}님이 댓글을 남겼습니다: {summary}',
            'POST_LIKE': '{sender}님이 게시물을 좋아합니다',
            'COMMENT_LIKE': '{sender}님이 댓글을 좋아합니다: {summary}',
            'MENTION': '{sender}님이 나를 언급했습니다: {summary}',
            'CARTOON_SUCCESS': '카툰 생성이 완료되었습니다',
            'CARTOON_FAILED': '카툰 생성에 실패했습니다',
            'CARTOON_PROGRESS': '카툰 작업이 진행 중입니다',
            'CARTOON_COMPLETED': '카툰 작업이 완료되었습니다',
            'PET_CARE_GOAL_REACHED': '오늘 목표를 달성했어요!',
            'PET_CARE_DAILY_SUMMARY': '오늘의 펫케어 요약을 확인하세요'
        }
    }
    
    # 타이틀 템플릿
    TITLE_TEMPLATES = {
        'ko': {
            'COMMENT': '새로운 댓글',
            'POST_LIKE': '새로운 좋아요',
            'COMMENT_LIKE': '새로운 좋아요',
            'MENTION': '나를 언급했어요',
            'CARTOON_SUCCESS': '카툰 작업 알림',
            'CARTOON_FAILED': '카툰 작업 알림',
            'CARTOON_PROGRESS': '카툰 작업 알림',
            'CARTOON_COMPLETED': '카툰 작업 알림',
            'PET_CARE_GOAL_REACHED': '펫케어 알림',
            'PET_CARE_DAILY_SUMMARY': '펫케어 알림'
        }
    }
    
    @classmethod
    def get_format_config(cls, format_type: str) -> Dict[str, Any]:
        """포맷 타입별 설정을 반환합니다."""
        return cls.FORMAT_CONFIGS.get(format_type, cls.FORMAT_CONFIGS['mobile'])
    
    @classmethod
    def get_type_config(cls, notification_type: str) -> Dict[str, Any]:
        """알림 타입별 설정을 반환합니다."""
        return cls.TYPE_CONFIGS.get(notification_type, {})
    
    @classmethod
    def get_deeplink_template(cls, template_key: str) -> str:
        """딥링크 템플릿을 반환합니다."""
        return cls.DEEPLINK_TEMPLATES.get(template_key, cls.DEEPLINK_TEMPLATES['home'])
    
    @classmethod
    def get_message_template(cls, notification_type: str, language: str = 'ko') -> str:
        """메시지 템플릿을 반환합니다."""
        templates = cls.MESSAGE_TEMPLATES.get(language, cls.MESSAGE_TEMPLATES['ko'])
        return templates.get(notification_type, '{summary}')
    
    @classmethod
    def get_title_template(cls, notification_type: str, language: str = 'ko') -> str:
        """타이틀 템플릿을 반환합니다."""
        templates = cls.TITLE_TEMPLATES.get(language, cls.TITLE_TEMPLATES['ko'])
        return templates.get(notification_type, '알림')


class NotificationFeatureFlags:
    """알림 도메인 기능 플래그"""
    
    # 점진적 롤아웃을 위한 기능 플래그
    ENABLE_NEW_HANDLER_SYSTEM = True
    ENABLE_TEMPLATE_SYSTEM = True
    ENABLE_ADVANCED_FORMATTING = True
    ENABLE_ANALYTICS = True
    
    # 실험적 기능
    ENABLE_SMART_BATCHING = False
    ENABLE_ML_BASED_PRIORITIZATION = False
    
    @classmethod
    def is_enabled(cls, feature: str) -> bool:
        """기능이 활성화되어 있는지 확인합니다."""
        return getattr(cls, feature, False)
