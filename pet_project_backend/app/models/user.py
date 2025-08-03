#app/models/user.py

from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class User:
    """사용자 데이터 구조를 정의하는 데이터클래스."""
    # user_id: 우리 서비스의 내부 고유 ID. Firestore 문서 ID와 동일하게 사용됩니다.
    user_id: str
    
    # google_id: Google이 제공하는 불변의 고유 사용자 ID(sub). 사용자를 찾는 유일한 키입니다.
    google_id: str
    
    # email: 사용자의 Google 계정 이메일 주소입니다.
    email: str
    
    # nickname: 서비스 내에서 사용될 이름. Google 계정 이름으로 초기화됩니다.
    nickname: str
    
    # join_date: 사용자가 서비스에 처음 가입한 시각입니다.
    join_date: datetime = field(default_factory=datetime.now)