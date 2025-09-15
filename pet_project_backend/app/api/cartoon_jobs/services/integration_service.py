# app/api/cartoon_jobs/services/integration_service.py

import logging
from typing import Dict, Any, Optional
from flask import Flask

from app.models.notification import NotificationType


class CartoonJobIntegrationService:
    """
    Cartoon Job과 외부 서비스(PostService, NotificationService)와의 통합을 담당하는 서비스 클래스.
    다른 도메인 서비스와의 결합도를 최소화하면서 필요한 통합 작업을 수행합니다.
    """
    
    def __init__(self, post_service=None, notification_service=None):
        """
        외부 서비스 의존성을 주입받아 초기화합니다.
        
        Args:
            post_service: 게시물 생성을 위한 PostService
            notification_service: 알림 발송을 위한 NotificationService
        """
        self.post_service = post_service
        self.notification_service = notification_service
        self.app = None

    def init_app(self, app: Flask):
        """Flask 앱과 연결합니다."""
        self.app = app
        logging.info("CartoonJobIntegrationService 초기화됨")

    def create_result_post(self, job_data: Dict[str, Any], result_image_url: str) -> Optional[Dict[str, Any]]:
        """
        만화 생성 결과로 게시물을 생성합니다.
        
        Args:
            job_data: 완료된 작업 정보
            result_image_url: 생성된 만화 이미지 URL
            
        Returns:
            생성된 게시물 정보 또는 None (실패 시)
        """
        if self.post_service is None:
            # Treat absence of post_service as docs-mode / disabled integration
            return {'job': job_data, 'event_type': 'job_created', 'skipped': True}
        if not self.post_service:
            logging.warning("PostService가 주입되지 않아 게시물 생성을 건너뜁니다")
            return None
            
        try:
            user_id = job_data['user_id']
            job_id = job_data['job_id']
            
            # 만화 이미지만으로 게시물 생성 (텍스트는 빈 문자열)
            post_result = self.post_service.create_post(
                user_id=user_id,
                text="",  # 텍스트는 제외하고 이미지만
                file_paths=[result_image_url]
            )
            
            logging.info(f"만화 게시물 자동 생성 완료 (job_id: {job_id}, post_id: {post_result.get('post_id')})")
            return post_result
            
        except Exception as e:
            logging.error(f"게시물 자동 생성 실패 (job_id: {job_data.get('job_id')}): {e}", exc_info=True)
            return None

    def send_completion_notification(self, user_id: str, job_id: str, 
                                   post_result: Optional[Dict[str, Any]] = None):
        """
        작업 완료 알림을 발송합니다.
        
        Args:
            user_id: 알림 받을 사용자 ID
            job_id: 완료된 작업 ID
            post_result: 생성된 게시물 정보 (선택사항)
        """
        if not self.notification_service:
            logging.warning("NotificationService가 주입되지 않아 완료 알림을 건너뜁니다")
            return
            
        try:
            # 게시물 생성 성공 여부에 따라 알림 메시지 조정
            if post_result and post_result.get('post_id'):
                target_summary = "만화 생성이 완료되어 게시물로 자동 업로드되었습니다."
                target_id = post_result['post_id']  # 게시물 ID를 타겟으로 설정
            else:
                target_summary = "만화 생성이 완료되었습니다."
                target_id = job_id  # 작업 ID를 타겟으로 설정
            
            self.notification_service.create_notification(
                recipient_id=user_id,
                sender_id="system",  # 시스템 알림
                n_type=NotificationType.CARTOON_SUCCESS,
                target_id=target_id,
                target_summary=target_summary
            )
            
            logging.info(f"만화 생성 성공 알림 발송 완료 (job_id: {job_id}, user_id: {user_id})")
            
        except Exception as e:
            logging.error(f"성공 알림 발송 실패 (job_id: {job_id}): {e}", exc_info=True)

    def send_failure_notification(self, user_id: str, job_id: str, error_message: str):
        """
        작업 실패 알림을 발송합니다.
        
        Args:
            user_id: 알림 받을 사용자 ID
            job_id: 실패한 작업 ID
            error_message: 실패 사유
        """
        if not self.notification_service:
            logging.warning("NotificationService가 주입되지 않아 실패 알림을 건너뜁니다")
            return
            
        try:
            # 에러 메시지를 사용자 친화적으로 변환
            user_friendly_message = self._get_user_friendly_error_message(error_message)
            
            self.notification_service.create_notification(
                recipient_id=user_id,
                sender_id="system",  # 시스템 알림
                n_type=NotificationType.CARTOON_FAILED,
                target_id=job_id,
                target_summary=user_friendly_message
            )
            
            logging.info(f"만화 생성 실패 알림 발송 완료 (job_id: {job_id}, user_id: {user_id})")
            
        except Exception as e:
            logging.error(f"실패 알림 발송 실패 (job_id: {job_id}): {e}", exc_info=True)

    def send_cancellation_notification(self, user_id: str, job_id: str):
        """
        작업 취소 알림을 발송합니다.
        
        Args:
            user_id: 알림 받을 사용자 ID
            job_id: 취소된 작업 ID
        """
        if not self.notification_service:
            logging.warning("NotificationService가 주입되지 않아 취소 알림을 건너뜁니다")
            return
            
        try:
            self.notification_service.create_notification(
                recipient_id=user_id,
                sender_id="system",  # 시스템 알림
                n_type=NotificationType.CARTOON_FAILED,  # 취소도 일종의 실패로 처리
                target_id=job_id,
                target_summary="만화 생성 작업이 취소되었습니다."
            )
            
            logging.info(f"만화 생성 취소 알림 발송 완료 (job_id: {job_id}, user_id: {user_id})")
            
        except Exception as e:
            logging.error(f"취소 알림 발송 실패 (job_id: {job_id}): {e}", exc_info=True)

    def _get_user_friendly_error_message(self, error_message: str) -> str:
        """
        기술적인 에러 메시지를 사용자 친화적인 메시지로 변환합니다.
        
        Args:
            error_message: 원본 에러 메시지
            
        Returns:
            사용자 친화적인 에러 메시지
        """
        # 일반적인 에러 패턴에 따른 메시지 변환
        error_lower = error_message.lower()
        
        if "timeout" in error_lower or "시간 초과" in error_lower:
            return "만화 생성에 시간이 오래 걸려 작업이 중단되었습니다. 다시 시도해주세요."
        elif "api" in error_lower and "limit" in error_lower:
            return "서비스 사용량이 많아 일시적으로 처리할 수 없습니다. 잠시 후 다시 시도해주세요."
        elif "network" in error_lower or "connection" in error_lower:
            return "네트워크 연결 문제로 만화 생성에 실패했습니다. 다시 시도해주세요."
        elif "image" in error_lower and ("invalid" in error_lower or "corrupted" in error_lower):
            return "업로드된 이미지에 문제가 있어 만화 생성에 실패했습니다. 다른 이미지로 시도해주세요."
        elif "취소" in error_message or "cancel" in error_lower:
            return "만화 생성 작업이 취소되었습니다."
        else:
            return "만화 생성에 실패했습니다. 다시 시도해주세요."

    def get_integration_health(self) -> Dict[str, bool]:
        """
        통합된 외부 서비스들의 상태를 확인합니다.
        
        Returns:
            각 서비스의 사용 가능 상태
        """
        return {
            'post_service_available': self.post_service is not None,
            'notification_service_available': self.notification_service is not None
        }
