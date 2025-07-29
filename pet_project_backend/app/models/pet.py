#예시코드입니다

from dataclasses import dataclass, asdict
from datetime import date

@dataclass
class Pet:
    """
    Firestore의 'pets' 컬렉션 문서 구조를 정의하는 데이터 클래스.
    """
    id: str
    owner_id: str
    name: str
    breed: str
    birth_date: date
    
    def to_dict(self):
        """데이터 클래스 인스턴스를 Firestore 저장용 딕셔너리로 변환"""
        # asdict는 dataclass를 dict로 변환해주는 헬퍼 함수
        # 날짜 객체는 문자열로 변환해야 함
        data = asdict(self)
        data['birth_date'] = self.birth_date.isoformat()
        return data