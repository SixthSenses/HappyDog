# app/api/comments/services/comment_service.py
"""
핵심 댓글 CRUD 작업만을 담당하는 서비스
- 순수한 댓글 생성/조회/삭제 로직
- 알림이나 멘션 처리는 별도 서비스에서 처리
- 이벤트 데이터를 반환하여 다른 서비스에서 후속 처리 가능
"""
import logging
import uuid
from datetime import datetime
from firebase_admin import firestore
from dataclasses import asdict
from typing import Optional, Dict, Any, List, Tuple

from app.models.comment import Comment, CommentAuthor, CommentPetInfo
from app.utils import metrics


class CommentService:
    """
    댓글 CRUD 작업을 담당하는 핵심 서비스
    """
    def __init__(self):
        self.db = firestore.client()
        self.comments_ref = self.db.collection('comments')
        self.posts_ref = self.db.collection('posts')
        self.users_ref = self.db.collection('users')
        self.pets_ref = self.db.collection('pets')
        self.likes_ref = self.db.collection('likes')

    def create_comment(self, post_id: str, author_id: str, text: str) -> Dict[str, Any]:
        """
        새로운 댓글을 생성합니다 (순수한 CRUD 로직만).
        알림이나 멘션 처리는 별도 서비스에서 처리합니다.
        """
        author_doc = self.users_ref.document(author_id).get()
        if not author_doc.exists:
            raise ValueError("댓글 작성자를 찾을 수 없습니다.")

        # 작성자의 반려동물 정보도 가져오기
        pet_docs = self.pets_ref.where('user_id', '==', author_id).limit(1).get()
        if not pet_docs:
            raise ValueError("댓글 작성자의 반려동물 정보를 찾을 수 없습니다.")

        author_info = author_doc.to_dict()
        pet_data = pet_docs[0].to_dict()
        
        # 레거시 문서 보완: pet_id 필드 누락 시 문서 ID로 주입
        if not pet_data.get("pet_id"):
            pet_data["pet_id"] = pet_docs[0].id

        author = CommentAuthor(
            user_id=author_id, 
            nickname=author_info.get("nickname")
            # profile_image_url는 pet 정보에서 가져오도록 변경됨
        )
        
        pet = CommentPetInfo(
            pet_id=pet_data.get("pet_id"),
            name=pet_data.get("name"),
            breed=pet_data.get("breed"),
            profile_image_url=pet_data.get("profile_image_url")  # Pet 프로필 이미지 사용
        )

        transaction = self.db.transaction()
        
        @firestore.transactional
        def _update_in_transaction(transaction, post_id, author, pet, text):
            post_ref = self.posts_ref.document(post_id)
            post_snapshot = post_ref.get(transaction=transaction)
            if not post_snapshot.exists:
                raise ValueError("댓글을 작성할 게시물이 존재하지 않습니다.")

            comment_id = str(uuid.uuid4())
            new_comment = Comment(
                comment_id=comment_id, 
                post_id=post_id, 
                author=author,
                pet=pet,
                text=text
            )
            transaction.set(self.comments_ref.document(comment_id), asdict(new_comment))
            transaction.update(post_ref, {'comment_count': firestore.Increment(1)})
            return new_comment, post_snapshot.to_dict()

        new_comment, post_data = _update_in_transaction(transaction, post_id, author, pet, text)
        metrics.increment('comments.created')
        
        # 이벤트 처리를 위해 댓글과 게시글 데이터를 함께 반환
        comment_dict = asdict(new_comment)
        comment_dict['post_data'] = post_data  # 이벤트 서비스에서 사용
        return comment_dict

    def get_comments_for_post(self, post_id: str, limit: int, cursor: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        특정 게시글의 댓글 목록을 페이지네이션으로 조회합니다 (좋아요 정보 제외).
        좋아요 정보는 별도 서비스에서 추가됩니다.
        """
        query = self.comments_ref.where('post_id', '==', post_id).order_by("created_at")
        if cursor:
            cursor_doc = self.comments_ref.document(cursor).get()
            if cursor_doc.exists:
                query = query.start_after(cursor_doc)
        
        docs = query.limit(limit).stream()
        comments = [doc.to_dict() for doc in docs]
        last_doc_id = comments[-1]['comment_id'] if comments else None
        
        return comments, last_doc_id

    def get_comment_by_id(self, comment_id: str) -> Optional[Dict[str, Any]]:
        """특정 댓글의 정보를 조회합니다."""
        doc = self.comments_ref.document(comment_id).get()
        if not doc.exists:
            return None
        return doc.to_dict()

    def delete_comment(self, comment_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        댓글을 삭제하고 삭제된 댓글 정보를 반환합니다.
        이벤트 처리를 위해 삭제된 댓글 데이터를 반환합니다.
        """
        transaction = self.db.transaction()
        deleted_comment_data = None

        @firestore.transactional
        def _delete_in_transaction(transaction, comment_id, user_id):
            nonlocal deleted_comment_data
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
            
            deleted_comment_data = comment_data

        try:
            _delete_in_transaction(transaction, comment_id, user_id)
            return deleted_comment_data
        except Exception as e:
            logging.error(f"댓글 삭제 실패 (comment_id: {comment_id}): {e}", exc_info=True)
            raise

    def update_comment(self, comment_id: str, author_id: str, text: str) -> Optional[Dict[str, Any]]:
        """
        댓글 내용을 수정합니다.
        이벤트 처리를 위해 수정된 댓글 데이터를 반환합니다.
        """
        comment_ref = self.comments_ref.document(comment_id)
        doc = comment_ref.get()
        
        if not doc.exists:
            raise ValueError("수정할 댓글이 없습니다.")
        
        comment_data = doc.to_dict()
        if comment_data.get('author', {}).get('user_id') != author_id:
            raise PermissionError("댓글을 수정할 권한이 없습니다.")
        
        update_data = {
            "text": text, 
            "updated_at": datetime.utcnow()
        }
        comment_ref.update(update_data)
        
        # 업데이트된 댓글 데이터 반환
        updated_doc = comment_ref.get()
        return updated_doc.to_dict() if updated_doc.exists else None

    def toggle_comment_like(self, user_id: str, comment_id: str) -> Optional[Dict[str, Any]]:
        """
        댓글 좋아요를 토글하고 이벤트 데이터를 반환합니다.
        알림 생성은 별도 서비스에서 처리합니다.
        """
        transaction = self.db.transaction()

        @firestore.transactional
        def _toggle_like_in_transaction(transaction, user_id, comment_id):
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
                return {
                    'action': 'unliked',
                    'user_id': user_id,
                    'comment_id': comment_id,
                    'comment_data': comment_doc.to_dict()
                }
            else:
                transaction.set(like_ref, {
                    'user_id': user_id, 
                    'comment_id': comment_id, 
                    'created_at': datetime.utcnow()
                })
                transaction.update(comment_ref, {'like_count': firestore.Increment(1)})
                return {
                    'action': 'liked',
                    'user_id': user_id,
                    'comment_id': comment_id,
                    'comment_data': comment_doc.to_dict()
                }

        try:
            like_event_data = _toggle_like_in_transaction(transaction, user_id, comment_id)
            action = like_event_data['action']
            metrics.increment('comments.like.toggle', action=action)
            return like_event_data
        except Exception as e:
            logging.error(f"댓글 좋아요 토글 실패: {e}", exc_info=True)
            if isinstance(e, ValueError): 
                raise e
            return None

    def check_likes_for_comments(self, user_id: str, comment_ids: List[str]) -> set:
        """주어진 댓글 ID 목록에 대해 사용자의 좋아요 여부를 일괄 확인합니다."""
        if not user_id or not comment_ids:
            return set()
            
        liked_comment_ids = set()
        for i in range(0, len(comment_ids), 30):
            chunk_ids = comment_ids[i:i+30]
            like_doc_ids = [f"comment_{user_id}_{cid}" for cid in chunk_ids]
            like_docs = self.likes_ref.where('__name__', 'in', like_doc_ids).stream()
            for doc in like_docs:
                liked_comment_ids.add(doc.to_dict().get('comment_id'))
        return liked_comment_ids
