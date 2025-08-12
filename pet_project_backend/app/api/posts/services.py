# app/api/posts/services.py
import logging
import uuid
from datetime import datetime
from firebase_admin import firestore
from dataclasses import asdict
from typing import Optional, Dict, Any, Tuple, List

from app.models.post import Post, Author, PetInfo
from app.models.notification import NotificationType
from app.services.notification_service import notification_service
from app.services.storage_service import StorageService # 삭제 로직에 필요

class PostService:
    """
    게시글 관련 비즈니스 로직을 담당하는 서비스 클래스.
    모든 DB 상호작용과 핵심 로직을 포함합니다.
    """
    def __init__(self):
        self.db = firestore.client()
        self.posts_ref = self.db.collection('posts')
        self.users_ref = self.db.collection('users')
        self.pets_ref = self.db.collection('pets')
        self.likes_ref = self.db.collection('likes')

    def create_post(self, user_id: str, text: str, file_paths: List[str]) -> Optional[Dict[str, Any]]:
        """새로운 게시글을 생성하고 Firestore에 저장합니다."""
        try:
            user_doc = self.users_ref.document(user_id).get()
            if not user_doc.exists: return None
            
            pet_doc = self.pets_ref.where('user_id', '==', user_id).limit(1).get()
            if not pet_doc: return None

            user_data = user_doc.to_dict()
            pet_data = pet_doc[0].to_dict()

            author = Author(user_id=user_id, nickname=user_data.get("nickname"), profile_image_url=user_data.get("profile_image_url"))
            pet_info = PetInfo(pet_id=pet_data.get("pet_id"), name=pet_data.get("name"), breed=pet_data.get("breed"), birthdate=pet_data.get("birthdate"))
            
            post_id = str(uuid.uuid4())
            new_post = Post(
                post_id=post_id, author=author, pet=pet_info,
                image_urls=file_paths,
                text=text
            )

            self.posts_ref.document(post_id).set(asdict(new_post))
            return asdict(new_post)
        except Exception as e:
            logging.error(f"게시글 생성 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def get_posts(self, current_user_id: Optional[str], limit: int, cursor: Optional[str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """게시글 피드 목록을 페이지네이션으로 조회합니다."""
        query = self.posts_ref.order_by("created_at", direction=firestore.Query.DESCENDING)
        if cursor:
            cursor_doc = self.posts_ref.document(cursor).get()
            if cursor_doc.exists:
                query = query.start_after(cursor_doc)

        docs = query.limit(limit).stream()
        posts = []
        last_doc_id = None
        
        post_list_for_like_check = []
        for doc in docs:
            post_data = doc.to_dict()
            post_list_for_like_check.append(post_data)
            last_doc_id = doc.id
        
        if current_user_id:
            liked_post_ids = self._check_likes_for_posts(current_user_id, [p['post_id'] for p in post_list_for_like_check])
            for post_data in post_list_for_like_check:
                post_data['is_liked'] = post_data['post_id'] in liked_post_ids
                posts.append(post_data)
        else:
            posts = post_list_for_like_check

        return posts, last_doc_id

    def get_post_by_id(self, post_id: str, current_user_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """특정 게시글의 상세 정보를 조회합니다."""
        doc = self.posts_ref.document(post_id).get()
        if not doc.exists:
            return None
        post_data = doc.to_dict()
        post_data['is_liked'] = self._is_user_liked_post(current_user_id, post_id)
        return post_data

    def update_post(self, post_id: str, user_id: str, text: str) -> Optional[Dict[str, Any]]:
        """특정 게시글의 내용을 수정합니다."""
        post_ref = self.posts_ref.document(post_id)
        doc = post_ref.get()
        if not doc.exists or doc.to_dict().get('author', {}).get('user_id') != user_id:
            raise PermissionError("게시글을 수정할 권한이 없습니다.")
        
        update_data = {"text": text, "updated_at": datetime.utcnow()}
        post_ref.update(update_data)
        updated_doc = post_ref.get()
        return updated_doc.to_dict() if updated_doc.exists else None

    def delete_post(self, post_id: str, user_id: str, storage_service: StorageService) -> None:
        """특정 게시글과 관련 이미지들을 삭제합니다."""
        post_ref = self.posts_ref.document(post_id)
        doc = post_ref.get()
        if not doc.exists:
            raise ValueError("삭제할 게시물이 없습니다.")
        
        post_data = doc.to_dict()
        if post_data.get('author', {}).get('user_id') != user_id:
            raise PermissionError("게시글을 삭제할 권한이 없습니다.")

        image_urls = post_data.get('image_urls', [])
        for url in image_urls:
            try:
                # GCS 경로 추출 로직을 더 견고하게 수정
                if "firebasestorage.googleapis.com" in url:
                    file_path = url.split('o/')[1].split('?')[0].replace('%2F', '/')
                    blob = storage_service.bucket.blob(file_path)
                    if blob.exists():
                        blob.delete()
            except Exception as e:
                logging.error(f"Storage 이미지 삭제 실패 (url: {url}): {e}")
        
        post_ref.delete()

    def toggle_post_like(self, user_id: str, post_id: str) -> bool:
        """게시글 좋아요를 누르거나 취소하고, 필요 시 알림을 생성합니다."""
        transaction = self.db.transaction()

        @firestore.transactional
        def _update_in_transaction(transaction, user_id, post_id):
            like_id = f"post_{user_id}_{post_id}"
            like_ref = self.likes_ref.document(like_id)
            post_ref = self.posts_ref.document(post_id)
            
            like_doc = like_ref.get(transaction=transaction)
            post_doc = post_ref.get(transaction=transaction)

            if not post_doc.exists:
                raise ValueError("게시글을 찾을 수 없습니다.")
            
            if like_doc.exists:
                transaction.delete(like_ref)
                transaction.update(post_ref, {'like_count': firestore.Increment(-1)})
                return False, post_doc.to_dict()
            else:
                transaction.set(like_ref, {'user_id': user_id, 'post_id': post_id, 'created_at': datetime.utcnow()})
                transaction.update(post_ref, {'like_count': firestore.Increment(1)})
                return True, post_doc.to_dict()

        try:
            is_liked, post_data = _update_in_transaction(transaction, user_id, post_id)
            
            if is_liked and post_data:
                post_author_id = post_data.get('author', {}).get('user_id')
                if post_author_id != user_id:
                    notification_service.create_notification(
                        recipient_id=post_author_id,
                        sender_id=user_id,
                        n_type=NotificationType.POST_LIKE,
                        target_id=post_id
                    )
            return True
        except Exception as e:
            logging.error(f"게시글 좋아요 토글 실패: {e}", exc_info=True)
            if isinstance(e, ValueError): raise e
            return False

    def count_posts_by_user_id(self, author_id: str) -> int:
        """특정 사용자가 작성한 게시물의 총 개수를 반환합니다."""
        try:
            query = self.posts_ref.where('author.user_id', '==', author_id)
            count_query = query.count()
            count_result = count_query.get()
            return count_result[0][0].value
        except Exception as e:
            logging.error(f"사용자 게시물 수 집계 실패 (author_id: {author_id}): {e}", exc_info=True)
            return 0

    def get_posts_by_user_id(self, author_id: str, current_user_id: Optional[str], limit: int, cursor: Optional[str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """특정 사용자가 작성한 게시물 목록을 페이지네이션으로 조회합니다."""
        try:
            query = self.posts_ref.where('author.user_id', '==', author_id).order_by("created_at", direction=firestore.Query.DESCENDING)
            
            if cursor:
                cursor_doc = self.posts_ref.document(cursor).get()
                if cursor_doc.exists:
                    query = query.start_after(cursor_doc)

            docs = query.limit(limit).stream()
            posts = [doc.to_dict() for doc in docs]
            last_doc_id = posts[-1]['post_id'] if posts else None
            
            if current_user_id and posts:
                liked_post_ids = self._check_likes_for_posts(current_user_id, [p['post_id'] for p in posts])
                for post in posts:
                    post['is_liked'] = post['post_id'] in liked_post_ids
            return posts, last_doc_id
        except Exception as e:
            logging.error(f"사용자 게시물 목록 조회 실패 (author_id: {author_id}): {e}", exc_info=True)
            raise

    def _is_user_liked_post(self, user_id: Optional[str], post_id: str) -> bool:
        """[신규] 특정 게시물에 대한 사용자의 좋아요 여부를 확인합니다."""
        if not user_id:
            return False
        like_id = f"post_{user_id}_{post_id}"
        like_doc = self.likes_ref.document(like_id).get()
        return like_doc.exists

    def _check_likes_for_posts(self, user_id: Optional[str], post_ids: List[str]) -> set:
        """[신규] 주어진 게시물 ID 목록에 대한 사용자의 좋아요 여부를 일괄 확인합니다."""
        if not user_id or not post_ids:
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

# 서비스 인스턴스는 app/__init__.py에서 생성 및 주입됩니다.
post_service: Optional[PostService] = None