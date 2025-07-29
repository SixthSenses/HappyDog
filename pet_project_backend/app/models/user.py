#예시 코드입니다.
#회원가입시 어떤값을 받을건지에따라 수정될예정입니다. 
# 수정시 pet_project_backend\app\api\auth\services.py의 get_or_create_user_from_google함수와
#pet_project_backend\app\schemas\user_schema.py 의 UserSchema도 수정되어야합니다.
from dataclasses import dataclass
from datetime import datetime

@dataclass
class User:
    """
    Firestore의 'users' 컬렉션 문서 구조를 정의하는 데이터 클래스.
    """
    id: str         # Firestore 문서 ID
    google_id: str  # Google에서 제공하는 고유 ID
    email: str
    name: str
    picture: str | None = None # 프로필 사진 URL (선택적)
    created_at: datetime | None = None # 생성 시간