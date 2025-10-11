# tests/test_pet_care_timezone.py
"""
펫케어 기록 타임존 처리 테스트

이슈: searchDate가 UTC 기준으로 생성되어 KST 기준 날짜와 불일치
해결: to_kst_date_str() 함수로 KST 기준 날짜 생성
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.utils.datetime_utils import DateTimeUtils


class TestKSTDateConversion:
    """KST 날짜 변환 테스트"""
    
    def test_basic_kst_conversion(self):
        """기본 KST 변환이 올바르게 작동하는지 확인"""
        # 10월 9일 15:48 UTC = 10월 10일 00:48 KST
        utc_dt = datetime(2025, 10, 9, 15, 48, 7, tzinfo=timezone.utc)
        
        # UTC 기준 날짜 추출 (기존 방식)
        utc_date_str = DateTimeUtils.to_date_str(utc_dt.date())
        assert utc_date_str == "2025-10-09"
        
        # KST 기준 날짜 추출 (새 방식)
        kst_date_str = DateTimeUtils.to_kst_date_str(utc_dt)
        assert kst_date_str == "2025-10-10"
        
    def test_midnight_boundary_utc_to_kst(self):
        """자정 경계 케이스 테스트 (UTC 전날 = KST 당일)"""
        # 10월 9일 23:59:59 UTC = 10월 10일 08:59:59 KST
        utc_dt1 = datetime(2025, 10, 9, 23, 59, 59, tzinfo=timezone.utc)
        assert DateTimeUtils.to_kst_date_str(utc_dt1) == "2025-10-10"
        
        # 10월 9일 15:00:00 UTC = 10월 10일 00:00:00 KST (자정)
        utc_dt2 = datetime(2025, 10, 9, 15, 0, 0, tzinfo=timezone.utc)
        assert DateTimeUtils.to_kst_date_str(utc_dt2) == "2025-10-10"
        
        # 10월 9일 14:59:59 UTC = 10월 9일 23:59:59 KST (자정 직전)
        utc_dt3 = datetime(2025, 10, 9, 14, 59, 59, tzinfo=timezone.utc)
        assert DateTimeUtils.to_kst_date_str(utc_dt3) == "2025-10-09"
        
    def test_morning_hours_utc_to_kst(self):
        """오전 시간대 테스트 (UTC와 KST 날짜 다름)"""
        # 10월 10일 00:00:00 UTC = 10월 10일 09:00:00 KST
        utc_dt1 = datetime(2025, 10, 10, 0, 0, 0, tzinfo=timezone.utc)
        assert DateTimeUtils.to_kst_date_str(utc_dt1) == "2025-10-10"
        
        # 10월 10일 08:59:59 UTC = 10월 10일 17:59:59 KST
        utc_dt2 = datetime(2025, 10, 10, 8, 59, 59, tzinfo=timezone.utc)
        assert DateTimeUtils.to_kst_date_str(utc_dt2) == "2025-10-10"
        
    def test_afternoon_hours_utc_to_kst(self):
        """오후 시간대 테스트 (UTC와 KST 날짜 같음 또는 다름)"""
        # 10월 10일 14:59:59 UTC = 10월 10일 23:59:59 KST
        utc_dt1 = datetime(2025, 10, 10, 14, 59, 59, tzinfo=timezone.utc)
        assert DateTimeUtils.to_kst_date_str(utc_dt1) == "2025-10-10"
        
        # 10월 10일 15:00:00 UTC = 10월 11일 00:00:00 KST (다음날 자정)
        utc_dt2 = datetime(2025, 10, 10, 15, 0, 0, tzinfo=timezone.utc)
        assert DateTimeUtils.to_kst_date_str(utc_dt2) == "2025-10-11"
        

class TestTimestampMsToKSTDate:
    """timestamp(ms)에서 KST 날짜 추출 테스트"""
    
    def test_real_world_scenario(self):
        """실제 프론트엔드 시나리오"""
        # 2025-10-10T00:48:07+09:00 (KST) = 2025-10-09T15:48:07Z (UTC)
        # Unix timestamp (ms)
        timestamp_ms = 1728492487000
        
        # UTC datetime으로 변환
        utc_dt = DateTimeUtils.from_timestamp_ms(timestamp_ms)
        
        # UTC 날짜 (기존 방식 - 문제)
        utc_date = utc_dt.date()
        assert DateTimeUtils.to_date_str(utc_date) == "2025-10-09"
        
        # KST 날짜 (새 방식 - 해결)
        kst_date_str = DateTimeUtils.to_kst_date_str(utc_dt)
        assert kst_date_str == "2025-10-10"
        
    def test_early_morning_kst_record(self):
        """새벽 시간대 기록 (가장 문제가 많은 케이스)"""
        # 2025-10-10T01:30:00+09:00 (KST) = 2025-10-09T16:30:00Z (UTC)
        timestamp_ms = 1728495000000
        
        utc_dt = DateTimeUtils.from_timestamp_ms(timestamp_ms)
        kst_date_str = DateTimeUtils.to_kst_date_str(utc_dt)
        
        # 사용자는 10월 10일 새벽에 기록했으므로 searchDate도 10월 10일이어야 함
        assert kst_date_str == "2025-10-10"
        
    def test_late_night_kst_record(self):
        """밤 늦은 시간 기록"""
        # 2025-10-09T23:59:00+09:00 (KST) = 2025-10-09T14:59:00Z (UTC)
        timestamp_ms = 1728489540000
        
        utc_dt = DateTimeUtils.from_timestamp_ms(timestamp_ms)
        kst_date_str = DateTimeUtils.to_kst_date_str(utc_dt)
        
        # 사용자는 10월 9일 밤에 기록했으므로 searchDate도 10월 9일이어야 함
        assert kst_date_str == "2025-10-09"


class TestTodayKST:
    """today_kst 함수 테스트"""
    
    def test_today_kst_returns_kst_date(self):
        """today_kst()가 KST 기준 오늘 날짜를 반환하는지 확인"""
        kst_today = DateTimeUtils.today_kst()
        utc_today = DateTimeUtils.today()
        
        # KST와 UTC는 최대 1일 차이날 수 있음
        diff_days = abs((kst_today - utc_today).days)
        assert diff_days <= 1
        
    def test_today_kst_as_date_str(self):
        """today_kst_as_date_str()이 올바른 형식을 반환하는지 확인"""
        date_str = DateTimeUtils.today_kst_as_date_str()
        
        # YYYY-MM-DD 형식 확인
        assert len(date_str) == 10
        assert date_str[4] == '-'
        assert date_str[7] == '-'
        
        # 파싱 가능한지 확인
        from datetime import datetime
        parsed = datetime.strptime(date_str, '%Y-%m-%d')
        assert parsed is not None


class TestBackwardCompatibility:
    """기존 코드 호환성 테스트"""
    
    def test_to_date_str_alias_still_works(self):
        """to_date_str() alias가 여전히 작동하는지 확인"""
        from datetime import date
        test_date = date(2025, 10, 10)
        
        # alias를 통한 호출
        result1 = DateTimeUtils.to_date_str(test_date)
        # 원본 함수 호출
        result2 = DateTimeUtils.to_date_string(test_date)
        
        assert result1 == result2 == "2025-10-10"
        
    def test_existing_utc_functions_unchanged(self):
        """기존 UTC 함수들이 변경되지 않았는지 확인"""
        utc_now = DateTimeUtils.now()
        assert utc_now.tzinfo == timezone.utc
        
        utc_today = DateTimeUtils.today()
        assert isinstance(utc_today, datetime.date)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
