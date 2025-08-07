# app/api/mungstagram/services.py
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import asdict

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.models.post import Post, Author, PetInfo
from app.models.user import User
from app.models.pet import Pet
from app.models.notification import Notification, NotificationActor
from app.models.cartoon_job import CartoonJob
from app.services.storage_service import StorageService

class MungstagramService:
    def __init__(self):
        self.db = None
        self.posts_ref = None
        self.users_ref = None
        self.pets_ref = None
        self.notifications_ref = None
        self.cartoon_jobs_ref = None

    def init_app(self):
        self.db = firestore.client()
        self.posts_ref = self.db.collection('posts')
        self.users_ref = self.db.collection('users')
        self.pets_ref = self.db.collection('pets')
        self.notifications_ref = self.db.collection('notifications')
        self.cartoon_jobs_ref = self.db.collection('cartoon_jobs')

    # --- Phase 1: 핵심 CRUD ---
    def create_post(self, user_id: str, post_data: Dict[str, Any], storage_service: StorageService) -> Optional[Dict[str, Any]]:
        user_doc = self.users_ref.document(user_id).get()
        if not user_doc.exists:
            raise ValueError("사용자를 찾을 수 없습니다.")
        user = User(**user_doc.to_dict())

        pet_query = self.pets_ref.where(filter=FieldFilter("user_id", "==", user_id)).limit(1).stream()
        pet_doc = next(pet_query, None)
        if not pet_doc:
            raise ValueError("반려동물 정보를 찾을 수 없습니다.")
        pet = Pet(**pet_doc.to_dict())

        author = Author(user_id=user.user_id, nickname=user.nickname, profile_image_url=user.profile_image_url)
        pet_info = PetInfo(pet_id=pet.pet_id, name=pet.name, breed=pet.breed, birthdate=pet.birthdate)

        image_urls = []
        for file_path in post_data['file_paths']:
            blob = storage_service.bucket.blob(file_path)
            if blob.exists():
                blob.make_public()
                image_urls.append(blob.public_url)

        if not image_urls:
            raise ValueError("유효한 이미지 경로가 없습니다.")

        new_post = Post(
            post_id=str(uuid.uuid4()),
            author=author,
            pet=pet_info,
            image_urls=image_urls,
            text=post_data['text']
        )

        post_dict = asdict(new_post)
        self.posts_ref.document(new_post.post_id).set(post_dict)
        return post_dict

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

    # 좋아요 기능 ---
    def add_like(self, user_id: str, post_id: str):
        post_ref = self.posts_ref.document(post_id)
        like_ref = post_ref.collection('likes').document(user_id)

        @firestore.transactional
        def _add_like_transaction(transaction, post_ref, like_ref):
            post_snapshot = post_ref.get(transaction=transaction)
            if not post_snapshot.exists:
                raise ValueError("게시물을 찾을 수 없습니다.")
            
            like_snapshot = like_ref.get(transaction=transaction)
            if like_snapshot.exists:
                return post_snapshot.to_dict() # 이미 좋아요를 누름

            transaction.set(like_ref, {'created_at': datetime.now()})
            transaction.update(post_ref, {'like_count': firestore.Increment(1)})
            
            # 알림 생성
            post_author_id = post_snapshot.to_dict().get('author', {}).get('user_id')
            if post_author_id != user_id:
                self._create_notification(
                    recipient_id=post_author_id,
                    actor_id=user_id,
                    notification_type='LIKE',
                    post_id=post_id
                )
            
            return post_ref.get(transaction=transaction).to_dict()

        transaction = self.db.transaction()
        return _add_like_transaction(transaction, post_ref, like_ref)

    def remove_like(self, user_id: str, post_id: str):
        post_ref = self.posts_ref.document(post_id)
        like_ref = post_ref.collection('likes').document(user_id)

        @firestore.transactional
        def _remove_like_transaction(transaction, post_ref, like_ref):
            like_snapshot = like_ref.get(transaction=transaction)
            if not like_snapshot.exists:
                return # 이미 좋아요 취소됨

            transaction.delete(like_ref)
            transaction.update(post_ref, {'like_count': firestore.Increment(-1)})

        transaction = self.db.transaction()
        _remove_like_transaction(transaction, post_ref, like_ref)
    
    def _is_user_liked_post(self, user_id: str, post_id: str) -> bool:
        like_ref = self.posts_ref.document(post_id).collection('likes').document(user_id)
        return like_ref.get().exists

    def _check_likes_for_posts(self, user_id: str, post_ids: List[str]) -> set:
        liked_post_ids = set()
        for post_id in post_ids:
            if self._is_user_liked_post(user_id, post_id):
                liked_post_ids.add(post_id)
        return liked_post_ids

    # ---  만화 생성 ---
    def create_cartoon_job(self, user_id: str, job_data: Dict[str, Any], storage_service: StorageService) -> Dict[str, Any]:
        image_urls = []
        for file_path in job_data['file_paths']:
            blob = storage_service.bucket.blob(file_path)
            if blob.exists():
                blob.make_public()
                image_urls.append(blob.public_url)
        
        new_job = CartoonJob(
            job_id=str(uuid.uuid4()),
            user_id=user_id,
            source_image_urls=image_urls,
            source_text=job_data['text']
        )
        job_dict = asdict(new_job)
        self.cartoon_jobs_ref.document(new_job.job_id).set(job_dict)
        return job_dict

    def get_cartoon_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        doc = self.cartoon_jobs_ref.document(job_id).get()
        return doc.to_dict() if doc.exists else None

    # --알림 ---
    def _create_notification(self, recipient_id: str, actor_id: str, notification_type: str, post_id: str):
        actor_doc = self.users_ref.document(actor_id).get()
        if not actor_doc.exists:
            return

        actor_user = User(**actor_doc.to_dict())
        actor = NotificationActor(
            user_id=actor_user.user_id,
            nickname=actor_user.nickname,
            profile_image_url=actor_user.profile_image_url
        )

        new_notification = Notification(
            notification_id=str(uuid.uuid4()),
            recipient_id=recipient_id,
            actor=actor,
            type=notification_type,
            post_id=post_id
        )
        notification_dict = asdict(new_notification)
        self.notifications_ref.document(new_notification.notification_id).set(notification_dict)


mungstagram_service = MungstagramService()
