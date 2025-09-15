# app/api/posts/services/like_service.py
"""
게시글 좋아요 관련 작업을 담당하는 서비스
- 좋아요/좋아요 취소 로직
- 좋아요 상태 확인 및 집계
- 알림 트리거는 별도 이벤트 서비스에서 처리
"""
import logging
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

from firebase_admin import firestore


class PostLikeService:
    """Post like management service.

    In DOCS_MODE Firestore is not initialized; methods become no-ops returning
    neutral placeholder values to allow application bootstrap.
    """
    def __init__(self, db_client=None):
        self.db = db_client
        self.posts_ref = self.db.collection('posts') if self.db else None
        self.likes_ref = self.db.collection('likes') if self.db else None
        if self.db is None:
            logging.info("PostLikeService initialized without Firestore client (docs mode or disabled persistence)")

    def like_post(self, user_id: str, post_id: str) -> Optional[Dict[str, Any]]:
        """
        게시글에 좋아요를 추가합니다.
        반환값: 성공시 좋아요 이벤트 데이터, 실패시 None
        """
        if self.db is None:
            return None
        transaction = self.db.transaction()

        @firestore.transactional
        def _add_like_in_transaction(transaction, user_id, post_id):
            like_id = f"post_{user_id}_{post_id}"
            like_ref = self.likes_ref.document(like_id)
            post_ref = self.posts_ref.document(post_id)
            
            like_doc = like_ref.get(transaction=transaction)
            post_doc = post_ref.get(transaction=transaction)

            if not post_doc.exists:
                raise ValueError("게시글을 찾을 수 없습니다.")
            
            if like_doc.exists:
                return None  # 이미 좋아요 상태
            
            transaction.set(like_ref, {
                'user_id': user_id, 
                'post_id': post_id, 
                'created_at': datetime.utcnow()
            })
            transaction.update(post_ref, {'like_count': firestore.Increment(1)})
            return {
                'user_id': user_id,
                'post_id': post_id,
                'post_author_id': post_doc.to_dict().get('author', {}).get('user_id'),
                'action': 'liked'
            }

        try:
            return _add_like_in_transaction(transaction, user_id, post_id)
        except Exception as e:
            logging.error(f"게시글 좋아요 추가 실패: {e}", exc_info=True)
            if isinstance(e, ValueError): 
                raise e
            return None

    def unlike_post(self, user_id: str, post_id: str) -> Optional[Dict[str, Any]]:
        """
        게시글에서 좋아요를 제거합니다.
        반환값: 성공시 좋아요 취소 이벤트 데이터, 실패시 None
        """
        if self.db is None:
            return None
        transaction = self.db.transaction()

        @firestore.transactional
        def _remove_like_in_transaction(transaction, user_id, post_id):
            like_id = f"post_{user_id}_{post_id}"
            like_ref = self.likes_ref.document(like_id)
            post_ref = self.posts_ref.document(post_id)
            
            like_doc = like_ref.get(transaction=transaction)
            post_doc = post_ref.get(transaction=transaction)

            if not post_doc.exists:
                raise ValueError("게시글을 찾을 수 없습니다.")
            
            if not like_doc.exists:
                return None  # 이미 좋아요 취소 상태
            
            transaction.delete(like_ref)
            transaction.update(post_ref, {'like_count': firestore.Increment(-1)})
            return {
                'user_id': user_id,
                'post_id': post_id,
                'post_author_id': post_doc.to_dict().get('author', {}).get('user_id'),
                'action': 'unliked'
            }

        try:
            return _remove_like_in_transaction(transaction, user_id, post_id)
        except Exception as e:
            logging.error(f"게시글 좋아요 제거 실패: {e}", exc_info=True)
            if isinstance(e, ValueError): 
                raise e
            return None

    def toggle_post_like(self, user_id: str, post_id: str) -> Optional[Dict[str, Any]]:
        """
        게시글 좋아요를 토글합니다.
        반환값: 좋아요 이벤트 데이터 또는 None
        """
        # 현재 좋아요 상태 확인
        if self.is_user_liked_post(user_id, post_id):
            return self.unlike_post(user_id, post_id)
        else:
            return self.like_post(user_id, post_id)

    def is_user_liked_post(self, user_id: Optional[str], post_id: str) -> bool:
        """특정 게시물에 대한 사용자의 좋아요 여부를 확인합니다."""
        if not user_id or self.db is None:
            return False
        like_id = f"post_{user_id}_{post_id}"
        like_doc = self.likes_ref.document(like_id).get()
        return like_doc.exists

    def check_likes_for_posts(self, user_id: Optional[str], post_ids: List[str]) -> set:
        """주어진 게시물 ID 목록에 대한 사용자의 좋아요 여부를 일괄 확인합니다."""
        if not user_id or not post_ids or self.db is None:
            return set()
        
        liked_post_ids = set()
        # Firestore 'in' 쿼리는 최대 30개까지 가능하므로, 30개씩 나눠서 처리합니다.
        for i in range(0, len(post_ids), 30):
            chunk_ids = post_ids[i:i+30]
            like_doc_ids = [f"post_{user_id}_{pid}" for pid in chunk_ids]
            
            like_docs = self.likes_ref.where('__name__', 'in', like_doc_ids).stream()
            for doc in like_docs:
                liked_post_ids.add(doc.to_dict().get('post_id'))
        return liked_post_ids

    def get_post_like_count(self, post_id: str) -> int:
        """특정 게시글의 좋아요 개수를 반환합니다."""
        if self.db is None:
            return 0
        try:
            post_doc = self.posts_ref.document(post_id).get()
            if not post_doc.exists:
                return 0
            return post_doc.to_dict().get('like_count', 0)
        except Exception as e:
            logging.error(f"게시글 좋아요 수 조회 실패 (post_id: {post_id}): {e}")
            return 0
