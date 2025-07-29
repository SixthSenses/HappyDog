# app/services/firebase_service.py

import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import settings

# Firebase Admin SDK 초기화
# 이미 초기화된 경우를 대비하여 예외 처리를 합니다.
try:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
except ValueError:
    pass # 이미 초기화되었을 경우 무시

db = firestore.client()

def get_or_create_user_by_social(user_info: dict) -> dict:
    # """
    # 소셜 로그인 정보로 사용자를 찾거나 생성합니다.
    # :param user_info: 구글 서버로부터 받은 사용자 정보 딕셔너리
    # :return: 우리 서비스의 사용자 프로필 정보 (DB 문서 ID 포함)
    # """
    users_ref = db.collection('users')
    google_id = user_info.get('sub') # 구글의 고유 사용자 ID

    # google_id로 기존 사용자를 검색합니다.
    docs = users_ref.where('google_id', '==', google_id).limit(1).stream()
    
    existing_user = next(docs, None)

    if existing_user:
        # 사용자가 존재하면 해당 사용자 정보를 반환합니다.
        user_data = existing_user.to_dict()
        user_data['user_id'] = existing_user.id # Firestore 문서 ID를 user_id로 추가
        return user_data
    else:
        # 사용자가 없으면 새로 생성합니다.
        new_user_data = {
            'google_id': google_id,
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'created_at': firestore.SERVER_TIMESTAMP,
        }
        # Firestore에 새 사용자 문서를 추가합니다.
        update_time, new_user_ref = users_ref.add(new_user_data)
        
        # 생성된 사용자 정보를 반환합니다.
        created_user = new_user_ref.get().to_dict()
        created_user['user_id'] = new_user_ref.id # 문서 ID를 user_id로 추가
        return created_user
    
    
    
# Firebase 초기화: 앱이 시작될 때 한 번만 실행되도록 try...except 블록으로 감쌌습니다.

# get_or_create_user_by_social:

# 구글이 제공하는 고유 ID인 sub 필드를 google_id로 사용하여 사용자를 식별합니다.

# users 컬렉션에서 google_id가 일치하는 문서를 조회합니다.

# 사용자가 있으면, 문서 데이터를 반환합니다. 이때 Firestore 문서의 고유 ID를 user_id라는 키로 추가하여 반환하는 것이 중요합니다. 이 ID가 우리 서비스의 내부 사용자 ID가 됩니다.

# 사용자가 없으면, user_info를 기반으로 새 문서를 생성하고, 생성된 문서의 정보와 ID를 user_id로 추가하여 반환합니다.