"""
일요일 탭 GUI 기능 테스트
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import tkinter as tk

# 부모 디렉토리를 경로에 추가
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from gui import BellRegularGUI
from app import SUNDAY_SCHEDULE


class TestSundayTab(unittest.TestCase):
    """일요일 탭 기능 테스트"""

    def setUp(self):
        """테스트 설정"""
        self.root = tk.Tk()
        self.root.withdraw()  # GUI 창 숨기기
        
        with patch('gui.setup_logging'), \
             patch('gui.load_config') as mock_config:
            mock_config.return_value = {
                'sounds_dir': 'test_sounds',
                'test_mode': False,
                'volume': 1.0,
                'prefer_mci': False,
                'log_file': 'test.log'
            }
            self.app = BellRegularGUI(self.root)

    def tearDown(self):
        """테스트 정리"""
        if self.root:
            self.root.destroy()

    def test_sunday_tab_exists(self):
        """일요일 탭이 존재하는지 테스트"""
        # notebook의 탭 수 확인 (메인, 일요일, 설명서)
        self.assertEqual(self.app.notebook.index("end"), 3)
        
        # 탭 텍스트 확인
        tab_texts = []
        for i in range(self.app.notebook.index("end")):
            tab_texts.append(self.app.notebook.tab(i, "text"))
        
        self.assertIn("일요일 스케줄", tab_texts)

    def test_sunday_checkboxes_created(self):
        """일요일 체크박스가 올바르게 생성되었는지 테스트"""
        # 일요일 체크박스 변수 개수 확인
        self.assertEqual(len(self.app.sunday_check_vars), len(SUNDAY_SCHEDULE))
        
        # 체크박스 위젯 개수 확인
        self.assertEqual(len(self.app.sunday_checkbox_widgets), len(SUNDAY_SCHEDULE))
        
        # 인덱스 레이블 개수 확인
        self.assertEqual(len(self.app.sunday_index_labels), len(SUNDAY_SCHEDULE))

    def test_sunday_checkboxes_initial_state(self):
        """일요일 체크박스 초기 상태 테스트"""
        # 모든 체크박스가 초기에는 선택되지 않은 상태
        for var in self.app.sunday_check_vars:
            self.assertFalse(var.get())

    def test_clear_selection_sunday(self):
        """일요일 선택 해제 기능 테스트"""
        # 먼저 일부 체크박스 선택
        for i in range(3):
            self.app.sunday_check_vars[i].set(True)
        
        # 선택 해제 실행
        self.app.clear_selection_sunday()
        
        # 모든 체크박스가 해제되었는지 확인
        for var in self.app.sunday_check_vars:
            self.assertFalse(var.get())

    def test_select_all_sunday(self):
        """일요일 모두 선택 기능 테스트"""
        # 모두 선택 실행
        self.app.select_all_sunday()
        
        # 모든 체크박스가 선택되었는지 확인
        for var in self.app.sunday_check_vars:
            self.assertTrue(var.get())

    def test_select_defaults_sunday(self):
        """일요일 디폴트 선택 기능 테스트"""
        # 디폴트 선택 실행
        self.app.select_defaults_sunday()
        
        # 선택된 항목들의 시간 확인
        selected_times = []
        for i, var in enumerate(self.app.sunday_check_vars):
            if var.get():
                _, time_str, _ = SUNDAY_SCHEDULE[i]
                selected_times.append(time_str)
        
        # 주요 시간대가 포함되었는지 확인
        important_times = ["07:00", "10:50", "11:00", "12:10", "13:00", "17:30", "18:30"]
        for time_str in important_times:
            if time_str in [item[1] for item in SUNDAY_SCHEDULE]:
                self.assertIn(time_str, selected_times)

    @patch('gui.messagebox.showwarning')
    def test_play_selected_sunday_no_selection(self, mock_warning):
        """일요일 아무것도 선택하지 않고 재생 시도하는 경우 테스트"""
        # 아무것도 선택하지 않은 상태에서 재생 시도
        self.app.play_selected_sunday()
        
        # 경고 메시지가 표시되었는지 확인
        mock_warning.assert_called_once_with("알림", "일요일 스케줄에서 재생할 항목을 선택하세요.")

    def test_sunday_schedule_content(self):
        """일요일 스케줄 내용 검증"""
        # 첫 번째 항목이 07:00 기상종인지 확인
        self.assertEqual(SUNDAY_SCHEDULE[0], (1, "07:00", "기상종소리"))
        
        # 두 번째 항목이 10:50 입실종인지 확인
        self.assertEqual(SUNDAY_SCHEDULE[1], (2, "10:50", "입실종"))
        
        # 세 번째 항목이 11:00 시작종인지 확인
        self.assertEqual(SUNDAY_SCHEDULE[2], (3, "11:00", "시작종"))
        
        # 네 번째 항목부터 12:10 식사시간종인지 확인
        self.assertEqual(SUNDAY_SCHEDULE[3], (4, "12:10", "식사시간종"))

    def test_sunday_stop_events(self):
        """일요일 정지 이벤트 테스트"""
        # 정지 이벤트 초기 상태 확인
        self.assertFalse(self.app.sunday_manual_stop_event.is_set())
        
        # 정지 실행
        self.app.stop_manual_sunday()
        
        # 정지 이벤트가 설정되었는지 확인
        self.assertTrue(self.app.sunday_manual_stop_event.is_set())


if __name__ == '__main__':
    # GUI 테스트이므로 main 스레드에서 실행
    unittest.main()