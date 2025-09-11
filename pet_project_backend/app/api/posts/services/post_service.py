# app/api/posts/services/post_service.py
"""
핵심 게시글 CRUD 작업만을 담당하는 서비스
- 순수한 게시글 생성/조회/수정/삭제 로직
- 알림이나 스토리지 정리는 별도 서비스에서 처리
- 이벤트 데이터를 반환하여 다른 서비스에서 후속 처리 가능
"""
import logging
import uuid
from datetime import datetime
from firebase_admin import firestore
from dataclasses import asdict
from typing import Optional, Dict, Any, Tuple, List

from app.models.post import Post, Author, PetInfo
from app.utils.datetime_utils import DateTimeUtils


class PostService:
    """
    게시글 CRUD 작업을 담당하는 핵심 서비스
    """
    def __init__(self):
        self.db = firestore.client()
        self.posts_ref = self.db.collection('posts')
        self.users_ref = self.db.collection('users')
        self.pets_ref = self.db.collection('pets')

    def create_post(self, user_id: str, text: str, file_paths: List[str]) -> Optional[Dict[str, Any]]:
        """새로운 게시글을 생성하고 Firestore에 저장합니다."""
        try:
            user_doc = self.users_ref.document(user_id).get()
            if not user_doc.exists: 
                return None
            
            pet_doc = self.pets_ref.where('user_id', '==', user_id).limit(1).get()
            if not pet_doc: 
                return None

            user_data = user_doc.to_dict()
            pet_raw = pet_doc[0]
            pet_data = pet_raw.to_dict()
            # 레거시 문서 보완: pet_id 필드 누락 시 문서 ID로 주입
            if not pet_data.get("pet_id"):
                pet_data["pet_id"] = pet_raw.id

            author = Author(
                user_id=user_id, 
                nickname=user_data.get("nickname")
                # profile_image_url는 pet 정보에서 가져오도록 변경됨
            )
            pet_info = PetInfo(
                pet_id=pet_data.get("pet_id"), 
                name=pet_data.get("name"), 
                breed=pet_data.get("breed"), 
                birthdate=pet_data.get("birthdate"),
                profile_image_url=pet_data.get("profile_image_url")  # Pet 프로필 이미지 사용
            )
            
            post_id = str(uuid.uuid4())
            new_post = Post(
                post_id=post_id, 
                author=author, 
                pet=pet_info,
                image_urls=file_paths,
                text=text
            )

            # Firestore 호환 변환 후 저장
            post_data = DateTimeUtils.for_firestore(asdict(new_post))
            self.posts_ref.document(post_id).set(post_data)
            return asdict(new_post)
        except Exception as e:
            logging.error(f"게시글 생성 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def get_posts(self, limit: int, cursor: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """게시글 피드 목록을 페이지네이션으로 조회합니다 (좋아요 정보 제외)."""
        query = self.posts_ref.order_by("created_at", direction=firestore.Query.DESCENDING)
        if cursor:
            cursor_doc = self.posts_ref.document(cursor).get()
            if cursor_doc.exists:
                query = query.start_after(cursor_doc)

        docs = query.limit(limit).stream()
        posts = []
        last_doc_id = None
        
        for doc in docs:
            post_data = doc.to_dict()
            posts.append(post_data)
            last_doc_id = doc.id

        return posts, last_doc_id

    def get_post_by_id(self, post_id: str) -> Optional[Dict[str, Any]]:
        """특정 게시글의 상세 정보를 조회합니다 (좋아요 정보 제외)."""
        doc = self.posts_ref.document(post_id).get()
        if not doc.exists:
            return None
        return doc.to_dict()

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

    def delete_post(self, post_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        특정 게시글을 삭제하고 삭제된 게시글 정보를 반환합니다.
        스토리지 정리는 별도 서비스에서 처리합니다.
        """
        post_ref = self.posts_ref.document(post_id)
        doc = post_ref.get()
        if not doc.exists:
            raise ValueError("삭제할 게시물이 없습니다.")
        
        post_data = doc.to_dict()
        if post_data.get('author', {}).get('user_id') != user_id:
            raise PermissionError("게시글을 삭제할 권한이 없습니다.")

        post_ref.delete()
        return post_data  # 스토리지 정리를 위해 삭제된 게시글 데이터 반환

    def get_posts_by_user_id(self, author_id: str, limit: int, cursor: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
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
            
            return posts, last_doc_id
        except Exception as e:
            logging.error(f"사용자 게시물 목록 조회 실패 (author_id: {author_id}): {e}", exc_info=True)
            raise

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

    def get_user_post_count(self, user_id: str) -> int:
        """특정 사용자가 작성한 게시물의 총 개수를 반환합니다. (alias for count_posts_by_user_id)"""
        return self.count_posts_by_user_id(user_id)
