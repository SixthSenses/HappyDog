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
from dataclasses import asdict
from typing import Optional, Dict, Any, List, Tuple

from firebase_admin import firestore

from app.models.comment import Comment, CommentAuthor, CommentPetInfo
from app.utils import metrics


class CommentService:
    """Core comment CRUD service.

    Firestore dependency is injected. When `db_client` is None (e.g., DOCS_MODE),
    methods return placeholders or no-op values instead of touching Firestore.
    """
    def __init__(self, db_client=None, storage_service=None):
        self.db = db_client
        self.storage_service = storage_service
        if self.db is None:
            self.comments_ref = None
            self.posts_ref = None
            self.users_ref = None
            self.pets_ref = None
            self.likes_ref = None
            logging.info("CommentService initialized without Firestore client (dependency not provided)")
        else:
            self.comments_ref = self.db.collection('comments')
            self.posts_ref = self.db.collection('posts')
            self.users_ref = self.db.collection('users')
            self.pets_ref = self.db.collection('pets')
            self.likes_ref = self.db.collection('likes')

    def _convert_profile_image_url(self, profile_image_url: Optional[str]) -> Optional[str]:
        """
        펫 프로필 이미지 경로를 Firebase Storage 공개 URL로 변환합니다.
        
        Args:
            profile_image_url: Storage 파일 경로 또는 URL 또는 None
            
        Returns:
            Firebase Storage URL 또는 None
        """
        if not profile_image_url:
            return None
        
        # 이미 전체 URL인 경우
        if profile_image_url.startswith('https://'):
            return profile_image_url
        
        # StorageService가 없으면 원본 반환
        if not self.storage_service:
            logging.warning(f"StorageService가 없어 profile_image_url 변환 불가: {profile_image_url}")
            return profile_image_url
        
        # 상대 경로를 URL로 변환
        try:
            return self.storage_service.get_public_url(profile_image_url)
        except Exception as e:
            logging.warning(f"Profile image URL 변환 실패 (fallback to original): {profile_image_url} - {e}")
            return profile_image_url

    def _ensure_full_profile_image_url(self, comment_data: Dict[str, Any]) -> None:
        """
        댓글 데이터의 pet.profile_image_url이 상대 경로인 경우 전체 URL로 변환합니다.
        기존 데이터 호환성을 위한 헬퍼 메서드입니다.
        
        Note:
            - 레거시 데이터 지원: DB에 상대 경로로 저장된 기존 데이터 처리
            - 새로운 데이터는 create_comment에서 이미 URL로 변환되어 저장됨
            - URL 변환 실패 시 원본 유지 (에러 발생 안 함)
        """
        if not comment_data or not self.storage_service:
            return
        
        # pet.profile_image_url 변환
        if 'pet' in comment_data and isinstance(comment_data['pet'], dict):
            pet_data = comment_data['pet']
            if 'profile_image_url' in pet_data:
                profile_url = pet_data.get('profile_image_url')
                if profile_url and not profile_url.startswith('https://'):
                    try:
                        full_url = self.storage_service.get_public_url(profile_url)
                        pet_data['profile_image_url'] = full_url
                    except Exception as e:
                        logging.warning(f"Profile image URL 변환 실패 (fallback to original): {profile_url} - {e}")

    def create_comment(self, post_id: str, author_id: str, text: str) -> Dict[str, Any]:
        """
        새로운 댓글을 생성합니다 (순수한 CRUD 로직만).
        알림이나 멘션 처리는 별도 서비스에서 처리합니다.
        """
        if self.db is None:
            comment_id = str(uuid.uuid4())
            author = CommentAuthor(user_id=author_id, nickname="demo_user")
            pet = CommentPetInfo(pet_id="demo_pet", name="Demo", breed="Unknown", profile_image_url=None, is_verified=False)
            new_comment = Comment(comment_id=comment_id, post_id=post_id, author=author, pet=pet, text=text)
            metrics.increment('comments.created')
            comment_dict = asdict(new_comment)
            comment_dict['post_data'] = {}
            return comment_dict
        author_doc = self.users_ref.document(author_id).get()
        if not author_doc.exists:
            raise ValueError("댓글 작성자를 찾을 수 없습니다.")
        pet_docs = self.pets_ref.where('user_id', '==', author_id).limit(1).get()
        if not pet_docs:
            raise ValueError("댓글 작성자의 반려동물 정보를 찾을 수 없습니다.")
        author_info = author_doc.to_dict()
        pet_data = pet_docs[0].to_dict()
        if not pet_data.get("pet_id"):
            pet_data["pet_id"] = pet_docs[0].id
        author = CommentAuthor(user_id=author_id, nickname=author_info.get("nickname"))
        
        # 펫 프로필 이미지 URL 변환 (상대 경로 → 공개 URL)
        profile_image_url = pet_data.get("profile_image_url")
        full_profile_image_url = self._convert_profile_image_url(profile_image_url)
        
        pet = CommentPetInfo(
            pet_id=pet_data.get("pet_id"),
            name=pet_data.get("name"),
            breed=pet_data.get("breed"),
            profile_image_url=full_profile_image_url,
            is_verified=pet_data.get("is_verified", False)
        )
        transaction = self.db.transaction()
        @firestore.transactional
        def _update_in_transaction(transaction, post_id, author, pet, text):
            post_ref = self.posts_ref.document(post_id)
            post_snapshot = post_ref.get(transaction=transaction)
            if not post_snapshot.exists:
                raise ValueError("댓글을 작성할 게시물이 존재하지 않습니다.")
            comment_id = str(uuid.uuid4())
            new_comment = Comment(comment_id=comment_id, post_id=post_id, author=author, pet=pet, text=text)
            transaction.set(self.comments_ref.document(comment_id), asdict(new_comment))
            transaction.update(post_ref, {'comment_count': firestore.Increment(1)})
            return new_comment, post_snapshot.to_dict()
        new_comment, post_data = _update_in_transaction(transaction, post_id, author, pet, text)
        metrics.increment('comments.created')
        comment_dict = asdict(new_comment)
        comment_dict['post_data'] = post_data
        return comment_dict

    def get_comments_for_post(self, post_id: str, limit: int, cursor: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        특정 게시글의 댓글 목록을 페이지네이션으로 조회합니다 (좋아요 정보 제외).
        좋아요 정보는 별도 서비스에서 추가됩니다.
        """
        if self.db is None:
            return [], None
        query = self.comments_ref.where('post_id', '==', post_id).order_by("created_at")
        if cursor:
            cursor_doc = self.comments_ref.document(cursor).get()
            if cursor_doc.exists:
                query = query.start_after(cursor_doc)
        
        docs = query.limit(limit).stream()
        comments = []
        last_doc_id = None
        
        for doc in docs:
            comment_data = doc.to_dict()
            self._ensure_full_profile_image_url(comment_data)  # 레거시 데이터 지원
            comments.append(comment_data)
            last_doc_id = comment_data.get('comment_id') if comment_data else None
        
        return comments, last_doc_id

    def get_comment_by_id(self, comment_id: str) -> Optional[Dict[str, Any]]:
        """특정 댓글의 정보를 조회합니다."""
        if self.db is None:
            return None
        doc = self.comments_ref.document(comment_id).get()
        if not doc.exists:
            return None
        return doc.to_dict()

    def delete_comment(self, comment_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        댓글을 삭제하고 삭제된 댓글 정보를 반환합니다.
        이벤트 처리를 위해 삭제된 댓글 데이터를 반환합니다.
        """
        if self.db is None:
            return None
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
        if self.db is None:
            return None
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
        if self.db is None:
            return None
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
        if not user_id or not comment_ids or self.db is None:
            return set()
            
        liked_comment_ids = set()
        for i in range(0, len(comment_ids), 30):
            chunk_ids = comment_ids[i:i+30]
            like_doc_ids = [f"comment_{user_id}_{cid}" for cid in chunk_ids]
            like_docs = self.likes_ref.where('__name__', 'in', like_doc_ids).stream()
            for doc in like_docs:
                liked_comment_ids.add(doc.to_dict().get('comment_id'))
        return liked_comment_ids
