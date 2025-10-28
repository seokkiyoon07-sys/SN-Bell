"""
시간 처리 관련 단위 테스트
"""

import unittest
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

# 부모 디렉토리를 경로에 추가하여 app 모듈을 import 가능하게 함
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from app import hhmm_to_today, get_tz, get_current_time, get_ntp_time, get_worldtime_api


class TestTimeHandling(unittest.TestCase):
    """시간 처리 함수 테스트"""

    def test_hhmm_to_today_with_colon(self):
        """콜론이 포함된 시간 형식 테스트"""
        zone = get_tz("Asia/Seoul")
        result = hhmm_to_today("06:30", zone)
        
        self.assertEqual(result.hour, 6)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.tzinfo, zone)

    def test_hhmm_to_today_without_colon(self):
        """콜론이 없는 시간 형식 테스트"""
        zone = get_tz("Asia/Seoul")
        result = hhmm_to_today("0630", zone)
        
        self.assertEqual(result.hour, 6)
        self.assertEqual(result.minute, 30)
        self.assertEqual(result.tzinfo, zone)

    def test_hhmm_to_today_edge_cases(self):
        """시간 경계값 테스트"""
        zone = get_tz("Asia/Seoul")
        
        # 자정
        result = hhmm_to_today("00:00", zone)
        self.assertEqual(result.hour, 0)
        self.assertEqual(result.minute, 0)
        
        # 23시 59분
        result = hhmm_to_today("23:59", zone)
        self.assertEqual(result.hour, 23)
        self.assertEqual(result.minute, 59)

    def test_get_tz_valid(self):
        """유효한 타임존 테스트"""
        zone = get_tz("Asia/Seoul")
        self.assertIsNotNone(zone)
        
        zone = get_tz("UTC")
        self.assertIsNotNone(zone)

    def test_get_tz_invalid(self):
        """잘못된 타임존 테스트"""
        with self.assertRaises(ValueError):
            get_tz("Invalid/Timezone")

    @patch('app.get_ntp_time')
    @patch('app.get_worldtime_api')
    def test_get_current_time_fallback(self, mock_worldtime, mock_ntp):
        """시간 동기화 실패 시 폴백 테스트"""
        mock_ntp.return_value = None
        mock_worldtime.return_value = None
        
        result = get_current_time()
        self.assertIsInstance(result, datetime)

    @patch('app.get_ntp_time')
    def test_get_current_time_ntp_success(self, mock_ntp):
        """NTP 시간 동기화 성공 테스트"""
        test_time = datetime(2025, 10, 28, 12, 0, 0)
        mock_ntp.return_value = test_time
        
        result = get_current_time()
        self.assertEqual(result, test_time)

    @patch('requests.get')
    def test_get_worldtime_api_success(self, mock_get):
        """WorldTimeAPI 성공 테스트"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'datetime': '2025-10-28T12:00:00+09:00'
        }
        mock_get.return_value = mock_response
        
        result = get_worldtime_api()
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 28)

    @patch('requests.get')
    def test_get_worldtime_api_failure(self, mock_get):
        """WorldTimeAPI 실패 테스트"""
        mock_get.side_effect = Exception("Network error")
        
        result = get_worldtime_api()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()