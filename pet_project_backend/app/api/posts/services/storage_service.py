# app/api/posts/services/storage_service.py
"""
게시글 관련 스토리지 작업을 담당하는 서비스
- 게시글 이미지 파일 업로드/삭제 처리
- Firebase Storage와의 상호작용
"""
import logging
from typing import List, Dict, Any
from app.services.storage_service import StorageService


class PostStorageService:
    """
    게시글 관련 스토리지 관리를 담당하는 서비스
    """
    def __init__(self, storage_service: StorageService):
        self.storage_service = storage_service

    def init_app(self, app):
        self.app = app

    def cleanup_post_files(self, file_paths: List[str]) -> None:
        """
        게시글 삭제 후 관련된 이미지 파일들을 Storage에서 삭제합니다.
        """
        if not file_paths:
            return

        for url in file_paths:
            try:
                # GCS 경로 추출 로직을 더 견고하게 수정
                if "firebasestorage.googleapis.com" in url:
                    file_path = url.split('o/')[1].split('?')[0].replace('%2F', '/')
                    blob = self.storage_service.bucket.blob(file_path)
                    if blob.exists():
                        blob.delete()
                        logging.info(f"게시글 이미지 파일 삭제 완료: {file_path}")
                    else:
                        logging.warning(f"삭제할 파일이 존재하지 않습니다: {file_path}")
            except Exception as e:
                logging.error(f"Storage 이미지 삭제 실패 (url: {url}): {e}")

    def process_post_uploads(self, files: List[Any]) -> List[str]:
        """
        게시글용 파일 업로드를 처리합니다.
        반환값: 업로드된 파일들의 URL 리스트
        """
        try:
            uploaded_urls = []
            for file in files:
                # 실제 파일 업로드 로직은 기존 StorageService를 활용
                # 이 메서드는 필요에 따라 구현할 수 있음
                pass
            return uploaded_urls
        except Exception as e:
            logging.error(f"게시글 파일 업로드 실패: {e}", exc_info=True)
            return []

    def validate_image_files(self, file_paths: List[str]) -> bool:
        """
        게시글에 첨부된 이미지 파일들의 유효성을 검사합니다.
        """
        try:
            for file_path in file_paths:
                if not file_path or not isinstance(file_path, str):
                    return False
                # 추가적인 파일 유효성 검사 로직
            return True
        except Exception as e:
            logging.error(f"이미지 파일 유효성 검사 실패: {e}")
            return False
