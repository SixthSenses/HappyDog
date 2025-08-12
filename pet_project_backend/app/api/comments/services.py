# app/api/comments/services.py
import logging
import re
import uuid
from datetime import datetime
from firebase_admin import firestore
from dataclasses import asdict
from typing import Optional, Dict, Any, List, Tuple

from app.models.comment import Comment
from app.models.notification import NotificationType
from app.services.notification_service import notification_service

class CommentService:
    """
    댓글 관련 비즈니스 로직을 담당하는 서비스 클래스.
    - 댓글 CRUD, 좋아요, 멘션 및 알림 생성 로직을 포함합니다.
    """
    def __init__(self):
        """서비스 초기화 시 Firestore 클라이언트 및 컬렉션 참조를 설정합니다."""
        self.db = firestore.client()
        self.comments_ref = self.db.collection('comments')
        self.posts_ref = self.db.collection('posts')
        self.users_ref = self.db.collection('users')
        self.likes_ref = self.db.collection('likes')

    def _extract_mentions(self, text: str, sender_id: str) -> List[str]:
        """
        텍스트에서 '@닉네임' 형식의 멘션을 추출하여 user_id 리스트를 반환합니다.
        - Firestore 'in' 쿼리 제약(최대 30개)을 고려하여, 실제 프로덕션에서는
          닉네임 목록을 분할하여 처리하거나 다른 검색 방법을 고려해야 할 수 있습니다.
        """
        mention_pattern = r'@(\w+)'
        mentioned_nicknames = set(re.findall(mention_pattern, text))
        if not mentioned_nicknames:
            return []
        
        mentioned_user_ids = []
        for nickname in mentioned_nicknames:
            query = self.users_ref.where('nickname', '==', nickname).limit(1).stream()
            user_doc = next(query, None)
            # 자기 자신을 멘션한 경우는 알림에서 제외합니다.
            if user_doc and user_doc.id != sender_id:
                mentioned_user_ids.append(user_doc.id)
        return mentioned_user_ids

    @firestore.transactional
    def _create_comment_transaction(self, transaction, post_id: str, author_info: Dict[str, Any], text: str) -> Tuple[Comment, Dict]:
        """트랜잭션 내에서 댓글을 생성하고 게시물의 댓글 수를 1 증가시킵니다."""
        post_ref = self.posts_ref.document(post_id)
        post_snapshot = post_ref.get(transaction=transaction)
        if not post_snapshot.exists:
            raise ValueError("댓글을 작성할 게시물이 존재하지 않습니다.")
        
        comment_id = str(uuid.uuid4())
        new_comment = Comment(comment_id=comment_id, post_id=post_id, author=author_info, text=text)
        
        transaction.set(self.comments_ref.document(comment_id), asdict(new_comment))
        transaction.update(post_ref, {'comment_count': firestore.Increment(1)})

        return new_comment, post_snapshot.to_dict()

    def create_comment(self, post_id: str, author_id: str, text: str) -> Dict[str, Any]:
        """새로운 댓글을 생성하고 관련 알림을 트리거합니다."""
        author_doc = self.users_ref.document(author_id).get()
        if not author_doc.exists:
            raise ValueError("댓글 작성자를 찾을 수 없습니다.")
        
        author_info = author_doc.to_dict()
        author_data = {"user_id": author_id, "nickname": author_info.get("nickname"), "profile_image_url": author_info.get("profile_image_url")}
        
        transaction = self.db.transaction()
        new_comment, post_data = self._create_comment_transaction(transaction, post_id, author_data, text)

        # 트랜잭션이 성공적으로 커밋된 후에만 알림을 생성합니다.
        post_author_id = post_data.get('author', {}).get('user_id')
        notification_service.create_notification(
            recipient_id=post_author_id, sender_id=author_id,
            n_type=NotificationType.COMMENT, target_id=post_id, target_summary=text[:50]
        )
        
        mentioned_user_ids = self._extract_mentions(text, author_id)
        for user_id in mentioned_user_ids:
            notification_service.create_notification(
                recipient_id=user_id, sender_id=author_id,
                n_type=NotificationType.MENTION, target_id=post_id, target_summary=text[:50]
            )
        return asdict(new_comment)

    def get_comments_for_post(self, post_id: str, current_user_id: Optional[str], limit: int, cursor: Optional[str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """특정 게시글의 댓글 목록을 페이지네이션으로 조회합니다."""
        query = self.comments_ref.where('post_id', '==', post_id).order_by("created_at")
        if cursor:
            cursor_doc = self.comments_ref.document(cursor).get()
            if cursor_doc.exists:
                query = query.start_after(cursor_doc)
        
        docs = query.limit(limit).stream()
        comments = [doc.to_dict() for doc in docs]
        
        last_doc_id = comments[-1]['comment_id'] if comments else None
        
        # 로그인한 경우, 각 댓글에 대한 좋아요 여부를 확인합니다.
        if current_user_id:
            liked_comment_ids = self._check_likes_for_comments(current_user_id, [c['comment_id'] for c in comments])
            for comment in comments:
                comment['is_liked'] = comment['comment_id'] in liked_comment_ids
                
        return comments, last_doc_id

    @firestore.transactional
    def _delete_comment_transaction(self, transaction, comment_id: str, user_id: str):
        """트랜잭션 내에서 댓글을 삭제하고 게시물의 댓글 수를 1 감소시킵니다."""
        comment_ref = self.comments_ref.document(comment_id)
        comment_doc = comment_ref.get(transaction=transaction)

        if not comment_doc.exists:
            raise ValueError("삭제할 댓글이 없습니다.")
        comment_data = comment_doc.to_dict()
        if comment_data.get('author', {}).get('user_id') != user_id:
            raise PermissionError("댓글을 삭제할 권한이 없습니다.")

        post_ref = self.posts_ref.document(comment_data.get('post_id'))
        transaction.delete(comment_ref)
        transaction.update(post_ref, {'comment_count': firestore.Increment(-1)})

    def delete_comment(self, comment_id: str, user_id: str) -> None:
        """댓글을 삭제합니다."""
        try:
            transaction = self.db.transaction()
            self._delete_comment_transaction(transaction, comment_id, user_id)
        except (ValueError, PermissionError) as e:
            logging.warning(f"댓글 삭제 거부 (comment_id: {comment_id}): {e}")
            raise e
        except Exception as e:
            logging.error(f"댓글 삭제 실패 (comment_id: {comment_id}): {e}", exc_info=True)
            raise

    @firestore.transactional
    def _toggle_like_comment_transaction(self, transaction, user_id: str, comment_id: str) -> Tuple[bool, Optional[Dict]]:
        """트랜잭션 내에서 댓글 좋아요 상태를 토글합니다."""
        like_id = f"comment_{user_id}_{comment_id}"
        like_ref = self.likes_ref.document(like_id)
        comment_ref = self.comments_ref.document(comment_id)
        
        like_doc = like_ref.get(transaction=transaction)
        comment_doc = comment_ref.get(transaction=transaction)

        if not comment_doc.exists:
            raise ValueError("좋아요를 누를 댓글을 찾을 수 없습니다.")

        if like_doc.exists:
            transaction.delete(like_ref)
            transaction.update(comment_ref, {'like_count': firestore.Increment(-1)})
            return False, comment_doc.to_dict()
        else:
            transaction.set(like_ref, {'user_id': user_id, 'comment_id': comment_id, 'created_at': datetime.utcnow()})
            transaction.update(comment_ref, {'like_count': firestore.Increment(1)})
            return True, comment_doc.to_dict()

    def toggle_comment_like(self, user_id: str, comment_id: str) -> bool:
        """댓글 좋아요를 누르거나 취소하고, 필요 시 알림을 생성합니다."""
        try:
            transaction = self.db.transaction()
            is_liked, comment_data = self._toggle_like_comment_transaction(transaction, user_id, comment_id)
            
            if is_liked:
                comment_author_id = comment_data.get('author', {}).get('user_id')
                notification_service.create_notification(
                    recipient_id=comment_author_id, sender_id=user_id,
                    n_type=NotificationType.COMMENT_LIKE, target_id=comment_id,
                    target_summary=comment_data.get("text", "")[:50]
                )
            return True
        except Exception as e:
            logging.error(f"댓글 좋아요 토글 실패 (user_id: {user_id}, comment_id: {comment_id}): {e}", exc_info=True)
            if isinstance(e, ValueError): raise e
            return False

    def _check_likes_for_comments(self, user_id: str, comment_ids: List[str]) -> set:
        """주어진 댓글 ID 목록에 대해 사용자의 좋아요 여부를 일괄 확인합니다."""
        liked_comment_ids = set()
        # Firestore 'in' 쿼리는 최대 30개까지 가능하므로, 30개씩 나눠서 처리합니다.
        for i in range(0, len(comment_ids), 30):
            chunk_ids = comment_ids[i:i+30]
            like_doc_ids = [f"comment_{user_id}_{cid}" for cid in chunk_ids]
            
            like_docs = self.likes_ref.where('__name__', 'in', like_doc_ids).stream()
            for doc in like_docs:
                liked_comment_ids.add(doc.to_dict().get('comment_id'))
        return liked_comment_ids

# 서비스 인스턴스는 app/__init__.py에서 생성 및 주입됩니다.
comment_service: Optional[CommentService] = None