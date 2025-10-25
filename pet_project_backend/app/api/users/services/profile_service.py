# app/api/users/services/profile_service.py
import logging
from typing import Optional, Dict, Any
from firebase_admin import firestore
from app.services.storage_interfaces import StorageUrlProvider


class UserProfileService:
    """
    사용자 프로필 관련 비즈니스 로직을 담당하는 서비스 클래스.
    프로필 이미지, 기본 사용자 정보 관리에 집중합니다.
    """
    
    def __init__(self, storage_service: StorageUrlProvider, db_client=None):
        """Initialize service with optional injected Firestore client."""
        self.db = db_client
        self.users_ref = self.db.collection('users') if self.db else None
        self.storage_service = storage_service
        if self.db is None:
            logging.info("UserProfileService initialized without Firestore client (docs mode or disabled persistence)")
        
    def init_app(self, app):
        """Flask 앱 초기화"""
        self.app = app
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        사용자 ID로 기본 프로필 정보를 조회합니다.
        :param user_id: 조회할 사용자의 고유 ID
        :return: 사용자 데이터 딕셔너리 또는 None
        """
        if self.users_ref is None:
            return None
        try:
            user_doc = self.users_ref.document(user_id).get()
            if not user_doc.exists:
                return None
            return user_doc.to_dict()
        except Exception as e:
            logging.error(f"사용자 프로필 조회 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        사용자 ID로 Firestore에서 사용자 문서를 찾아 딕셔너리로 반환합니다.
        :param user_id: 조회할 사용자의 고유 ID
        :return: 사용자 데이터 딕셔너리 또는 None
        """
        if self.users_ref is None:
            return None
        try:
            doc = self.users_ref.document(user_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logging.error(f"ID로 사용자 조회 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    # update_user_profile_image 메소드 제거됨 - 프로필 이미지는 Pet 테이블에서 관리

    def get_notification_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """사용자의 알림 개인 설정을 조회합니다."""
        if self.users_ref is None:
            return None
        try:
            doc = self.users_ref.document(user_id).get()
            if not doc.exists:
                return None
            data = doc.to_dict()
            return data.get('notification_preferences')
        except Exception as e:
            logging.error(f"알림 설정 조회 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def update_notification_preferences(self, user_id: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """사용자의 알림 개인 설정을 저장/업데이트합니다."""
        if self.users_ref is None:
            return preferences
        try:
            ref = self.users_ref.document(user_id)
            ref.update({"notification_preferences": preferences})
            return ref.get().to_dict().get('notification_preferences', {})
        except Exception as e:
            logging.error(f"알림 설정 업데이트 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def update_fcm_token(self, user_id: str, fcm_token: str) -> None:
        """
        사용자의 FCM 토큰을 Firestore에 저장하거나 업데이트합니다.
        :param user_id: FCM 토큰을 업데이트할 사용자 ID
        :param fcm_token: 클라이언트로부터 받은 새로운 FCM 토큰
        """
        if self.users_ref is None:
            logging.info("UserProfileService: DOCS_MODE - update_fcm_token skipped")
            return
        try:
            self.users_ref.document(user_id).update({"fcm_token": fcm_token})
            logging.info(f"FCM 토큰 업데이트 완료 (user_id: {user_id})")
        except Exception as e:
            logging.error(f"FCM 토큰 업데이트 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise
