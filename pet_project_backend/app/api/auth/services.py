from firebase_admin import firestore
from app.models.user import User

db = firestore.client()

def get_or_create_user_from_google(id_info: dict) -> tuple[User, bool]:
    """
    Google 사용자 정보로 Firestore에서 사용자를 찾거나 생성합니다.

    Args:
        id_info: Google id_token.verify_oauth2_token()을 통해 받은 사용자 정보.

    Returns:
        A tuple containing:
        - User: The created or retrieved User dataclass instance.
        - bool: True if the user was newly created, False otherwise.
    """
    users_ref = db.collection('users')
    google_id = id_info.get('sub') # Google의 고유 사용자 ID
    user_email = id_info.get('email')

    # google_id로 기존 사용자 조회
    query = users_ref.where('google_id', '==', google_id).limit(1)
    results = query.stream()
    existing_user_doc = next(results, None)

    if existing_user_doc:
        # 사용자가 존재하면 User 객체로 변환하여 반환
        user_data = existing_user_doc.to_dict()
        user = User(id=existing_user_doc.id, **user_data)
        return user, False # (기존 유저, is_new_user=False)
    else:
        # 사용자가 없으면 새로 생성
        new_user_data = {
            'google_id': google_id,
            'email': user_email,
            'name': id_info.get('name'),
            'picture': id_info.get('picture'),
            'created_at': firestore.SERVER_TIMESTAMP,
        }
        
        # Firestore에 새 사용자 문서 추가
        update_time, new_user_ref = users_ref.add(new_user_data)
        
        # 생성된 사용자 정보를 User 객체로 변환하여 반환
        created_user_data = new_user_ref.get().to_dict()
        created_user = User(id=new_user_ref.id, **created_user_data)

        return created_user, True # (신규 유저, is_new_user=True)
