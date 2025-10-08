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
        
        Args:
            file_paths: Firebase Storage URL 리스트
            
        Note:
            Firebase Storage URL 형식에서 파일 경로를 추출하여 삭제합니다.
            URL 형식: https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{encoded_path}?alt=media&token={token}
        """
        if not file_paths:
            return

        for url in file_paths:
            try:
                # Firebase Storage URL에서 파일 경로 추출
                if "firebasestorage.googleapis.com" in url:
                    from urllib.parse import unquote
                    # URL에서 'o/' 뒤의 인코딩된 경로 추출
                    file_path = url.split('o/')[1].split('?')[0]
                    # URL 디코딩 (%2F -> /)
                    file_path = unquote(file_path)
                    
                    blob = self.storage_service.bucket.blob(file_path)
                    if blob.exists():
                        blob.delete()
                        logging.info(f"게시글 이미지 파일 삭제 완료: {file_path}")
                    else:
                        logging.warning(f"삭제할 파일이 존재하지 않습니다: {file_path}")
                else:
                    logging.warning(f"인식할 수 없는 URL 형식: {url}")
            except Exception as e:
                logging.error(f"Storage 이미지 삭제 실패 (url: {url}): {e}")
