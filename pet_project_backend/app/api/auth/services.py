from firebase_admin import firestore
from app.models.user import User

db = firestore.client()

def get_or_create_user_from_google(id_info: dict) -> User:
    """
    Google 사용자 정보로 Firestore에서 사용자를 찾거나 생성합니다.
    
    Args:
        id_info: Google id_token.verify_oauth2_token()을 통해 받은 사용자 정보 딕셔너리.

    Returns:
        생성되거나 조회된 User 데이터 클래스 인스턴스.
    """
    users_ref = db.collection('users')
    google_id = id_info.get('sub') # 'sub'는 Google의 고유 사용자 ID입니다.

    # 1. google_id로 기존 사용자 조회
    docs = users_ref.where('google_id', '==', google_id).limit(1).stream()
    existing_user_doc = next(docs, None)

    if existing_user_doc:
        # 2. 사용자가 존재하면 User 객체로 변환하여 반환
        user_data = existing_user_doc.to_dict()
        user = User(
            id=existing_user_doc.id,
            google_id=user_data.get('google_id'),
            email=user_data.get('email'),
            name=user_data.get('name'),
            picture=user_data.get('picture'),
            created_at=user_data.get('created_at')
        )
        return user
    else:
        # 3. 사용자가 없으면 새로 생성
        new_user_data = {
            'google_id': google_id,
            'email': id_info.get('email'),
            'name': id_info.get('name'),
            'picture': id_info.get('picture'),
            'created_at': firestore.SERVER_TIMESTAMP, # 서버 시간으로 기록
        }
        
        # Firestore에 새 사용자 문서 추가
        update_time, new_user_ref = users_ref.add(new_user_data)
        
        # 4. 생성된 사용자 정보를 User 객체로 변환하여 반환
        created_user = User(
            id=new_user_ref.id,
            **new_user_data
        )
        # created_at 필드는 서버에서 생성되므로 None으로 남겨둘 수 있습니다.
        # 필요하다면 new_user_ref.get()으로 다시 조회하여 채울 수 있습니다.
        created_user.created_at = None 
        return created_user