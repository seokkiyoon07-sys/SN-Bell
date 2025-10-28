"""
설정 검증 관련 단위 테스트
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path

# 부모 디렉토리를 경로에 추가하여 app 모듈을 import 가능하게 함
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from app import validate_config, DEFAULT_CONFIG, load_config


class TestConfigValidation(unittest.TestCase):
    """설정 검증 함수 테스트"""

    def test_validate_volume_in_range(self):
        """볼륨이 정상 범위일 때 테스트"""
        config = {"volume": 0.5}
        result = validate_config(config)
        self.assertEqual(result["volume"], 0.5)

    def test_validate_volume_out_of_range(self):
        """볼륨이 범위를 벗어날 때 테스트"""
        config = {"volume": 1.5}
        result = validate_config(config)
        self.assertEqual(result["volume"], 1.0)  # 기본값으로 수정됨

        config = {"volume": -0.1}
        result = validate_config(config)
        self.assertEqual(result["volume"], 1.0)  # 기본값으로 수정됨

    def test_validate_volume_invalid_type(self):
        """볼륨이 잘못된 타입일 때 테스트"""
        config = {"volume": "invalid"}
        result = validate_config(config)
        self.assertEqual(result["volume"], 1.0)  # 기본값으로 수정됨

    def test_validate_timezone_valid(self):
        """유효한 타임존 테스트"""
        config = {"timezone": "Asia/Seoul"}
        result = validate_config(config)
        self.assertEqual(result["timezone"], "Asia/Seoul")

    def test_validate_timezone_invalid(self):
        """잘못된 타임존 테스트"""
        config = {"timezone": "Invalid/Timezone"}
        result = validate_config(config)
        self.assertEqual(result["timezone"], "Asia/Seoul")  # 기본값으로 수정됨

    def test_validate_refresh_time_valid(self):
        """유효한 리프레시 시간 테스트"""
        config = {"refresh_time": "0130"}  # 01:30
        result = validate_config(config)
        self.assertEqual(result["refresh_time"], "0130")

    def test_validate_refresh_time_invalid_format(self):
        """잘못된 리프레시 시간 형식 테스트"""
        config = {"refresh_time": "25:70"}  # 잘못된 시간
        result = validate_config(config)
        self.assertEqual(result["refresh_time"], "0001")  # 기본값으로 수정됨

        config = {"refresh_time": "abc"}  # 잘못된 형식
        result = validate_config(config)
        self.assertEqual(result["refresh_time"], "0001")  # 기본값으로 수정됨

    def test_validate_misfire_grace_valid(self):
        """유효한 미스파이어 유예 시간 테스트"""
        config = {"misfire_grace_seconds": 120}
        result = validate_config(config)
        self.assertEqual(result["misfire_grace_seconds"], 120)

    def test_validate_misfire_grace_invalid(self):
        """잘못된 미스파이어 유예 시간 테스트"""
        config = {"misfire_grace_seconds": -10}
        result = validate_config(config)
        self.assertEqual(result["misfire_grace_seconds"], 60)  # 기본값으로 수정됨

        config = {"misfire_grace_seconds": "invalid"}
        result = validate_config(config)
        self.assertEqual(result["misfire_grace_seconds"], 60)  # 기본값으로 수정됨

    def test_validate_boolean_values(self):
        """부울 값 검증 테스트"""
        config = {
            "test_mode": "true",
            "prefer_mci": "false",
            "autoplay_next_day": 1,
            "workdays_only": 0
        }
        result = validate_config(config)
        
        self.assertTrue(result["test_mode"])
        self.assertFalse(result["prefer_mci"])
        self.assertTrue(result["autoplay_next_day"])
        self.assertFalse(result["workdays_only"])

    def test_validate_sound_extension(self):
        """사운드 확장자 검증 테스트"""
        config = {"sound_ext": "wav"}
        result = validate_config(config)
        self.assertEqual(result["sound_ext"], "wav")

        config = {"sound_ext": ".mp3"}  # 점 포함
        result = validate_config(config)
        self.assertEqual(result["sound_ext"], "mp3")  # 점 제거됨

        config = {"sound_ext": "unsupported"}
        result = validate_config(config)
        self.assertEqual(result["sound_ext"], "mp3")  # 기본값으로 수정됨


class TestConfigLoading(unittest.TestCase):
    """설정 로드 함수 테스트"""

    def test_load_config_nonexistent_file(self):
        """존재하지 않는 설정 파일 테스트"""
        result = load_config("nonexistent.yaml")
        self.assertEqual(result, DEFAULT_CONFIG)

    def test_load_config_valid_file(self):
        """유효한 설정 파일 테스트"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("volume: 0.8\ntest_mode: true\n")
            temp_path = f.name

        try:
            result = load_config(temp_path)
            self.assertEqual(result["volume"], 0.8)
            self.assertTrue(result["test_mode"])
        finally:
            os.unlink(temp_path)

    def test_load_config_invalid_yaml(self):
        """잘못된 YAML 파일 테스트"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name

        try:
            result = load_config(temp_path)
            # 파싱 오류 시 기본값 반환
            self.assertEqual(result["volume"], DEFAULT_CONFIG["volume"])
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()