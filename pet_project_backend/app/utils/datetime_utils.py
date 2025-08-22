# app/utils/datetime_utils.py
"""
프로젝트 전체에서 일관된 시간/날짜 처리를 위한 중앙화된 유틸리티 모듈

이 모듈의 목적:
1. 모든 시간 관련 작업을 표준화
2. Firestore 호환성 보장 
3. Timezone 처리 일관성 확보
4. ISO 포맷 파싱/생성 통일
5. 오류 없는 날짜 변환 제공
"""

import logging
from datetime import datetime, date, timezone, time
from typing import Union, Optional, Any, Dict, List
from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

# 프로젝트 기본 timezone (KST)
KST = timezone.utc  # 백엔드는 UTC로 통일, 프론트엔드에서 현지 시간으로 변환

class DateTimeUtils:
    """시간/날짜 처리를 위한 중앙화된 유틸리티 클래스"""

    @staticmethod
    def now() -> datetime:
        """현재 시간을 UTC timezone-aware datetime으로 반환"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def today() -> date:
        """오늘 날짜를 반환"""
        return datetime.now(timezone.utc).date()
    
    @staticmethod
    def parse_iso_datetime(iso_string: str) -> datetime:
        """
        ISO 포맷 문자열을 datetime 객체로 파싱
        
        지원 포맷:
        - 2024-01-15T10:30:00Z
        - 2024-01-15T10:30:00+09:00
        - 2024-01-15T10:30:00.123456Z
        - 2024-01-15T10:30:00
        """
        try:
            if not iso_string:
                raise ValueError("빈 문자열은 파싱할 수 없습니다")
            
            # 'Z' 접미사 처리 (UTC 표시)
            if iso_string.endswith('Z'):
                iso_string = iso_string[:-1] + '+00:00'
            
            # dateutil.parser를 사용한 강력한 파싱
            dt = dateutil_parser.isoparse(iso_string)
            
            # timezone-naive인 경우 UTC로 가정
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            
            # 모든 datetime을 UTC로 정규화
            return dt.astimezone(timezone.utc)
            
        except Exception as e:
            logger.error(f"ISO datetime 파싱 실패: {iso_string} - {e}")
            raise ValueError(f"잘못된 ISO 날짜 형식입니다: {iso_string}")
    
    @staticmethod
    def parse_date_string(date_string: str) -> date:
        """
        날짜 문자열을 date 객체로 파싱
        
        지원 포맷:
        - 2024-01-15
        - 2024/01/15
        - 01-15-2024
        """
        try:
            if not date_string:
                raise ValueError("빈 문자열은 파싱할 수 없습니다")
                
            # dateutil.parser로 파싱 후 date 부분만 추출
            dt = dateutil_parser.parse(date_string)
            return dt.date()
            
        except Exception as e:
            logger.error(f"날짜 문자열 파싱 실패: {date_string} - {e}")
            raise ValueError(f"잘못된 날짜 형식입니다: {date_string}")
    
    @staticmethod
    def to_iso_string(dt: datetime) -> str:
        """datetime 객체를 ISO 포맷 문자열로 변환"""
        try:
            if dt.tzinfo is None:
                # timezone-naive인 경우 UTC로 가정
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                # UTC로 변환
                dt = dt.astimezone(timezone.utc)
            
            # ISO 포맷으로 변환 (Z 접미사 포함)
            return dt.isoformat().replace('+00:00', 'Z')
            
        except Exception as e:
            logger.error(f"ISO 문자열 변환 실패: {dt} - {e}")
            raise ValueError(f"datetime 객체를 ISO 문자열로 변환할 수 없습니다: {dt}")
    
    @staticmethod
    def to_date_string(d: date) -> str:
        """date 객체를 YYYY-MM-DD 형식 문자열로 변환"""
        try:
            return d.strftime('%Y-%m-%d')
        except Exception as e:
            logger.error(f"날짜 문자열 변환 실패: {d} - {e}")
            raise ValueError(f"date 객체를 문자열로 변환할 수 없습니다: {d}")
    
    @staticmethod
    def for_firestore(obj: Any) -> Any:
        """
        Firestore 저장을 위해 객체의 날짜/시간 필드를 변환
        
        변환 규칙:
        - date -> datetime (00:00:00 UTC)
        - timezone-naive datetime -> timezone-aware datetime (UTC)
        - dict/list 내부 재귀적 변환
        """
        try:
            if isinstance(obj, date) and not isinstance(obj, datetime):
                # date를 UTC datetime으로 변환
                return datetime.combine(obj, time.min).replace(tzinfo=timezone.utc)
            
            elif isinstance(obj, datetime):
                # timezone-naive인 경우 UTC로 설정
                if obj.tzinfo is None:
                    return obj.replace(tzinfo=timezone.utc)
                # 이미 timezone-aware인 경우 UTC로 변환
                return obj.astimezone(timezone.utc)
            
            elif isinstance(obj, dict):
                # dict 내부 재귀적 변환
                return {k: DateTimeUtils.for_firestore(v) for k, v in obj.items()}
            
            elif isinstance(obj, list):
                # list 내부 재귀적 변환
                return [DateTimeUtils.for_firestore(item) for item in obj]
            
            else:
                # 다른 타입은 그대로 반환
                return obj
                
        except Exception as e:
            logger.error(f"Firestore 변환 실패: {obj} ({type(obj)}) - {e}")
            raise ValueError(f"Firestore 호환 형식으로 변환할 수 없습니다: {obj}")
    
    @staticmethod
    def from_firestore(obj: Any) -> Any:
        """
        Firestore에서 읽은 데이터의 datetime 필드를 적절히 변환
        
        변환 규칙:
        - Firestore timestamp -> timezone-aware datetime (UTC)
        - dict/list 내부 재귀적 변환
        """
        try:
            # Firestore timestamp 객체 처리
            if hasattr(obj, 'timestamp'):
                # Firestore timestamp to datetime
                return datetime.fromtimestamp(obj.timestamp(), tz=timezone.utc)
            
            elif isinstance(obj, datetime):
                # 이미 datetime인 경우 timezone 확인
                if obj.tzinfo is None:
                    return obj.replace(tzinfo=timezone.utc)
                return obj.astimezone(timezone.utc)
            
            elif isinstance(obj, dict):
                # dict 내부 재귀적 변환
                return {k: DateTimeUtils.from_firestore(v) for k, v in obj.items()}
            
            elif isinstance(obj, list):
                # list 내부 재귀적 변환
                return [DateTimeUtils.from_firestore(item) for item in obj]
            
            else:
                # 다른 타입은 그대로 반환
                return obj
                
        except Exception as e:
            logger.error(f"Firestore 읽기 변환 실패: {obj} ({type(obj)}) - {e}")
            # 변환 실패 시 원본 객체 반환 (로그만 남김)
            return obj
    
    @staticmethod
    def calculate_age_months(birthdate: Union[date, datetime, str]) -> int:
        """생년월일로부터 나이를 월 단위로 계산"""
        try:
            # 문자열인 경우 파싱
            if isinstance(birthdate, str):
                birthdate = DateTimeUtils.parse_date_string(birthdate)
            
            # datetime인 경우 date로 변환
            elif isinstance(birthdate, datetime):
                birthdate = birthdate.date()
            
            today = DateTimeUtils.today()
            age_months = (today.year - birthdate.year) * 12 + (today.month - birthdate.month)
            
            return max(0, age_months)
            
        except Exception as e:
            logger.error(f"나이 계산 실패: {birthdate} - {e}")
            raise ValueError(f"나이를 계산할 수 없습니다: {birthdate}")
    
    @staticmethod
    def add_months(d: Union[date, datetime], months: int) -> Union[date, datetime]:
        """날짜에 월 수를 더함"""
        try:
            if isinstance(d, datetime):
                return d + relativedelta(months=months)
            else:
                return d + relativedelta(months=months)
        except Exception as e:
            logger.error(f"월 더하기 실패: {d} + {months}개월 - {e}")
            raise ValueError(f"날짜에 월을 더할 수 없습니다: {d}")
    
    @staticmethod
    def get_month_range(year: int, month: int) -> tuple[date, date]:
        """특정 년월의 첫째 날과 마지막 날을 반환"""
        try:
            start_date = date(year, month, 1)
            
            if month == 12:
                end_date = date(year + 1, 1, 1) - relativedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - relativedelta(days=1)
            
            return start_date, end_date
            
        except Exception as e:
            logger.error(f"월 범위 계산 실패: {year}-{month} - {e}")
            raise ValueError(f"월 범위를 계산할 수 없습니다: {year}-{month}")
    
    @staticmethod
    def is_same_day(dt1: Union[date, datetime], dt2: Union[date, datetime]) -> bool:
        """두 날짜가 같은 날인지 확인"""
        try:
            if isinstance(dt1, datetime):
                dt1 = dt1.date()
            if isinstance(dt2, datetime):
                dt2 = dt2.date()
            
            return dt1 == dt2
            
        except Exception as e:
            logger.error(f"날짜 비교 실패: {dt1} vs {dt2} - {e}")
            return False
    
    @staticmethod
    def validate_datetime_field(value: Any, field_name: str = "datetime") -> datetime:
        """
        API 요청에서 받은 datetime 값을 검증하고 변환
        
        Args:
            value: 검증할 값 (문자열, datetime 객체 등)
            field_name: 필드명 (오류 메시지용)
            
        Returns:
            검증된 timezone-aware datetime 객체
            
        Raises:
            ValueError: 잘못된 형식이거나 파싱할 수 없는 경우
        """
        try:
            if value is None:
                raise ValueError(f"{field_name}은 필수 필드입니다")
            
            if isinstance(value, str):
                return DateTimeUtils.parse_iso_datetime(value)
            
            elif isinstance(value, datetime):
                if value.tzinfo is None:
                    return value.replace(tzinfo=timezone.utc)
                return value.astimezone(timezone.utc)
            
            else:
                raise ValueError(f"{field_name}은 문자열 또는 datetime 객체여야 합니다")
                
        except Exception as e:
            logger.error(f"{field_name} 검증 실패: {value} - {e}")
            raise ValueError(f"잘못된 {field_name} 형식입니다: {value}")
    
    @staticmethod
    def validate_date_field(value: Any, field_name: str = "date") -> date:
        """
        API 요청에서 받은 date 값을 검증하고 변환
        
        Args:
            value: 검증할 값 (문자열, date 객체 등)
            field_name: 필드명 (오류 메시지용)
            
        Returns:
            검증된 date 객체
            
        Raises:
            ValueError: 잘못된 형식이거나 파싱할 수 없는 경우
        """
        try:
            if value is None:
                raise ValueError(f"{field_name}은 필수 필드입니다")
            
            if isinstance(value, str):
                return DateTimeUtils.parse_date_string(value)
            
            elif isinstance(value, date):
                return value
            
            elif isinstance(value, datetime):
                return value.date()
            
            else:
                raise ValueError(f"{field_name}은 문자열 또는 date/datetime 객체여야 합니다")
                
        except Exception as e:
            logger.error(f"{field_name} 검증 실패: {value} - {e}")
            raise ValueError(f"잘못된 {field_name} 형식입니다: {value}")

    @staticmethod
    def from_timestamp_ms(timestamp_ms: int) -> datetime:
        """
        Unix timestamp (밀리초)를 UTC datetime 객체로 변환
        
        Args:
            timestamp_ms: Unix timestamp in milliseconds
            
        Returns:
            UTC timezone-aware datetime 객체
        """
        try:
            if not isinstance(timestamp_ms, (int, float)):
                raise ValueError("timestamp_ms는 숫자여야 합니다")
            
            # 밀리초를 초로 변환하여 datetime 생성
            dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
            return dt
            
        except Exception as e:
            logger.error(f"timestamp_ms 변환 실패: {timestamp_ms} - {e}")
            raise ValueError(f"잘못된 timestamp 형식입니다: {timestamp_ms}")

    @staticmethod
    def to_timestamp_ms(dt: Union[datetime, Any]) -> int:
        """
        datetime 객체를 Unix timestamp (밀리초)로 변환
        
        Args:
            dt: datetime 객체 또는 Firestore timestamp
            
        Returns:
            Unix timestamp in milliseconds
        """
        try:
            # Firestore timestamp 객체 처리
            if hasattr(dt, 'timestamp'):
                return int(dt.timestamp() * 1000)
            
            # datetime 객체 처리
            elif isinstance(dt, datetime):
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return int(dt.timestamp() * 1000)
            
            else:
                raise ValueError(f"datetime 객체 또는 Firestore timestamp여야 합니다: {type(dt)}")
                
        except Exception as e:
            logger.error(f"timestamp_ms 변환 실패: {dt} - {e}")
            raise ValueError(f"timestamp로 변환할 수 없습니다: {dt}")


# 편의를 위한 글로벌 함수들 (기존 코드와의 호환성)
def now() -> datetime:
    """현재 UTC 시간 반환"""
    return DateTimeUtils.now()

def today() -> date:
    """오늘 날짜 반환"""
    return DateTimeUtils.today()

def parse_iso(iso_string: str) -> datetime:
    """ISO 문자열을 datetime으로 파싱"""
    return DateTimeUtils.parse_iso_datetime(iso_string)

def to_iso(dt: datetime) -> str:
    """datetime을 ISO 문자열로 변환"""
    return DateTimeUtils.to_iso_string(dt)

def for_firestore(obj: Any) -> Any:
    """Firestore 저장용 변환"""
    return DateTimeUtils.for_firestore(obj)

def from_firestore(obj: Any) -> Any:
    """Firestore 읽기용 변환"""
    return DateTimeUtils.from_firestore(obj)

def validate_datetime(value: Any, field_name: str = "datetime") -> datetime:
    """datetime 필드 검증"""
    return DateTimeUtils.validate_datetime_field(value, field_name)

def validate_date(value: Any, field_name: str = "date") -> date:
    """date 필드 검증"""
    return DateTimeUtils.validate_date_field(value, field_name)
