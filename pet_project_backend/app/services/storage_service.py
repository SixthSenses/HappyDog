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
        # app.config에서 버킷 이름을 가져옵니다. 이 값은 .env 파일에 정의되어야 합니다.
        bucket_name = app.config.get('FIREBASE_STORAGE_BUCKET')
        if not bucket_name:
            raise ValueError("FIREBASE_STORAGE_BUCKET 설정이 .env 또는 설정 파일에 필요합니다.")
        
        # Firebase Admin SDK를 통해 기본 스토리지 버킷에 대한 참조를 가져옵니다.
        self.bucket = storage.bucket(bucket_name)
        logging.info("StorageService: Firebase Storage 서비스가 성공적으로 초기화되었습니다.")

    def generate_upload_url(self, user_id: str, upload_type: str, filename: str, content_type: str) -> dict:
        """
        파일 타입에 따라 적절한 경로에 업로드할 수 있는 Pre-signed URL을 생성합니다.
        클라이언트는 이 URL을 사용하여 서버를 거치지 않고 Firebase Storage에 직접 파일을 업로드(PUT)할 수 있습니다.

        :param user_id: JWT에서 추출한 현재 로그인된 사용자의 고유 ID
        :param upload_type: 업로드 목적을 나타내는 문자열 (예: "pet_profile", "pet_nose_print")
        :param filename: 클라이언트가 업로드할 원본 파일명 (확장자 파악에 사용)
        :param content_type: 업로드할 파일의 MIME 타입 (예: "image/jpeg")
        :return: 업로드 URL과 서버에서 사용할 파일 경로가 담긴 딕셔너리
        """
        if not self.bucket:
            raise RuntimeError("StorageService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")

        # 'upload_type'에 따라 파일이 저장될 폴더 경로를 매핑합니다.
        # 새로운 파일 업로드 기능이 추가될 때마다 이 딕셔너리에 항목을 추가하면 됩니다.
        path_map = {
            # 사용자 프로필 이미지는 pet_profiles/{user_id}/ 경로에 저장됩니다.
            "user_profile": f"user_profiles/{user_id}",
            
            # 비문 이미지는 ML 분석 전 임시로 nose_prints_staging/{user_id}/ 경로에 저장됩니다.
            "pet_nose_print": f"nose_prints_staging/{user_id}",
            
            # '멍스타그램' 게시물 이미지는 posts/{user_id}/ 경로에 저장됩니다.
            "post_image": f"posts/{user_id}",
        }

        folder_path = path_map.get(upload_type)
        if not folder_path:
            # path_map에 정의되지 않은 upload_type이 들어오면 에러를 발생시킵니다.
            raise ValueError(f"'{upload_type}'은(는) 유효한 업로드 타입이 아닙니다.")

        # 파일명 중복을 피하기 위해 UUID로 고유한 파일 이름을 생성합니다.
        # 원본 파일의 확장자는 유지합니다.
        extension = filename.split('.')[-1] if '.' in filename else ''
        unique_filename = f"{uuid.uuid4()}.{extension}"
        
        # 최종적으로 파일이 저장될 전체 경로입니다. (예: "posts/user123/abc-def.jpg")
        destination_blob_name = f"{folder_path}/{unique_filename}"

        # Storage에서 해당 경로의 blob(파일) 객체에 대한 참조를 만듭니다.
        blob = self.bucket.blob(destination_blob_name)

        # 15분 동안 유효한 업로드 전용 URL을 생성합니다.
        # 클라이언트는 반드시 'PUT' HTTP 메서드를 사용해야 합니다.
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type=content_type # 클라이언트가 보내는 Content-Type과 일치해야 합니다.
        )

        # 클라이언트와 서버에 필요한 정보를 딕셔너리 형태로 반환합니다.
        return {
            "upload_url": upload_url,          # 클라이언트가 파일 업로드에 사용할 URL
            "file_path": destination_blob_name # 업로드 완료 후, 서버에 알려줄 파일의 최종 경로
        }
