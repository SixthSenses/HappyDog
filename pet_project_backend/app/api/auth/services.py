# app/api/auth/services.py
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from dataclasses import asdict
from firebase_admin import firestore, auth as firebase_auth
from flask import Flask
from app.models.user import User
from dataclasses import fields as dataclass_fields
from app.utils.datetime_utils import DateTimeUtils, for_firestore

class AuthService:
    def __init__(self, db_client=None):
        self.db = db_client
        if self.db is None:
            self.users_ref = None
            self.revoked_tokens_ref = None
        else:
            self.users_ref = self.db.collection('users')
            self.revoked_tokens_ref = self.db.collection('revoked_tokens')
        self.app: Optional[Flask] = None

    def init_app(self, app: Flask):
        """앱 초기화 과정에서 호출되어 JWT 콜백만 등록합니다 (DI된 db 사용)."""
        self.app = app
        if self.db is not None:
            self._register_jwt_callbacks(app)
            logging.info("AuthService initialized with injected Firestore client and JWT integration")
        else:
            logging.info("AuthService initialized without Firestore client (no-op for persistence)")

    def _register_jwt_callbacks(self, app: Flask):
        """Register JWT token blocklist callbacks with Flask-JWT-Extended."""
        try:
            from flask_jwt_extended import JWTManager
            jwt_manager = app.extensions.get('flask-jwt-extended')
            if jwt_manager:
                # Register token revocation check callback
                @jwt_manager.token_in_blocklist_loader
                def check_if_token_revoked(jwt_header, jwt_payload):
                    return self.is_token_revoked(jwt_payload)
                logging.info("JWT token blocklist callback registered successfully")
        except ImportError:
            logging.warning("Flask-JWT-Extended not available for token blocklist integration")
        except Exception as e:
            logging.error(f"Failed to register JWT callbacks: {e}")

    def get_or_create_user_by_google(self, google_user_info: dict) -> Tuple[User, bool]:
        google_id = google_user_info.get('sub')
        if not google_id:
            raise ValueError("Google user info must contain 'sub' (google_id).")
        if self.users_ref is None:
            # Return synthetic user (not persisted) in docs mode / no DB context
            synthetic_user = User(
                user_id=str(uuid.uuid4()),
                google_id=google_id,
                email=google_user_info.get('email'),
                nickname=google_user_info.get('name'),
                join_date=DateTimeUtils.now(),
                notification_unread_count=0
            )
            return synthetic_user, True
        query = self.users_ref.where('google_id', '==', google_id).limit(1).stream()
        user_doc = next(query, None)

        if user_doc:
            is_new_user = False
            user_data = user_doc.to_dict() or {}
            # User 데이터클래스에 정의된 필드만 선별 (예상치 못한 필드로 인한 __init__ 오류 방지)
            allowed = {f.name for f in dataclass_fields(User)}
            filtered = {k: v for k, v in user_data.items() if k in allowed}
            # 누락 가능 기본 필드 보정
            if 'notification_unread_count' not in filtered:
                filtered['notification_unread_count'] = 0
            user = User(**filtered)
            return user, is_new_user
        else:
            is_new_user = True
            user_id = str(uuid.uuid4())
            new_user = User(
                user_id=user_id,
                google_id=google_id,
                email=google_user_info.get('email'),
                nickname=google_user_info.get('name'),
                join_date=DateTimeUtils.now()
            )
            # Firestore 호환 변환 후 저장
            user_data = DateTimeUtils.for_firestore(asdict(new_user))
            self.users_ref.document(user_id).set(user_data)
            return new_user, is_new_user

    # --- Blocklist 관련 로직 ---
    def add_token_to_blocklist(self, jti: str, expires: datetime):
        """전달받은 토큰의 jti를 만료 시간과 함께 Firestore에 저장합니다."""
        if self.revoked_tokens_ref is None:
            return
        try:
            token_data = {
                'revoked_at': DateTimeUtils.now(),
                'expires_at': expires
            }
            token_data = DateTimeUtils.for_firestore(token_data)
            self.revoked_tokens_ref.document(jti).set(token_data)
        except Exception as e:
            logging.error(f"Blocklist 토큰 추가 실패 (jti: {jti}): {e}")


    def is_token_revoked(self, jwt_payload: dict) -> bool:
        """jti를 이용해 해당 토큰이 무효화 목록에 있는지 확인합니다."""
        jti = jwt_payload['jti']
        if self.revoked_tokens_ref is None:
            return False
        doc = self.revoked_tokens_ref.document(jti).get()
        return doc.exists

    def logout_user(self, access_jti: str, access_exp: int, refresh_jti: str, refresh_exp: int):
        """Access 토큰과 Refresh 토큰을 모두 Blocklist에 추가합니다."""
        access_expires = datetime.fromtimestamp(access_exp)
        refresh_expires = datetime.fromtimestamp(refresh_exp)
        self.add_token_to_blocklist(access_jti, access_expires)
        self.add_token_to_blocklist(refresh_jti, refresh_expires)
        logging.info(f"사용자 로그아웃 처리 완료. JTI: {access_jti[:8]}..., {refresh_jti[:8]}...")

    # update_profile_image 메소드 제거됨 - 프로필 이미지는 Pet 테이블에서 관리

    # --- 회원 탈퇴 로직 ---
    def delete_user_account(self, user_id: str):
        """Firebase Auth에서 사용자를 삭제합니다. (나머지는 Extension이 처리)"""
        try:
            firebase_auth.delete_user(user_id)
            logging.info(f"Firebase Auth 사용자 삭제 성공 (user_id: {user_id}). Firestore/Storage 데이터는 Extension에 의해 삭제됩니다.")
        except firebase_auth.UserNotFoundError:
            logging.warning(f"Firebase Auth에서 이미 삭제된 사용자입니다 (user_id: {user_id}).")
            # 이미 없는 사용자이므로 성공으로 간주할 수 있습니다.
            pass
        except Exception as e:
            logging.error(f"회원 탈퇴 처리 중 Firebase Auth 사용자 삭제 실패 (user_id: {user_id}): {e}")
            # 이 경우, DB나 Storage의 데이터가 남을 수 있으므로 심각한 오류입니다.
            raise

# ❌ Remove singleton pattern - services should be registered in DI container
# auth_service = AuthService()