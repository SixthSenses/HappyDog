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
        self.likes_ref = self.db.collection('likes') # 좋아요 문서를 별도 컬렉션으로 관리

    def create_post(self, user_id: str, text: str, file_paths: List[str]) -> Optional[Dict[str, Any]]:
        """새로운 게시글을 생성하고 Firestore에 저장합니다."""
        try:
            # 1. 게시글 작성에 필요한 사용자 및 반려동물 정보 조회
            user_doc = self.users_ref.document(user_id).get()
            if not user_doc.exists: return None
            
            pet_doc = self.pets_ref.where('user_id', '==', user_id).limit(1).get()
            if not pet_doc: return None

            user_data = user_doc.to_dict()
            pet_data = pet_doc[0].to_dict()

            # 2. 데이터 모델 객체 생성
            author = Author(user_id=user_id, nickname=user_data.get("nickname"), profile_image_url=user_data.get("profile_image_url"))
            pet_info = PetInfo(pet_id=pet_data.get("pet_id"), name=pet_data.get("name"), breed=pet_data.get("breed"), birthdate=pet_data.get("birthdate"))
            
            post_id = str(uuid.uuid4())
            new_post = Post(
                post_id=post_id, author=author, pet=pet_info,
                image_urls=file_paths, # Pre-signed URL로 업로드된 경로를 그대로 사용
                text=text
            )

            # 3. Firestore에 저장
            self.posts_ref.document(post_id).set(asdict(new_post))
            return asdict(new_post)
        except Exception as e:
            logging.error(f"게시글 생성 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    # ... get_posts, get_post_by_id, update_post, delete_post 로직 ...
    def get_posts(self, current_user_id: str, limit: int, cursor: Optional[str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
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
        
        # 좋아요 상태 일괄 확인
        liked_post_ids = self._check_likes_for_posts(current_user_id, [p['post_id'] for p in post_list_for_like_check])
        for post_data in post_list_for_like_check:
            post_data['is_liked'] = post_data['post_id'] in liked_post_ids
            posts.append(post_data)

        return posts, last_doc_id

    def get_post_by_id(self, post_id: str, current_user_id: str) -> Optional[Dict[str, Any]]:
        doc = self.posts_ref.document(post_id).get()
        if not doc.exists:
            return None
        post_data = doc.to_dict()
        post_data['is_liked'] = self._is_user_liked_post(current_user_id, post_id)
        return post_data

    def update_post(self, post_id: str, user_id: str, text: str) -> Optional[Dict[str, Any]]:
        post_ref = self.posts_ref.document(post_id)
        doc = post_ref.get()
        if not doc.exists or doc.to_dict().get('author', {}).get('user_id') != user_id:
            return None
        
        update_data = {"text": text, "updated_at": datetime.now()}
        post_ref.update(update_data)
        return post_ref.get().to_dict()

    def delete_post(self, post_id: str, user_id: str, storage_service: StorageService) -> bool:
        post_ref = self.posts_ref.document(post_id)
        doc = post_ref.get()
        if not doc.exists or doc.to_dict().get('author', {}).get('user_id') != user_id:
            return False

        post_data = doc.to_dict()
        image_urls = post_data.get('image_urls', [])
        for url in image_urls:
            try:
                file_path = "/".join(url.split("?")[0].split("/")[-4:])
                blob = storage_service.bucket.blob(file_path)
                if blob.exists():
                    blob.delete()
            except Exception as e:
                logging.error(f"Storage 이미지 삭제 실패 (url: {url}): {e}")
        
        post_ref.delete()
        return True
    
    @firestore.transactional
    def _toggle_like_in_transaction(self, transaction, user_id: str, post_id: str) -> Tuple[bool, Optional[Dict]]:
        """
        트랜잭션 내에서 게시글 좋아요 상태를 토글합니다.
        - `likes` 컬렉션에 `f"{user_id}_{post_id}"` 형식의 문서를 생성/삭제합니다.
        - `posts` 문서의 `like_count` 필드를 원자적으로 증가/감소시킵니다.
        """
        like_id = f"post_{user_id}_{post_id}"
        like_ref = self.likes_ref.document(like_id)
        post_ref = self.posts_ref.document(post_id)
        
        like_doc = like_ref.get(transaction=transaction)
        post_doc = post_ref.get(transaction=transaction)

        if not post_doc.exists:
            raise ValueError("게시글을 찾을 수 없습니다.")
        
        if like_doc.exists:
            # 이미 좋아요를 누른 상태 -> 좋아요 취소
            transaction.delete(like_ref)
            transaction.update(post_ref, {'like_count': firestore.Increment(-1)})
            return False, post_doc.to_dict() # is_liked: False, 알림 생성 안 함
        else:
            # 새로운 좋아요
            transaction.set(like_ref, {'user_id': user_id, 'post_id': post_id, 'created_at': datetime.utcnow()})
            transaction.update(post_ref, {'like_count': firestore.Increment(1)})
            return True, post_doc.to_dict() # is_liked: True, 알림 생성 필요

    def toggle_post_like(self, user_id: str, post_id: str) -> bool:
        """게시글 좋아요를 누르거나 취소하고, 필요 시 알림을 생성합니다."""
        try:
            transaction = self.db.transaction()
            is_liked, post_data = self._toggle_like_in_transaction(transaction, user_id, post_id)
            
            # 새로운 좋아요인 경우에만 알림 생성
            if is_liked:
                post_author_id = post_data.get('author', {}).get('user_id')
                notification_service.create_notification(
                    recipient_id=post_author_id,
                    sender_id=user_id,
                    n_type=NotificationType.POST_LIKE,
                    target_id=post_id
                )
            return True
        except Exception as e:
            logging.error(f"게시글 좋아요 토글 실패 (user_id: {user_id}, post_id: {post_id}): {e}", exc_info=True)
            # ValueError는 route에서 처리하므로, 여기서는 False를 반환하거나 다시 raise
            if isinstance(e, ValueError):
                raise e
            return False
        
    def count_posts_by_user_id(self, author_id: str) -> int:
        """특정 사용자가 작성한 게시물의 총 개수를 반환합니다."""
        try:
            # count()는 Firestore의 최신 기능으로, 모든 문서를 가져오지 않고
            # 숫자만 효율적으로 집계하여 비용과 시간을 절약합니다.
            query = self.posts_ref.where('author.user_id', '==', author_id)
            count_query = query.count()
            count_result = count_query.get()
            return count_result[0][0].value
        except Exception as e:
            logging.error(f"사용자 게시물 수 집계 실패 (author_id: {author_id}): {e}", exc_info=True)
            return 0 # 오류 발생 시 0을 반환

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
            raise e
# 서비스 인스턴스는 app/__init__.py에서 생성 및 주입됩니다.
post_service: Optional[PostService] = None