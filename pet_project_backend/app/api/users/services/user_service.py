# app/api/users/services/user_service.py
import logging
from typing import Optional, Dict, Any
from firebase_admin import auth as firebase_auth


class UserService:
    """
    핵심 사용자 관리 로직을 담당하는 서비스 클래스.
    인증 관련 작업, 계정 삭제 등 핵심 사용자 관리에 집중합니다.
    프로필 관리와 통계 정보는 각각 UserProfileService와 UserStatsService에서 처리합니다.
    """
    
    def __init__(self):
        """서비스 초기화 - 외부 서비스 의존성 제거"""
        pass
        
    def init_app(self, app):
        """Flask 앱 초기화"""
        self.app = app
    
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


# 서비스 인스턴스는 app/__init__.py에서 생성되어 주입됩니다.
user_service: Optional[UserService] = None
