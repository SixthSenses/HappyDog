# app/api/comments/services/notification_service.py
"""
댓글 관련 알림 생성을 담당하는 서비스
- 게시글 작성자 알림
- 멘션 사용자 알림  
- 댓글 좋아요 알림
- 중앙화된 알림 서비스와의 연동
"""
import logging
import re
from typing import Dict, Any, List, Optional
from app.utils.text_utils import truncate_summary
from flask import current_app

from app.models.notification import NotificationType


class CommentNotificationService:
    """
    댓글 관련 알림 생성을 담당하는 서비스
    """
    def __init__(self):
        pass

    def init_app(self, app):
        self.app = app

    # _sanitize_summary 제거: truncate_summary 사용

    def notify_post_author(self, notification_data: Dict[str, Any]) -> None:
        """
        게시글 작성자에게 새 댓글 알림을 생성합니다.
        """
        try:
            comment_id = notification_data.get('comment_id')
            post_id = notification_data.get('post_id')
            comment_author_id = notification_data.get('comment_author_id')
            post_author_id = notification_data.get('post_author_id')
            comment_text = notification_data.get('comment_text', '')

            if not all([comment_id, post_id, comment_author_id, post_author_id]):
                logging.warning("게시글 작성자 알림에 필수 데이터가 없습니다.")
                return

            notification_service = current_app.services.get('notifications')
            if notification_service:
                notification_service.create_notification(
                    recipient_id=post_author_id,
                    sender_id=comment_author_id,
                    n_type=NotificationType.COMMENT,
                    target_id=post_id,
                    target_summary=truncate_summary(comment_text)
                )
                logging.debug(f"게시글 작성자 알림 생성 완료 (post_author: {post_author_id}, comment: {comment_id})")

        except Exception as e:
            logging.error(f"게시글 작성자 알림 생성 실패: {e}", exc_info=True)

    def notify_mentioned_users(self, notification_data: Dict[str, Any]) -> None:
        """
        멘션된 사용자들에게 멘션 알림을 생성합니다.
        """
        try:
            comment_id = notification_data.get('comment_id')
            post_id = notification_data.get('post_id')
            comment_author_id = notification_data.get('comment_author_id')
            mentioned_user_ids = notification_data.get('mentioned_user_ids', [])
            comment_text = notification_data.get('comment_text', '')

            if not all([comment_id, post_id, comment_author_id]) or not mentioned_user_ids:
                logging.warning("멘션 알림에 필수 데이터가 없습니다.")
                return

            notification_service = current_app.services.get('notifications')
            if not notification_service:
                logging.warning("NotificationService를 찾을 수 없습니다.")
                return

            created_count = 0
            for user_id in mentioned_user_ids:
                try:
                    notification_service.create_notification(
                        recipient_id=user_id,
                        sender_id=comment_author_id,
                        n_type=NotificationType.MENTION,
                        target_id=post_id,
                        target_summary=truncate_summary(comment_text)
                    )
                    created_count += 1
                except Exception as e:
                    logging.error(f"개별 멘션 알림 생성 실패 (user: {user_id}): {e}")

            logging.debug(f"멘션 알림 생성 완료 (comment: {comment_id}, 생성된 알림: {created_count}개)")

        except Exception as e:
            logging.error(f"멘션 알림 생성 실패: {e}", exc_info=True)

    def notify_comment_liked(self, notification_data: Dict[str, Any]) -> None:
        """
        댓글 좋아요 알림을 생성합니다.
        """
        try:
            comment_id = notification_data.get('comment_id')
            comment_author_id = notification_data.get('comment_author_id')
            liker_id = notification_data.get('liker_id')
            comment_text = notification_data.get('comment_text', '')

            if not all([comment_id, comment_author_id, liker_id]):
                logging.warning("댓글 좋아요 알림에 필수 데이터가 없습니다.")
                return

            notification_service = current_app.services.get('notifications')
            if notification_service:
                notification_service.create_notification(
                    recipient_id=comment_author_id,
                    sender_id=liker_id,
                    n_type=NotificationType.COMMENT_LIKE,
                    target_id=comment_id,
                    target_summary=truncate_summary(comment_text)
                )
                logging.debug(f"댓글 좋아요 알림 생성 완료 (comment: {comment_id}, recipient: {comment_author_id})")

        except Exception as e:
            logging.error(f"댓글 좋아요 알림 생성 실패: {e}", exc_info=True)

    def create_comment_notification(self, notification_type: str, data: Dict[str, Any]) -> bool:
        """
        일반적인 댓글 관련 알림을 생성하는 헬퍼 메서드입니다.
        """
        try:
            notification_service = current_app.services.get('notifications')
            if not notification_service:
                return False

            # notification_type에 따라 적절한 처리
            if notification_type == "COMMENT":
                self.notify_post_author(data)
            elif notification_type == "MENTION":
                self.notify_mentioned_users(data)
            elif notification_type == "COMMENT_LIKE":
                self.notify_comment_liked(data)
            else:
                logging.warning(f"지원하지 않는 알림 타입: {notification_type}")
                return False

            return True

        except Exception as e:
            logging.error(f"댓글 알림 생성 실패 (type: {notification_type}): {e}", exc_info=True)
            return False

    def get_notification_statistics(self) -> Dict[str, int]:
        """
        댓글 관련 알림 통계를 반환합니다.
        디버깅이나 모니터링 목적으로 사용할 수 있습니다.
        """
        # 향후 알림 통계가 필요한 경우 구현
        return {
            'comment_notifications': 0,
            'mention_notifications': 0,
            'comment_like_notifications': 0
        }
