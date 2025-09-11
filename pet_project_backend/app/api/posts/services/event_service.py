# app/api/posts/services/event_service.py
"""
게시글 관련 이벤트 처리를 담당하는 서비스
- 게시글 생성/삭제/좋아요 이벤트 처리
- 알림 서비스와의 연동
- 사용자 통계 업데이트
"""
import logging
from typing import Dict, Any, Optional
from flask import current_app

from app.models.notification import NotificationType


class PostEventService:
    """
    게시글 관련 이벤트를 처리하는 서비스
    """
    def __init__(self):
        pass

    def init_app(self, app):
        self.app = app

    def handle_post_created(self, post_data: Dict[str, Any]) -> None:
        """
        게시글 생성 이벤트를 처리합니다.
        - 사용자 통계 업데이트
        - 필요시 다른 후속 처리
        """
        try:
            user_id = post_data.get('author', {}).get('user_id')
            if not user_id:
                logging.warning("게시글 생성 이벤트에 사용자 ID가 없습니다.")
                return

            # UserStatsService를 통해 포스트 수 캐시 업데이트
            user_stats_service = current_app.services.get('user_stats')
            if user_stats_service:
                user_stats_service.update_post_count_cache(user_id, increment=1)
                
            logging.info(f"게시글 생성 이벤트 처리 완료 (post_id: {post_data.get('post_id')}, user_id: {user_id})")
        except Exception as e:
            logging.error(f"게시글 생성 이벤트 처리 실패: {e}", exc_info=True)

    def handle_post_liked(self, like_data: Dict[str, Any]) -> None:
        """
        게시글 좋아요 이벤트를 처리합니다.
        - 좋아요 알림 생성
        """
        try:
            user_id = like_data.get('user_id')
            post_id = like_data.get('post_id')
            post_author_id = like_data.get('post_author_id')
            action = like_data.get('action')

            if not all([user_id, post_id, post_author_id, action]):
                logging.warning("좋아요 이벤트 데이터가 불완전합니다.")
                return

            # 자신의 게시글에는 알림을 보내지 않음
            if post_author_id == user_id:
                return

            # 좋아요일 때만 알림 생성
            if action == 'liked':
                notification_service = current_app.services.get('notifications')
                if notification_service:
                    notification_service.create_notification(
                        recipient_id=post_author_id,
                        sender_id=user_id,
                        n_type=NotificationType.POST_LIKE,
                        target_id=post_id
                    )
                    logging.info(f"좋아요 알림 생성 완료 (post_id: {post_id}, recipient: {post_author_id})")
        except Exception as e:
            logging.error(f"좋아요 이벤트 처리 실패: {e}", exc_info=True)

    def handle_post_deleted(self, post_data: Dict[str, Any]) -> None:
        """
        게시글 삭제 이벤트를 처리합니다.
        - 사용자 통계 업데이트
        - 스토리지 정리는 PostStorageService에서 별도 처리
        """
        try:
            user_id = post_data.get('author', {}).get('user_id')
            if not user_id:
                logging.warning("게시글 삭제 이벤트에 사용자 ID가 없습니다.")
                return

            # UserStatsService를 통해 포스트 수 캐시 업데이트
            user_stats_service = current_app.services.get('user_stats')
            if user_stats_service:
                user_stats_service.update_post_count_cache(user_id, increment=-1)
                
            logging.info(f"게시글 삭제 이벤트 처리 완료 (post_id: {post_data.get('post_id')}, user_id: {user_id})")
        except Exception as e:
            logging.error(f"게시글 삭제 이벤트 처리 실패: {e}", exc_info=True)
