# app/api/users/services.py
import logging
from typing import Optional, Dict, Any
from firebase_admin import firestore, auth as firebase_auth
from app.services.storage_service import StorageService
from app.api.posts.services import PostService 
class UserService:
    """
    사용자 관련 비즈니스 로직을 담당하는 서비스 클래스.
    - 다른 서비스와의 결합도를 낮추기 위해 DB 컬렉션을 직접 참조합니다.
    - StorageService와 같은 공용 서비스는 의존성 주입을 통해 받습니다.
    """
    def __init__(self, storage_service: StorageService, post_service: PostService):
        """
        서비스 초기화 시 의존성 주입을 통해 필요한 서비스를 받습니다.
        :param storage_service: Storage 관련 작업을 처리하는 서비스
        """
        self.db = firestore.client()
        self.users_ref = self.db.collection('users')
        self.storage_service = storage_service
        self.post_service = post_service
        
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        사용자 ID로 공개 프로필 정보와 총 게시물 수를 함께 조회합니다.
        :param user_id: 조회할 사용자의 고유 ID
        :return: 사용자 데이터와 post_count가 포함된 딕셔너리 또는 None
        """
        try:
            user_doc = self.users_ref.document(user_id).get()
            if not user_doc.exists:
                return None
            
            user_data = user_doc.to_dict()
            
            # 주입받은 PostService를 사용해 총 게시물 수를 가져옵니다.
            post_count = self.post_service.count_posts_by_user_id(user_id)
            user_data['post_count'] = post_count
            
            return user_data
        except Exception as e:
            logging.error(f"사용자 프로필 조회 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        사용자 ID로 Firestore에서 사용자 문서를 찾아 딕셔너리로 반환합니다.
        :param user_id: 조회할 사용자의 고유 ID
        :return: 사용자 데이터 딕셔너리 또는 None
        """
        try:
            doc = self.users_ref.document(user_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logging.error(f"ID로 사용자 조회 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def update_user_profile_image(self, user_id: str, file_path: str) -> Optional[Dict[str, Any]]:
        """
        사용자의 프로필 이미지 URL을 업데이트합니다.
        :param user_id: 프로필 이미지를 업데이트할 사용자 ID
        :param file_path: Firebase Storage에 업로드된 파일의 경로
        :return: 업데이트된 사용자 정보 딕셔너리 또는 None
        """
        try:
            # 1. Storage 파일 경로를 공개 URL로 변환
            blob = self.storage_service.bucket.blob(file_path)
            if not blob.exists():
                logging.warning(f"Storage에서 파일을 찾을 수 없음: {file_path} (user_id: {user_id})")
                raise FileNotFoundError("스토리지에서 해당 파일을 찾을 수 없습니다.")
            
            blob.make_public()
            public_url = blob.public_url

            # 2. Firestore 사용자 문서 업데이트
            user_ref = self.users_ref.document(user_id)
            user_ref.update({'profile_image_url': public_url})
            
            updated_doc = user_ref.get()
            return updated_doc.to_dict() if updated_doc.exists else None
        except Exception as e:
            logging.error(f"프로필 이미지 업데이트 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def delete_user_account(self, user_id: str) -> None:
        """
        Firebase Authentication에서 사용자를 삭제합니다.
        Firestore 데이터는 'Delete User Data' Firebase Extension에 의해 자동으로 처리됩니다.
        :param user_id: 삭제할 사용자의 ID
        """
        try:
            firebase_auth.delete_user(user_id)
            logging.info(f"Firebase Auth 사용자 삭제 성공 (user_id: {user_id}).")
        except firebase_auth.UserNotFoundError:
            logging.warning(f"Firebase Auth에서 이미 삭제된 사용자입니다 (user_id: {user_id}).")
            # 이미 없는 사용자이므로 오류를 발생시키지 않고 넘어갑니다.
            pass
        except Exception as e:
            logging.error(f"회원 탈퇴 처리 중 Firebase Auth 사용자 삭제 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def update_fcm_token(self, user_id: str, fcm_token: str) -> None:
        """
        사용자의 FCM 토큰을 Firestore에 저장하거나 업데이트합니다.
        :param user_id: FCM 토큰을 업데이트할 사용자 ID
        :param fcm_token: 클라이언트로부터 받은 새로운 FCM 토큰
        """
        try:
            self.users_ref.document(user_id).update({"fcm_token": fcm_token})
            logging.info(f"FCM 토큰 업데이트 완료 (user_id: {user_id})")
        except Exception as e:
            logging.error(f"FCM 토큰 업데이트 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

# 서비스 인스턴스는 app/__init__.py에서 생성되어 주입됩니다.
user_service: Optional[UserService] = None