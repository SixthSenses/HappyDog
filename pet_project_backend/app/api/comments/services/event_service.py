# app/api/comments/services/event_service.py
"""
댓글 관련 이벤트 처리를 담당하는 서비스
- 댓글 생성/수정/삭제 이벤트 처리
- 멘션 변경 감지 및 처리
- 다른 서비스들과의 이벤트 기반 통신
"""
import logging
import re
from typing import Dict, Any, List, Optional
from app.utils.text_utils import truncate_summary
from flask import current_app


class CommentEventService:
    """
    댓글 관련 이벤트를 처리하는 서비스
    """
    def __init__(self):
        pass

    def init_app(self, app):
        self.app = app

    # _sanitize_summary 제거: truncate_summary 사용

    def handle_comment_created(self, comment_data: Dict[str, Any], mention_data: Dict[str, Any]) -> None:
        """
        댓글 생성 이벤트를 처리합니다.
        - 게시글 작성자에게 댓글 알림
        - 멘션된 사용자들에게 멘션 알림
        - 중복 알림 방지 로직 포함
        """
        try:
            author_id = comment_data.get('author', {}).get('user_id')
            post_id = comment_data.get('post_id')
            comment_text = comment_data.get('text', '')
            post_data = comment_data.get('post_data', {})
            
            if not all([author_id, post_id]):
                logging.warning("댓글 생성 이벤트에 필수 데이터가 없습니다.")
                return

            comment_notification_service = current_app.services.get('comment_notifications')
            if not comment_notification_service:
                logging.warning("CommentNotificationService를 찾을 수 없습니다.")
                return

            # 1. 게시글 작성자에게 댓글 알림
            post_author_id = post_data.get('author', {}).get('user_id')
            if post_author_id and post_author_id != author_id:
                comment_notification_service.notify_post_author({
                    'comment_id': comment_data.get('comment_id'),
                    'post_id': post_id,
                    'comment_author_id': author_id,
                    'post_author_id': post_author_id,
                    'comment_text': comment_text
                })

            # 2. 멘션된 사용자들에게 멘션 알림 (중복 방지)
            mentioned_user_ids = mention_data.get('mentioned_user_ids', [])
            if mentioned_user_ids:
                # 이미 댓글 알림을 받은 게시글 작성자는 멘션 알림에서 제외
                filtered_mentions = [
                    user_id for user_id in mentioned_user_ids 
                    if user_id != post_author_id or post_author_id == author_id
                ]
                
                if filtered_mentions:
                    comment_notification_service.notify_mentioned_users({
                        'comment_id': comment_data.get('comment_id'),
                        'post_id': post_id,
                        'comment_author_id': author_id,
                        'mentioned_user_ids': filtered_mentions,
                        'comment_text': comment_text
                    })

            logging.info(f"댓글 생성 이벤트 처리 완료 (comment_id: {comment_data.get('comment_id')})")
            
        except Exception as e:
            logging.error(f"댓글 생성 이벤트 처리 실패: {e}", exc_info=True)

    def handle_comment_updated(self, comment_data: Dict[str, Any], old_mentions: List[str], new_mentions: List[str]) -> None:
        """
        댓글 수정 이벤트를 처리합니다.
        - 새로 추가된 멘션에 대해서만 알림 생성
        - 제거된 멘션에 대해서는 특별한 처리 없음 (기존 알림 유지)
        """
        try:
            # 새로 추가된 멘션만 추출
            added_mentions = list(set(new_mentions) - set(old_mentions))
            if not added_mentions:
                return

            author_id = comment_data.get('author', {}).get('user_id')
            post_id = comment_data.get('post_id')
            comment_text = comment_data.get('text', '')

            if not all([author_id, post_id]):
                logging.warning("댓글 수정 이벤트에 필수 데이터가 없습니다.")
                return

            comment_notification_service = current_app.services.get('comment_notifications')
            if comment_notification_service:
                comment_notification_service.notify_mentioned_users({
                    'comment_id': comment_data.get('comment_id'),
                    'post_id': post_id,
                    'comment_author_id': author_id,
                    'mentioned_user_ids': added_mentions,
                    'comment_text': comment_text
                })

            logging.info(f"댓글 수정 이벤트 처리 완료 (comment_id: {comment_data.get('comment_id')}, 새 멘션: {len(added_mentions)}개)")
            
        except Exception as e:
            logging.error(f"댓글 수정 이벤트 처리 실패: {e}", exc_info=True)

    def handle_comment_liked(self, like_event_data: Dict[str, Any]) -> None:
        """
        댓글 좋아요 이벤트를 처리합니다.
        - 댓글 작성자에게 좋아요 알림
        """
        try:
            action = like_event_data.get('action')
            user_id = like_event_data.get('user_id')
            comment_id = like_event_data.get('comment_id')
            comment_data = like_event_data.get('comment_data', {})

            if action != 'liked':
                return  # 좋아요 취소는 알림 없음

            comment_author_id = comment_data.get('author', {}).get('user_id')
            if not comment_author_id or comment_author_id == user_id:
                return  # 자신의 댓글에는 알림 없음

            comment_text = comment_data.get('text', '')

            comment_notification_service = current_app.services.get('comment_notifications')
            if comment_notification_service:
                comment_notification_service.notify_comment_liked({
                    'comment_id': comment_id,
                    'comment_author_id': comment_author_id,
                    'liker_id': user_id,
                    'comment_text': comment_text
                })

            logging.info(f"댓글 좋아요 이벤트 처리 완료 (comment_id: {comment_id})")
            
        except Exception as e:
            logging.error(f"댓글 좋아요 이벤트 처리 실패: {e}", exc_info=True)

    def handle_comment_deleted(self, comment_data: Dict[str, Any]) -> None:
        """
        댓글 삭제 이벤트를 처리합니다.
        현재는 특별한 처리가 없지만, 향후 확장 가능한 구조입니다.
        """
        try:
            # 향후 확장 가능:
            # - 관련 알림 정리
            # - 통계 업데이트
            # - 캐시 무효화 등
            
            comment_id = comment_data.get('comment_id')
            logging.info(f"댓글 삭제 이벤트 처리 완료 (comment_id: {comment_id})")
            
        except Exception as e:
            logging.error(f"댓글 삭제 이벤트 처리 실패: {e}", exc_info=True)
