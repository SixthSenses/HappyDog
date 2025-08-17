# app/services/storage_service.py
import uuid
import logging
from datetime import timedelta
from flask import Flask
from firebase_admin import storage

class StorageService:
    """
    Firebase Storage 관련 로직을 담당하는 범용 서비스 클래스입니다.
    파일 업로드를 위한 Pre-signed URL 생성 등의 기능을 제공합니다.
    """

    def __init__(self):
        """
        클래스 인스턴스 생성 시 버킷을 None으로 초기화합니다.
        실제 버킷 객체는 init_app 메서드를 통해 주입됩니다.
        """
        self.bucket = None

    def init_app(self, app: Flask):
        """
        Flask 앱 초기화 과정에서 호출되어 Storage 버킷을 설정합니다.
        이 메서드는 app/__init__.py에서 단 한 번만 호출됩니다.
        
        :param app: Flask 애플리케이션 객체
        """
        bucket_name = app.config.get('FIREBASE_STORAGE_BUCKET')
        if not bucket_name:
            raise ValueError("FIREBASE_STORAGE_BUCKET 설정이 .env 또는 설정 파일에 필요합니다.")
        
        self.bucket = storage.bucket(bucket_name)
        logging.info("StorageService: Firebase Storage 서비스가 성공적으로 초기화되었습니다.")

    def generate_upload_url(self, user_id: str, upload_type: str, filename: str, content_type: str) -> dict:
        """
        파일 타입에 따라 적절한 경로에 업로드할 수 있는 Pre-signed URL을 생성합니다.
        클라이언트는 이 URL을 사용하여 서버를 거치지 않고 Firebase Storage에 직접 파일을 업로드(PUT)할 수 있습니다.

        :param user_id: JWT에서 추출한 현재 로그인된 사용자의 고유 ID
        :param upload_type: 업로드 목적을 나타내는 문자열 (예: "user_profile", "post_image")
        :param filename: 클라이언트가 업로드할 원본 파일명 (확장자 파악에 사용)
        :param content_type: 업로드할 파일의 MIME 타입 (예: "image/jpeg")
        :return: 업로드 URL과 서버에서 사용할 파일 경로가 담긴 딕셔너리
        """
        if not self.bucket:
            raise RuntimeError("StorageService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")

        # 'upload_type'에 따라 파일이 저장될 폴더 경로를 매핑합니다.
        path_map = {
            "user_profile": f"user_profiles/{user_id}",
            "pet_nose_print": f"nose_prints_staging/{user_id}",
            "eye_analysis": f"eye_analysis_images/{user_id}",
            "post_image": f"posts/{user_id}",
            "cartoon_source_image": f"cartoon_sources/{user_id}",
        }

        folder_path = path_map.get(upload_type)
        if not folder_path:
            raise ValueError(f"'{upload_type}'은(는) 유효한 업로드 타입이 아닙니다.")

        extension = filename.split('.')[-1] if '.' in filename else ''
        unique_filename = f"{uuid.uuid4()}.{extension}"
        destination_blob_name = f"{folder_path}/{unique_filename}"

        blob = self.bucket.blob(destination_blob_name)

        # 15분 동안 유효한 업로드 전용 URL을 생성합니다.
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type=content_type
        )

        return {
            "upload_url": upload_url,
            "file_path": destination_blob_name
        }

    def make_public_and_get_url(self, file_path: str) -> str:
        """
        지정된 파일을 공개(public)로 설정하고 해당 URL을 반환합니다.
        
        :param file_path: 공개로 전환할 파일의 경로
        :return: 공개적으로 접근 가능한 URL
        """
        if not self.bucket:
            raise RuntimeError("StorageService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")
            
        blob = self.bucket.blob(file_path)
        
        if not blob.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
            
        try:
            blob.make_public()
            return blob.public_url
        except Exception as e:
            logging.error(f"파일 공개 전환 실패: {e}", exc_info=True)
            raise