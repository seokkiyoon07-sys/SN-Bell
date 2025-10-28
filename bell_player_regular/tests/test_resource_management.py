"""
리소스 관리 관련 단위 테스트
"""

import unittest
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# 부모 디렉토리를 경로에 추가하여 app 모듈을 import 가능하게 함
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from app import AudioResourceManager, resource_manager


class TestAudioResourceManager(unittest.TestCase):
    """오디오 리소스 매니저 테스트"""

    def setUp(self):
        """테스트 전 설정"""
        self.manager = AudioResourceManager()

    def test_add_remove_process(self):
        """프로세스 추가/제거 테스트"""
        mock_proc = MagicMock()
        
        # 프로세스 추가
        self.manager.add_process(mock_proc)
        self.assertIn(mock_proc, self.manager._procs)
        
        # 프로세스 제거
        self.manager.remove_process(mock_proc)
        self.assertNotIn(mock_proc, self.manager._procs)

    def test_add_remove_mci_alias(self):
        """MCI 별칭 추가/제거 테스트"""
        alias = "test_alias"
        
        # 별칭 추가
        self.manager.add_mci_alias(alias)
        self.assertIn(alias, self.manager._mci_aliases)
        
        # 별칭 제거
        self.manager.remove_mci_alias(alias)
        self.assertNotIn(alias, self.manager._mci_aliases)

    def test_thread_safety(self):
        """스레드 안전성 테스트"""
        mock_procs = [MagicMock() for _ in range(10)]
        threads = []

        def add_processes():
            for proc in mock_procs:
                self.manager.add_process(proc)

        def remove_processes():
            for proc in mock_procs:
                self.manager.remove_process(proc)

        # 동시에 추가/제거 작업 수행
        add_thread = threading.Thread(target=add_processes)
        remove_thread = threading.Thread(target=remove_processes)
        
        add_thread.start()
        remove_thread.start()
        
        add_thread.join()
        remove_thread.join()
        
        # 스레드 안전성 확인 (정확한 상태는 보장되지 않지만 크래시가 없어야 함)
        self.assertIsInstance(self.manager._procs, list)

    @patch('app._mci_send')
    def test_managed_mci_alias_context(self, mock_mci_send):
        """MCI 별칭 컨텍스트 매니저 테스트"""
        alias = "test_alias"
        
        with self.manager.managed_mci_alias(alias) as managed_alias:
            self.assertEqual(managed_alias, alias)
            self.assertIn(alias, self.manager._mci_aliases)
        
        # 컨텍스트 종료 후 정리 확인
        self.assertNotIn(alias, self.manager._mci_aliases)
        # MCI 명령 호출 확인
        expected_calls = [
            f"stop {alias}",
            f"close {alias}"
        ]
        for call in expected_calls:
            mock_mci_send.assert_any_call(call)

    def test_managed_process_context_normal_exit(self):
        """프로세스 컨텍스트 매니저 정상 종료 테스트"""
        mock_popen = MagicMock()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # 이미 종료됨
        mock_popen.return_value = mock_proc

        with patch('subprocess.Popen', mock_popen):
            with self.manager.managed_process(['test', 'command']) as proc:
                self.assertEqual(proc, mock_proc)
                self.assertIn(proc, self.manager._procs)
            
            # 컨텍스트 종료 후 정리 확인
            self.assertNotIn(mock_proc, self.manager._procs)

    def test_managed_process_context_exception(self):
        """프로세스 컨텍스트 매니저 예외 발생 테스트"""
        mock_popen = MagicMock()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # 아직 실행 중
        mock_popen.return_value = mock_proc

        with patch('subprocess.Popen', mock_popen):
            try:
                with self.manager.managed_process(['test', 'command']) as proc:
                    self.assertIn(proc, self.manager._procs)
                    raise Exception("Test exception")
            except Exception:
                pass
            
            # 예외 발생 시에도 정리 확인
            self.assertNotIn(mock_proc, self.manager._procs)
            mock_proc.terminate.assert_called_once()

    @patch('app._mci_send')
    def test_cleanup_all(self, mock_mci_send):
        """전체 리소스 정리 테스트"""
        # 테스트 데이터 준비
        mock_procs = []
        for i in range(3):
            mock_proc = MagicMock()
            mock_proc.poll.return_value = None  # 실행 중
            mock_procs.append(mock_proc)
            self.manager.add_process(mock_proc)
        
        aliases = ["alias1", "alias2", "alias3"]
        for alias in aliases:
            self.manager.add_mci_alias(alias)
        
        # 전체 정리 실행
        self.manager.cleanup_all()
        
        # 정리 확인
        self.assertEqual(len(self.manager._procs), 0)
        self.assertEqual(len(self.manager._mci_aliases), 0)
        
        # 모든 프로세스가 terminate 호출되었는지 확인
        for proc in mock_procs:
            proc.terminate.assert_called()
        
        # 모든 MCI 별칭이 정리되었는지 확인
        for alias in aliases:
            mock_mci_send.assert_any_call(f"stop {alias}")
            mock_mci_send.assert_any_call(f"close {alias}")

    def test_cleanup_all_with_timeout(self):
        """타임아웃이 있는 프로세스 정리 테스트"""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # 실행 중
        mock_proc.wait.side_effect = [subprocess.TimeoutExpired('cmd', 2), None]  # 첫 번째는 타임아웃, 두 번째는 성공
        
        self.manager.add_process(mock_proc)
        self.manager.cleanup_all()
        
        # terminate와 kill이 호출되었는지 확인
        mock_proc.terminate.assert_called()
        mock_proc.kill.assert_called()


class TestGlobalResourceManager(unittest.TestCase):
    """전역 리소스 매니저 테스트"""

    def test_global_manager_exists(self):
        """전역 리소스 매니저가 존재하는지 테스트"""
        self.assertIsInstance(resource_manager, AudioResourceManager)

    def test_global_manager_thread_safety(self):
        """전역 매니저의 스레드 안전성 테스트"""
        def add_remove_alias():
            alias = f"test_{threading.current_thread().ident}"
            resource_manager.add_mci_alias(alias)
            time.sleep(0.01)  # 짧은 대기
            resource_manager.remove_mci_alias(alias)

        threads = []
        for i in range(5):
            thread = threading.Thread(target=add_remove_alias)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # 모든 스레드가 완료된 후 깨끗한 상태인지 확인
        self.assertEqual(len(resource_manager._mci_aliases), 0)


if __name__ == '__main__':
    # subprocess 모듈을 테스트에서 사용하기 위해 import
    import subprocess
    unittest.main()