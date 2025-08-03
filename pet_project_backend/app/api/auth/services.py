#app/api/auth/services.py
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple
from dataclasses import asdict
from firebase_admin import firestore
from app.models.user import User

class AuthService:
    def __init__(self):
        # __init__에서는 아무것도 하지 않고 비워둡니다.
        self.db = None
        self.users_ref = None

    def init_app(self):
        """
        app 초기화가 끝난 후 호출되어 실제 DB 연결을 수행합니다.
        """
        self.db = firestore.client()
        self.users_ref = self.db.collection('users')

    def get_or_create_user_by_google(self, google_user_info: dict):
        
        google_id = google_user_info.get('sub')
        if not google_id:
            raise ValueError("Google user info must contain 'sub' (google_id).")

        # Firestore에서 google_id가 일치하는 사용자를 찾습니다.
        query = self.users_ref.where('google_id', '==', google_id).limit(1).stream()
        # user_doc: 쿼리 결과로 찾은 Firestore 문서 스냅샷입니다. 없으면 None입니다.
        user_doc = next(query, None)

        if user_doc:
            # 기존 사용자인 경우
            # is_new_user: 신규 사용자 여부를 나타내는 플래그입니다.
            is_new_user = False
            # user_data: Firestore 문서에서 가져온 사용자 데이터 딕셔너리입니다.
            user_data = user_doc.to_dict()
            # user: user_data를 기반으로 생성된 User 데이터클래스 객체입니다.
            user = User(**user_data)
            return user, is_new_user
        else:
            # 신규 사용자인 경우
            is_new_user = True
            # user_id: 우리 서비스에서 사용할 새로운 고유 ID를 UUID로 생성합니다.
            user_id = str(uuid.uuid4())
            # new_user: 새로 생성할 User 데이터클래스 객체입니다.
            new_user = User(
                user_id=user_id,
                google_id=google_id,
                email=google_user_info.get('email'),
                nickname=google_user_info.get('name'),
                join_date=datetime.now()
            )
            # Firestore에 user_id를 문서 ID로 하여 새로운 사용자 정보를 저장합니다.
            self.users_ref.document(user_id).set(asdict(new_user))
            return new_user, is_new_user
auth_service = AuthService()