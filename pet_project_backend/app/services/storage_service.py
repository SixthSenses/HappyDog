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

    def __init__(self, bucket=None):
        """Optionally inject an existing storage bucket. When bucket is None the
        service operates in a no-op/docs mode and raises on operations that require storage.
        """
        self.bucket = bucket

    def init_app(self, app: Flask):
        """Optionally initialize bucket from app config if not already injected."""
        if self.bucket is not None:
            return
        bucket_name = app.config.get('FIREBASE_STORAGE_BUCKET')
        if not bucket_name:
            logging.info("StorageService: No bucket configured (treated as docs-mode/no-op).")
            return
        try:
            self.bucket = storage.bucket(bucket_name)
            logging.info("StorageService: Firebase Storage initialized (bucket acquired).")
        except Exception as e:
            logging.warning(f"StorageService: bucket initialization failed, operating in no-op mode: {e}")
            self.bucket = None

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
            "pet_profile": f"pet_profiles/{user_id}",  # Pet 프로필 이미지용 (User 프로필은 Pet에서 관리)
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

    def download_as_bytes(self, file_path: str) -> bytes:
        """
        Firebase Storage에서 파일을 바이트로 다운로드합니다.
        
        :param file_path: 다운로드할 파일의 경로
        :return: 파일의 바이트 데이터
        """
        if not self.bucket:
            raise RuntimeError("StorageService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")
            
        blob = self.bucket.blob(file_path)
        
        if not blob.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
            
        try:
            return blob.download_as_bytes()
        except Exception as e:
            logging.error(f"파일 다운로드 실패: {e}", exc_info=True)
            raise



    def promote_object(self, source_path: str, dest_path: str, delete_source: bool = True) -> None:
        """Copy a blob to a new destination (promotion) and optionally delete source.

        Used for promoting biometric artifacts from staging to verified.
        """
        if not self.bucket:
            raise RuntimeError("StorageService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")
        source_blob = self.bucket.blob(source_path)
        if not source_blob.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {source_path}")
        dest_blob = self.bucket.blob(dest_path)
        self.bucket.copy_blob(source_blob, self.bucket, new_name=dest_path)
        if delete_source:
            try:
                source_blob.delete()
            except Exception as e:  # non-fatal
                logging.warning(f"원본 삭제 실패(무시): {e}")

    def get_public_url(self, file_path: str) -> str:
        """
        파일 경로를 Firebase 다운로드 토큰이 포함된 공개 URL로 변환합니다.
        
        Firebase Storage는 업로드 시 자동으로 download token을 생성하며,
        이 메서드는 해당 토큰을 포함한 공개 접근 가능한 URL을 반환합니다.
        
        :param file_path: Storage 파일 경로 (상대 경로)
        :return: 공개 접근 가능한 Firebase Storage URL (토큰 포함)
        :raises FileNotFoundError: 파일이 존재하지 않는 경우
        :raises RuntimeError: Storage가 초기화되지 않은 경우
        """
        if not self.bucket:
            raise RuntimeError("StorageService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")
        
        blob = self.bucket.blob(file_path)
        
        # 파일 존재 여부 확인
        if not blob.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        # 메타데이터에서 다운로드 토큰 추출
        blob.reload()  # 메타데이터 최신화
        metadata = blob.metadata or {}
        download_token = metadata.get('firebaseStorageDownloadTokens')
        
        if not download_token:
            # 토큰이 없으면 새로 생성하여 설정
            import uuid
            download_token = str(uuid.uuid4())
            blob.metadata = metadata
            blob.metadata['firebaseStorageDownloadTokens'] = download_token
            try:
                blob.patch()  # 메타데이터만 업데이트
                logging.info(f"다운로드 토큰 생성 및 설정 완료: {file_path}")
            except Exception as e:
                logging.error(f"다운로드 토큰 설정 실패: {e}. Fallback to signed URL.")
                # Fallback: signed URL 생성 (시간 제한 있음)
                return blob.generate_signed_url(version="v4", expiration=timedelta(days=7), method="GET")
        
        # Firebase Storage 공개 URL 생성 (토큰 포함)
        from urllib.parse import quote
        bucket_name = self.bucket.name
        encoded_path = quote(file_path, safe='')
        
        # Firebase Storage의 공개 다운로드 URL 형식
        # https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{encodedPath}?alt=media&token={token}
        firebase_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded_path}?alt=media&token={download_token}"
        
        return firebase_url

    def get_signed_url(self, file_path: str, expiration_hours: int = 1, method: str = "GET") -> str:
        """
        파일에 대한 Signed URL을 생성합니다.
        OpenAI 등 외부 서비스가 Firebase Storage에 직접 접근할 수 있도록 합니다.
        
        다운로드 토큰 방식(`get_public_url`)과 달리, Signed URL은:
        - Firebase Security Rules에 관계없이 임시 접근 허용
        - OpenAI, 외부 API 서버가 직접 파일 접근 가능
        - 만료 시간 지정 가능 (기본 1시간)
        
        :param file_path: Storage 파일 경로 (상대 경로)
        :param expiration_hours: URL 만료 시간 (시간 단위, 기본 1시간)
        :param method: HTTP 메서드 (기본 "GET")
        :return: Signed URL
        :raises FileNotFoundError: 파일이 존재하지 않는 경우
        :raises RuntimeError: Storage가 초기화되지 않은 경우
        """
        if not self.bucket:
            raise RuntimeError("StorageService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")
        
        blob = self.bucket.blob(file_path)
        
        # 파일 존재 여부 확인
        if not blob.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        # Signed URL 생성
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=expiration_hours),
            method=method
        )
        
        logging.info(f"Signed URL 생성 완료: {file_path} (만료: {expiration_hours}시간)")
        return signed_url
    
