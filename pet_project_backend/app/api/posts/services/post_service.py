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
from dataclasses import asdict
from typing import Optional, Dict, Any, Tuple, List

from firebase_admin import firestore

from app.models.post import Post, Author, PetInfo
from app.utils.datetime_utils import DateTimeUtils


class PostService:
    """Core post CRUD service.

    Firestore dependency is injected. When `db_client` is None (e.g., DOCS_MODE)
    methods return lightweight placeholders or no-op values without touching Firestore.
    """
    def __init__(self, db_client=None, storage_service=None):
        self.db = db_client
        self.storage_service = storage_service
        if self.db is None:
            self.posts_ref = None
            self.users_ref = None
            self.pets_ref = None
            logging.info("PostService initialized without Firestore client (dependency not provided)")
        else:
            self.posts_ref = self.db.collection('posts')
            self.users_ref = self.db.collection('users')
            self.pets_ref = self.db.collection('pets')

    def create_post(self, user_id: str, text: str, file_paths: List[str]) -> Optional[Dict[str, Any]]:
        """새로운 게시글을 생성하고 Firestore에 저장합니다.

        Snapshot Policy (PR4 문서화):
        - 게시글 작성 시 작성자의 첫 번째 펫 문서를 조회하여 author.pet 정보를(snapshot 형태) 게시글에 내장합니다.
        - 이 스냅샷은 이후 펫 프로필(닉네임/품종/이미지) 변경 시 과거 게시글을 소급 업데이트하지 않습니다 (stale 허용).
        - 허용 이유: 게시글 타임라인 무결성 + 비용(대량 update fan-out) 절감. UI는 최신 프로필 필요 시 별도 lookup / lazy merge 전략 가능.
        - 향후 변경 여지: Verified 변경(예: is_verified)만 실시간 반영 요구 시 projection 레이어(PostPresenter)에서 merge hook 추가.
        
        Args:
            user_id: 작성자 사용자 ID
            text: 게시글 텍스트
            file_paths: Storage에 업로드된 파일의 상대 경로 리스트
        
        Returns:
            생성된 게시글 정보 (image_urls는 Firebase Storage URL 포함)
        
        Note:
            file_paths는 클라이언트가 pre-signed URL로 업로드 완료한 파일의 경로여야 합니다.
            존재하지 않는 파일 경로가 포함된 경우 FileNotFoundError 발생.
        """
        # file_paths를 Firebase Storage URL로 변환
        image_urls = self._convert_paths_to_urls(file_paths)
        
        if self.db is None:
            # Return synthetic post object (no persistence)
            post_id = str(uuid.uuid4())
            author = Author(user_id=user_id, nickname="demo_user")
            pet_info = PetInfo(pet_id="demo_pet", name="Demo", breed="Unknown", birthdate=None, profile_image_url=None)
            new_post = Post(post_id=post_id, author=author, pet=pet_info, image_urls=image_urls, text=text)
            return asdict(new_post)
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
            if not pet_data.get("pet_id"):
                pet_data["pet_id"] = pet_raw.id

            author = Author(user_id=user_id, nickname=user_data.get("nickname"))
            pet_info = PetInfo(
                pet_id=pet_data.get("pet_id"),
                name=pet_data.get("name"),
                breed=pet_data.get("breed"),
                birthdate=pet_data.get("birthdate"),
                profile_image_url=pet_data.get("profile_image_url")
            )
            post_id = str(uuid.uuid4())
            new_post = Post(post_id=post_id, author=author, pet=pet_info, image_urls=image_urls, text=text)
            post_data = DateTimeUtils.for_firestore(asdict(new_post))
            self.posts_ref.document(post_id).set(post_data)
            return asdict(new_post)
        except Exception as e:
            logging.error(f"게시글 생성 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def _convert_paths_to_urls(self, file_paths: List[str]) -> List[str]:
        """
        파일 경로를 Firebase Storage URL로 변환합니다.
        
        이미 완전한 URL인 경우(https://로 시작)는 변환 없이 그대로 반환합니다.
        이는 다른 서비스(예: CartoonJobIntegrationService)에서 이미 URL을 생성한 경우를 지원합니다.
        
        Args:
            file_paths: Storage 파일 경로 또는 URL 리스트
            
        Returns:
            Firebase Storage URL 리스트 (토큰 포함)
            
        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            RuntimeError: StorageService가 초기화되지 않은 경우
        """
        if not file_paths:
            return []
        
        if not self.storage_service:
            logging.warning("StorageService가 없음. 경로를 그대로 반환합니다.")
            return file_paths
        
        image_urls = []
        for fp in file_paths:
            # 이미 완전한 URL인 경우 변환 스킵 (OCP: 기존 동작 확장)
            if fp and fp.startswith('https://'):
                logging.debug(f"이미 URL 형식: {fp}")
                image_urls.append(fp)
                continue
            
            # 상대 경로를 URL로 변환
            try:
                url = self.storage_service.get_public_url(fp)
                image_urls.append(url)
            except FileNotFoundError:
                logging.error(f"파일을 찾을 수 없음: {fp}. 클라이언트가 업로드를 완료했는지 확인하세요.")
                raise
            except Exception as e:
                logging.error(f"URL 변환 실패: {fp} - {e}")
                raise RuntimeError(f"이미지 URL 생성 실패: {str(e)}")
        
        return image_urls

    def _ensure_full_image_urls(self, post_data: Dict[str, Any]) -> None:
        """
        image_urls가 상대 경로인 경우 전체 URL로 변환합니다.
        기존 데이터 호환성을 위한 헬퍼 메서드입니다.
        
        Note:
            - 레거시 데이터 지원: DB에 상대 경로로 저장된 기존 데이터 처리
            - 새로운 데이터는 create_post에서 이미 URL로 변환되어 저장됨
            - URL 변환 실패 시 원본 유지 (에러 발생 안 함)
        """
        if not post_data or 'image_urls' not in post_data:
            return
        
        image_urls = post_data['image_urls']
        if not image_urls or not self.storage_service:
            return
        
        # 상대 경로인지 확인 (https://로 시작하지 않으면 상대 경로)
        converted_urls = []
        for url in image_urls:
            if url and not url.startswith('https://'):
                try:
                    # 상대 경로를 전체 URL로 변환
                    full_url = self.storage_service.get_public_url(url)
                    converted_urls.append(full_url)
                except Exception as e:
                    logging.warning(f"URL 변환 실패 (fallback to original): {url} - {e}")
                    converted_urls.append(url)
            else:
                converted_urls.append(url)
        
        post_data['image_urls'] = converted_urls
    
    def get_posts(self, limit: int, cursor: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """게시글 피드 목록을 페이지네이션으로 조회합니다 (좋아요 정보 제외)."""
        if self.db is None:
            return [], None
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
            self._ensure_full_image_urls(post_data)  # 레거시 데이터 지원
            posts.append(post_data)
            last_doc_id = doc.id

        return posts, last_doc_id

    def get_post_by_id(self, post_id: str) -> Optional[Dict[str, Any]]:
        """특정 게시글의 상세 정보를 조회합니다 (좋아요 정보 제외)."""
        if self.db is None:
            return None
        doc = self.posts_ref.document(post_id).get()
        if not doc.exists:
            return None
        post_data = doc.to_dict()
        self._ensure_full_image_urls(post_data)  # 레거시 데이터 지원
        return post_data

    def update_post(self, post_id: str, user_id: str, text: str) -> Optional[Dict[str, Any]]:
        """특정 게시글의 내용을 수정합니다."""
        if self.db is None:
            return None
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
        if self.db is None:
            return None
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
        if self.db is None:
            return [], None
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
        if self.db is None:
            return 0
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
