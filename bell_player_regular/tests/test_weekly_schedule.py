"""
요일별 스케줄 관련 단위 테스트
"""

import unittest
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# 부모 디렉토리를 경로에 추가하여 app 모듈을 import 가능하게 함
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from app import (
    WEEKDAY_SCHEDULE, 
    SUNDAY_SCHEDULE, 
    is_sunday, 
    get_schedule_for_today,
    get_tz
)


class TestWeeklySchedule(unittest.TestCase):
    """요일별 스케줄 테스트"""

    def test_weekday_schedule_structure(self):
        """평일 스케줄 구조 테스트"""
        self.assertEqual(len(WEEKDAY_SCHEDULE), 20)
        
        # 첫 번째 항목 확인
        self.assertEqual(WEEKDAY_SCHEDULE[0], (1, "06:00", "기상종소리"))
        
        # 마지막 항목 확인
        self.assertEqual(WEEKDAY_SCHEDULE[-1], (20, "22:30", "하루일과 종료종"))

    def test_sunday_schedule_structure(self):
        """일요일 스케줄 구조 테스트"""
        self.assertEqual(len(SUNDAY_SCHEDULE), 17)
        
        # 첫 번째 항목 확인 (07:00부터 시작)
        self.assertEqual(SUNDAY_SCHEDULE[0], (1, "07:00", "기상종"))
        
        # 두 번째 항목 확인
        self.assertEqual(SUNDAY_SCHEDULE[1], (2, "10:50", "입실종"))
        
        # 세 번째 항목 확인
        self.assertEqual(SUNDAY_SCHEDULE[2], (3, "11:00", "시작종"))
        
        # 네 번째 항목 확인 (기존 첫 번째)
        self.assertEqual(SUNDAY_SCHEDULE[3], (4, "12:10", "식사시간종"))
        
        # 마지막 항목 확인
        self.assertEqual(SUNDAY_SCHEDULE[-1], (17, "22:30", "하루일과 종료종"))

    def test_sunday_schedule_structure_complete(self):
        """일요일 스케줄 완전성 테스트"""
        # 일요일 스케줄이 평일보다 짧거나 비슷해야 함
        self.assertLessEqual(len(SUNDAY_SCHEDULE), len(WEEKDAY_SCHEDULE))
        
        # 일요일 첫 번째 항목이 07:00인지 확인 (기상종)
        self.assertEqual(SUNDAY_SCHEDULE[0][1], "07:00")
        
        # 일요일만의 특별한 시간들 확인
        sunday_times = [item[1] for item in SUNDAY_SCHEDULE]
        self.assertIn("07:00", sunday_times)  # 기상종
        self.assertIn("10:50", sunday_times)  # 입실종
        self.assertIn("11:00", sunday_times)  # 시작종
        
        # 공통 시간들도 포함되어 있는지 확인
        self.assertIn("12:10", sunday_times)  # 식사시간종
        self.assertIn("22:30", sunday_times)  # 하루일과 종료종

    @patch('app.datetime')
    def test_is_sunday_true(self, mock_datetime):
        """일요일 판별 테스트 - True 케이스"""
        # 일요일 = weekday() 6
        mock_now = MagicMock()
        mock_now.weekday.return_value = 6
        mock_datetime.now.return_value = mock_now
        
        zone = get_tz("Asia/Seoul")
        self.assertTrue(is_sunday(zone))

    @patch('app.datetime')
    def test_is_sunday_false(self, mock_datetime):
        """일요일 판별 테스트 - False 케이스"""
        # 월요일 = weekday() 0
        mock_now = MagicMock()
        mock_now.weekday.return_value = 0
        mock_datetime.now.return_value = mock_now
        
        zone = get_tz("Asia/Seoul")
        self.assertFalse(is_sunday(zone))

    @patch('app.is_sunday')
    def test_get_schedule_for_today_sunday(self, mock_is_sunday):
        """일요일 스케줄 선택 테스트"""
        mock_is_sunday.return_value = True
        zone = get_tz("Asia/Seoul")
        
        result = get_schedule_for_today(zone)
        self.assertEqual(result, SUNDAY_SCHEDULE)

    @patch('app.is_sunday')
    def test_get_schedule_for_today_weekday(self, mock_is_sunday):
        """평일 스케줄 선택 테스트"""
        mock_is_sunday.return_value = False
        zone = get_tz("Asia/Seoul")
        
        result = get_schedule_for_today(zone)
        self.assertEqual(result, WEEKDAY_SCHEDULE)

    def test_schedule_indices_are_unique(self):
        """스케줄 인덱스가 고유한지 테스트"""
        # 평일 스케줄 인덱스
        weekday_indices = [item[0] for item in WEEKDAY_SCHEDULE]
        self.assertEqual(len(weekday_indices), len(set(weekday_indices)), 
                        "평일 스케줄에 중복 인덱스가 있습니다")
        
        # 일요일 스케줄 인덱스  
        sunday_indices = [item[0] for item in SUNDAY_SCHEDULE]
        self.assertEqual(len(sunday_indices), len(set(sunday_indices)),
                        "일요일 스케줄에 중복 인덱스가 있습니다")

    def test_schedule_times_are_chronological(self):
        """스케줄 시간이 시간순으로 정렬되어 있는지 테스트"""
        def time_to_minutes(time_str):
            """HH:MM 형식을 분으로 변환"""
            hours, minutes = map(int, time_str.split(':'))
            return hours * 60 + minutes
        
        # 평일 스케줄 시간 순서 확인
        weekday_times = [time_to_minutes(item[1]) for item in WEEKDAY_SCHEDULE]
        self.assertEqual(weekday_times, sorted(weekday_times),
                        "평일 스케줄이 시간순으로 정렬되지 않았습니다")
        
        # 일요일 스케줄 시간 순서 확인
        sunday_times = [time_to_minutes(item[1]) for item in SUNDAY_SCHEDULE]
        self.assertEqual(sunday_times, sorted(sunday_times),
                        "일요일 스케줄이 시간순으로 정렬되지 않았습니다")

    def test_valid_time_format(self):
        """스케줄의 시간 형식이 올바른지 테스트"""
        import re
        time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')
        
        # 평일 스케줄 시간 형식 확인
        for idx, time_str, desc in WEEKDAY_SCHEDULE:
            self.assertIsNotNone(time_pattern.match(time_str),
                               f"평일 스케줄 시간 형식 오류: {time_str}")
        
        # 일요일 스케줄 시간 형식 확인
        for idx, time_str, desc in SUNDAY_SCHEDULE:
            self.assertIsNotNone(time_pattern.match(time_str),
                               f"일요일 스케줄 시간 형식 오류: {time_str}")


class TestScheduleIntegration(unittest.TestCase):
    """스케줄 통합 테스트"""

    @patch('app.datetime')
    def test_weekend_transition(self, mock_datetime):
        """주말 전환 시나리오 테스트"""
        zone = get_tz("Asia/Seoul")
        
        # 토요일 (weekday = 5)
        mock_now = MagicMock()
        mock_now.weekday.return_value = 5
        mock_datetime.now.return_value = mock_now
        
        saturday_schedule = get_schedule_for_today(zone)
        self.assertEqual(saturday_schedule, WEEKDAY_SCHEDULE)
        
        # 일요일 (weekday = 6) 
        mock_now.weekday.return_value = 6
        sunday_schedule = get_schedule_for_today(zone)
        self.assertEqual(sunday_schedule, SUNDAY_SCHEDULE)
        
        # 월요일 (weekday = 0)
        mock_now.weekday.return_value = 0
        monday_schedule = get_schedule_for_today(zone)
        self.assertEqual(monday_schedule, WEEKDAY_SCHEDULE)


if __name__ == '__main__':
    unittest.main()