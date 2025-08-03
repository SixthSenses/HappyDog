# app/services/storage_service.py

import time
import uuid
from firebase_admin import storage
from flask import Flask

class StorageService:
    """Firebase Storage 관련 로직을 담당하는 범용 서비스 클래스"""

    def __init__(self):
        """
        클래스 인스턴스 생성 시 버킷을 None으로 초기화합니다.
        """
        self.bucket = None

    def init_app(self, app: Flask):
        """
        Flask 앱 초기화 과정에서 호출되어 Storage 버킷을 설정합니다.
        
        :param app: Flask 애플리케이션 객체
        """
        bucket_name = app.config.get('FIREBASE_STORAGE_BUCKET')
        if not bucket_name:
            raise ValueError("FIREBASE_STORAGE_BUCKET 설정이 .env 또는 설정 파일에 필요합니다.")
        self.bucket = storage.bucket(bucket_name)
        print("StorageService: Firebase Storage 서비스 초기화 완료.")

    def upload_image(self, folder_path: str, image_bytes: bytes, content_type: str = 'image/jpeg') -> str:
        """
        이미지를 지정된 폴더 경로에 고유한 파일 이름으로 업로드하고 공개 URL을 반환합니다.

        :param folder_path: 이미지를 저장할 폴더 경로 (예: 'user_profiles', 'nose_prints/user123')
        :param image_bytes: 이미지 파일의 raw bytes
        :param content_type: 업로드할 파일의 MIME 타입
        :return: 업로드된 이미지의 공개 URL
        """
        if not self.bucket:
            raise RuntimeError("StorageService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")
            
        # UUID와 타임스탬프를 조합하여 고유한 파일 이름을 생성합니다.
        file_name = f"{uuid.uuid4()}_{int(time.time())}.jpg"
        destination_blob_name = f"{folder_path}/{file_name}"
        
        blob = self.bucket.blob(destination_blob_name)
        
        # 바이트 데이터를 메모리에서 직접 업로드합니다.
        blob.upload_from_string(
            image_bytes,
            content_type=content_type
        )
        
        # 외부에서 접근 가능하도록 파일을 공개로 설정합니다.
        blob.make_public()
        
        print(f"StorageService: 이미지 업로드 성공. URL: {blob.public_url}")
        return blob.public_url
