# app/utils/test_datetime_utils.py
"""
통합 시간 관리 유틸리티 기능 테스트 스크립트

사용법: python -m pytest app/utils/test_datetime_utils.py -v
또는: python app/utils/test_datetime_utils.py
"""

import pytest
from datetime import datetime, date, timezone
from app.utils.datetime_utils import DateTimeUtils

def test_parse_iso_datetime():
    """ISO 포맷 파싱 테스트"""
    # 다양한 ISO 포맷 테스트
    test_cases = [
        "2024-01-15T10:30:00Z",
        "2024-01-15T10:30:00+09:00", 
        "2024-01-15T10:30:00.123456Z",
        "2024-01-15T10:30:00"
    ]
    
    for iso_string in test_cases:
        dt = DateTimeUtils.parse_iso_datetime(iso_string)
        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None  # timezone-aware 여야 함
        assert dt.tzinfo == timezone.utc  # UTC로 정규화되어야 함

def test_parse_date_string():
    """날짜 문자열 파싱 테스트"""
    test_cases = [
        "2024-01-15",
        "2024/01/15", 
        "01-15-2024"
    ]
    
    for date_string in test_cases:
        d = DateTimeUtils.parse_date_string(date_string)
        assert isinstance(d, date)

def test_for_firestore():
    """Firestore 변환 테스트"""
    test_data = {
        'birthdate': date(2020, 1, 15),
        'timestamp': datetime(2024, 1, 15, 10, 30),
        'nested': {
            'event_date': date(2023, 12, 25)
        },
        'list_data': [
            {'created_at': datetime(2024, 1, 1)}
        ]
    }
    
    converted = DateTimeUtils.for_firestore(test_data)
    
    # date는 datetime으로 변환되어야 함
    assert isinstance(converted['birthdate'], datetime)
    assert isinstance(converted['nested']['event_date'], datetime)
    assert isinstance(converted['list_data'][0]['created_at'], datetime)
    
    # 모든 datetime은 timezone-aware여야 함
    assert converted['birthdate'].tzinfo == timezone.utc

def test_validate_datetime_field():
    """datetime 필드 검증 테스트"""
    # 유효한 케이스들
    valid_cases = [
        "2024-01-15T10:30:00Z",
        datetime(2024, 1, 15, 10, 30),
        datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc)
    ]
    
    for case in valid_cases:
        result = DateTimeUtils.validate_datetime_field(case)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

def test_validate_date_field():
    """date 필드 검증 테스트"""
    # 유효한 케이스들  
    valid_cases = [
        "2024-01-15",
        date(2024, 1, 15),
        datetime(2024, 1, 15, 10, 30)
    ]
    
    for case in valid_cases:
        result = DateTimeUtils.validate_date_field(case)
        assert isinstance(result, date)

def test_calculate_age_months():
    """나이 계산 테스트"""
    # 2024년 1월 15일 기준
    birthdate = date(2020, 1, 15)
    age_months = DateTimeUtils.calculate_age_months(birthdate)
    
    # 대략적인 나이 확인 (정확한 값은 실행 시점에 따라 달라짐)
    assert isinstance(age_months, int)
    assert age_months >= 0

def test_error_handling():
    """오류 처리 테스트"""
    # 잘못된 ISO 포맷
    with pytest.raises(ValueError):
        DateTimeUtils.parse_iso_datetime("invalid-date")
    
    # 빈 문자열
    with pytest.raises(ValueError):
        DateTimeUtils.parse_iso_datetime("")
    
    # None 값
    with pytest.raises(ValueError):
        DateTimeUtils.validate_datetime_field(None)

if __name__ == "__main__":
    """직접 실행 시 간단한 테스트"""
    print("🧪 통합 시간 관리 유틸리티 테스트 시작...")
    
    try:
        # 기본 기능 테스트
        now = DateTimeUtils.now()
        print(f"✅ 현재 시간: {now}")
        
        today = DateTimeUtils.today()
        print(f"✅ 오늘 날짜: {today}")
        
        # ISO 파싱 테스트
        iso_dt = DateTimeUtils.parse_iso_datetime("2024-01-15T10:30:00Z")
        print(f"✅ ISO 파싱: {iso_dt}")
        
        # Firestore 변환 테스트
        test_data = {
            'date_field': date(2024, 1, 15),
            'datetime_field': datetime(2024, 1, 15, 10, 30)
        }
        converted = DateTimeUtils.for_firestore(test_data)
        print(f"✅ Firestore 변환: {converted}")
        
        # 유효성 검증 테스트
        validated = DateTimeUtils.validate_datetime_field("2024-01-15T10:30:00Z")
        print(f"✅ 유효성 검증: {validated}")
        
        print("\n🎉 모든 테스트 통과! 통합 시간 관리 시스템이 정상적으로 작동합니다.")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        raise
