import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import requests
import json
import logging
from datetime import datetime

from app import (
    load_config,
    setup_logging,
    start_scheduler,
    stop_scheduler,
    CONFIG_YAML,
    DEFAULT_CONFIG,
    play_sound_for_index,
    play_sound_for_index_sunday,
    get_sound_duration_seconds,
    REGULAR_SCHEDULE,
    WEEKDAY_SCHEDULE,
    SUNDAY_SCHEDULE,
    get_schedule_for_today,
    is_sunday,
    get_tz,
)
import yaml


class BellRegularGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("평상시 종소리 프로그램 v1.1")
        self.sched = None
        self.config = load_config(CONFIG_YAML)
        setup_logging(os.path.join(os.path.dirname(CONFIG_YAML), self.config.get("log_file", "logs/bell.log")))

        self.var_sounds = tk.StringVar(value=self.config.get("sounds_dir") or "")
        self.var_sounds_sunday = tk.StringVar(value=self.config.get("sounds_dir_sunday") or "")
        self.var_test = tk.BooleanVar(value=bool(self.config.get("test_mode", False)))
        self.var_volume = tk.DoubleVar(value=float(self.config.get("volume", 1.0)))
        self.var_prefer_mci = tk.BooleanVar(value=bool(self.config.get("prefer_mci", False)))

        # 메인 화면 시계 관련 변수
        self.main_clock_label = None
        self.main_date_label = None
        self.clock_update_job = None
        self.use_naver_time = tk.BooleanVar(value=False)

        # Manual playback state (평일용)
        # 동적 스케줄 크기에 맞춰 체크박스 변수 생성
        self.manual_check_vars = []
        self.manual_thread = None
        self.manual_stop_event = threading.Event()

        # 일요일 전용 체크박스 변수들
        self.sunday_check_vars = []
        self.sunday_manual_thread = None
        self.sunday_manual_stop_event = threading.Event()

        # 현재 스케줄에 맞는 라벨 생성
        self.index_labels = []
        self.current_schedule = []
        self.update_schedule_display()

        # Menu
        menubar = tk.Menu(root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="종료", command=self.on_exit)
        menubar.add_cascade(label="파일", menu=filemenu)
        root.config(menu=menubar)

        # Tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        tab_main = tk.Frame(self.notebook)
        tab_sunday = tk.Frame(self.notebook)
        tab_help = tk.Frame(self.notebook)
        self.notebook.add(tab_main, text="평일")
        self.notebook.add(tab_sunday, text="일요일")
        self.notebook.add(tab_help, text="설명서")

        frm = tk.Frame(tab_main)
        frm.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)

        # === 시계 및 날짜 표시 영역 ===
        clock_frame = tk.Frame(frm, relief=tk.RIDGE, bd=1, bg="#f0f8ff")
        clock_frame.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 10), padx=2)
        
        # 시계 표시
        self.main_clock_label = tk.Label(clock_frame, text="--:--:--", 
                                        font=("Segoe UI", 16, "bold"), 
                                        fg="#1e90ff", bg="#f0f8ff")
        self.main_clock_label.pack(side="left", padx=10, pady=5)
        
        # 날짜 및 요일 표시
        self.main_date_label = tk.Label(clock_frame, text="---- 년 -- 월 -- 일 (---요일)", 
                                       font=("맑은 고딕", 12, "bold"), 
                                       fg="#333333", bg="#f0f8ff")
        self.main_date_label.pack(side="left", padx=10, pady=5)

        # 외부 시간 동기화 컨트롤
        sync_frame = tk.Frame(clock_frame, bg="#f0f8ff")
        sync_frame.pack(side="right", padx=10, pady=5)
        
        tk.Checkbutton(sync_frame, text="외부 시간 동기화", 
                      variable=self.use_naver_time, 
                      font=("맑은 고딕", 9), 
                      bg="#f0f8ff",
                      command=self.on_sync_toggle).pack(side="top")
        
        self.sync_status_label = tk.Label(sync_frame, text="로컬 시계", 
                                         font=("맑은 고딕", 8), 
                                         fg="#666666", bg="#f0f8ff")
        self.sync_status_label.pack(side="top")

        # 시계 업데이트 시작
        self.start_main_clock()

        # Sounds dir
        tk.Label(frm, text="사운드 폴더").grid(row=1, column=0, sticky="w")
        ent = tk.Entry(frm, textvariable=self.var_sounds, width=50)
        ent.grid(row=1, column=1, padx=5)
        tk.Button(frm, text="찾기", command=self.pick_folder).grid(row=1, column=2)

        # Volume
        tk.Label(frm, text="볼륨(0~1)").grid(row=2, column=0, sticky="w")
        tk.Entry(frm, textvariable=self.var_volume, width=10).grid(row=2, column=1, sticky="w")

        # Test mode
        tk.Checkbutton(frm, text="테스트 모드(3초 간격)", variable=self.var_test).grid(row=3, column=0, columnspan=2, sticky="w")
        tk.Checkbutton(frm, text="MCI 우선 사용(윈도우 내장)", variable=self.var_prefer_mci).grid(row=3, column=2, columnspan=2, sticky="w")

        # Buttons for scheduler (첫 번째 줄)
        tk.Button(frm, text="▶️ 스케줄러 시작", command=self.start, bg="#e8f5e8").grid(row=4, column=0, pady=6, padx=2)
        tk.Button(frm, text="⏹️ 스케줄러 정지", command=self.stop, bg="#ffe8e8").grid(row=4, column=1, pady=6, padx=2)
        tk.Button(frm, text="💾 저장", command=self.save_config).grid(row=4, column=2, pady=6, padx=2)
        
        # 추가 기능 버튼들 (두 번째 줄)
        tk.Button(frm, text="📅 스케줄 새로고침", command=self.refresh_schedule).grid(row=5, column=0, pady=6, padx=2)
        tk.Button(frm, text="🔧 개발자 새로고침", command=self.refresh_all).grid(row=5, column=1, pady=6, padx=2)
        tk.Button(frm, text="🕒 시계", command=self.open_clock_window).grid(row=5, column=2, pady=6, padx=2)

        # Manual playback section
        sep = tk.Frame(frm, height=1, bg="#ddd")
        sep.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 6))

        tk.Label(frm, text="수동 재생 (체크된 번호만)").grid(row=7, column=0, columnspan=3, sticky="w")

        # Scrollable container for the checkboxes
        scroll_container = tk.Frame(frm)
        scroll_container.grid(row=8, column=0, columnspan=3, sticky="nsew")
        frm.grid_rowconfigure(8, weight=1)

        canvas = tk.Canvas(scroll_container, highlightthickness=0, width=520, height=280)
        vbar = tk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.grid = tk.Frame(canvas)  # self.grid로 저장해서 다른 메서드에서 접근 가능
        canvas.create_window((0, 0), window=self.grid, anchor="nw")

        # 현재 스케줄에 맞는 체크박스들을 동적으로 생성
        self.checkbox_widgets = []
        self.create_schedule_checkboxes()

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_mousewheel(event):
            # Windows/Mac use event.delta, Linux uses Button-4/5
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                # Fallback for systems sending Button-4/5
                direction = -1 if getattr(event, "num", None) == 4 else 1
                canvas.yview_scroll(direction, "units")

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel) 
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        self.grid.bind("<Configure>", _on_configure)
        
        # 마우스 휠 바인딩 - 캔버스 영역에 마우스가 있을 때만 활성화
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        scroll_container.bind("<Enter>", _bind_mousewheel)
        scroll_container.bind("<Leave>", _unbind_mousewheel)
        
        # 체크박스들에도 마우스 휠 바인딩 적용
        def _bind_to_children(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            widget.bind("<Button-4>", _on_mousewheel)
            widget.bind("<Button-5>", _on_mousewheel)
            for child in widget.winfo_children():
                _bind_to_children(child)
        
        # 초기 바인딩
        _bind_to_children(self.grid)

        ctrl = tk.Frame(frm)
        ctrl.grid(row=9, column=0, columnspan=3, sticky="w", pady=(6, 0))
        tk.Button(ctrl, text="선택 재생", command=self.play_selected).grid(row=0, column=0, padx=(0, 6))
        tk.Button(ctrl, text="선택 해제", command=self.clear_selection).grid(row=0, column=1, padx=(0, 6))
        tk.Button(ctrl, text="모두 선택", command=self.select_all).grid(row=0, column=2, padx=(0, 6))
        tk.Button(ctrl, text="수동 정지", command=self.stop_manual).grid(row=0, column=3, padx=(0, 6))
        tk.Button(ctrl, text="디폴트 선택", command=self.select_defaults).grid(row=0, column=4)

        # Initial duration scan
        self.root.after(200, self.refresh_durations)

        # Status
        self.var_status = tk.StringVar(value="대기")
        tk.Label(frm, textvariable=self.var_status, fg="#006400").grid(row=10, column=0, columnspan=3, sticky="w", pady=(8,0))

        # Branding (visible on first screen)
        tk.Label(frm, text="평상시 종소리 프로그램 developed by SN독학기숙학원", fg="#666666").grid(row=11, column=0, columnspan=3, sticky="w", pady=(4,0))

        for i in range(5):  # 컬럼 수를 늘려서 버튼들이 더 잘 배치되도록 함
            frm.grid_columnconfigure(i, weight=1)

        # === 일요일 탭 구성 ===
        self.setup_sunday_tab(tab_sunday)

        # Clock window state
        self.clock_win = None
        self.clock_label = None

        # Help tab content
        help_wrap = tk.Frame(tab_help)
        help_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        help_txt = tk.Text(help_wrap, height=24, wrap="word", font=("맑은 고딕", 11))
        help_txt.pack(side="left", fill=tk.BOTH, expand=True)
        help_scroll = tk.Scrollbar(help_wrap, command=help_txt.yview)
        help_scroll.pack(side="right", fill="y")
        help_txt.configure(yscrollcommand=help_scroll.set)
        help_content = (
            "평상시 종소리 프로그램 사용 설명서\n\n"
            "1) 기본 설정\n"
            "- 준비물(선택): FFmpeg(ffplay) — 이제 기본은 MCI(윈도우 내장)입니다.\n"
            "  A. 기본(MCI 우선): 별도 설치 없이 MP3/WAV 대부분 재생됩니다.\n"
            "  B. 보완(ffplay): 특정 코덱/형식 문제 시 FFmpeg의 ffplay를 추가로 사용합니다.\n"
            "     - 포터블 동봉 시 exe 옆 ffmpeg\\bin\\ffplay.exe를 자동 인식합니다.\n"
            "     - 시스템 PATH 또는 config.yaml의 ffplay_path로도 지정 가능.\n"
            "- 사운드 폴더: 벨 음원 위치를 지정합니다. (예: C\\code\\SN-Bell\\bell_sound_regular)\n"
            "- 볼륨: 0~1 사이 값. 일부 포맷은 OS 볼륨에 따릅니다.\n"
            "- 테스트 모드: 고정 스케줄을 3초 간격으로 빠르게 재생 스케줄링합니다.\n"
            "- (옵션) MCI 우선 사용: 메인 탭의 체크박스로 전환할 수 있습니다(기본: 켜짐).\n\n"
            "2) 요일별 스케줄\n"
            "📅 평일 스케줄 (월~토):\n"
            "- 06:00 기상종소리\n"
            "- 07:20 시작종\n"
            "- 08:30 쉬는시간종\n"
            "- 08:40 시작종\n"
            "- 10:00 쉬는시간종\n"
            "- 10:20 시작종\n"
            "- 12:10 식사시간종\n"
            "- 13:00 시작종\n"
            "- 14:20 쉬는시간종\n"
            "- 14:40 시작종\n"
            "- 16:30 쉬는시간종\n"
            "- 16:40 시작종\n"
            "- 17:30 식사시간종\n"
            "- 18:30 시작종\n"
            "- 19:50 쉬는시간종\n"
            "- 20:00 시작종\n"
            "- 21:00 간식시간종\n"
            "- 21:30 시작종\n"
            "- 22:20 학습종료종\n"
            "- 22:30 하루일과 종료종\n\n"
            "📅 일요일 스케줄:\n"
            "- 평일과 완전히 동일한 스케줄 사용\n\n"
            "3) 스케줄러\n"
            "- 스케줄러 시작: 현재 요일에 맞는 스케줄로 오늘 남은 시간만 예약합니다.\n"
            "- 스케줄러 정지: 예약과 진행을 중단합니다.\n"
            "- 스케줄 새로고침: 현재 요일에 맞게 스케줄을 다시 로드합니다.\n"
            "- 자동 요일 감지: 모든 요일 동일한 스케줄 사용.\n\n"
            "4) 수동 재생\n"
            "- 체크박스에서 선택 → [선택 재생]으로 즉시 재생합니다.\n"
            "- [수동 정지]로 중단, [모두 선택]/[선택 해제]/[디폴트 선택] 지원.\n"
            "- 각 항목 끝의 (mm:ss)는 파일 길이입니다.\n\n"
            "5) 파일명/폴더\n"
            "- 권장 파일명: 01.mp3 ~ 20.mp3 (다른 확장자도 자동 탐색).\n"
            "- 사운드 폴더 변경 시 길이를 자동 갱신합니다.\n\n"
            "6) 재생 백엔드\n"
            "- 기본 순서: MCI → ffplay(있으면) → playsound(있으면).\n"
            "- ffplay 포터블: \"ffmpeg\\bin\\ffplay.exe\"를 exe 옆에 두면 자동 인식.\n"
            "- 수동 지정: config.yaml의 ffplay_path에 절대경로 입력 가능.\n\n"
            "7) 종료/안전\n"
            "- 파일 → 종료 또는 창 닫기(X) 시 스케줄러와 재생이 함께 종료됩니다.\n"
            "- 백그라운드 실행분이 남을 경우 PowerShell에서 프로세스를 종료할 수 있습니다.\n\n"
            "8) 디폴트 수동 목록\n"
            "- 기본: 모든 항목 선택됨\n"
            "- config.yaml의 default_manual_indices로 변경 가능.\n\n"
            "FFmpeg 다운로드(옵션): https://www.gyan.dev/ffmpeg/builds/ , https://ffmpeg.org/download.html\n\n"
            "평상시 종소리 프로그램 developed by SN독학기숙학원\n"
        )
        help_txt.insert("1.0", help_content)
        help_txt.configure(state="disabled")

    def update_schedule_display(self):
        """현재 요일에 맞는 스케줄을 업데이트합니다."""
        try:
            zone = get_tz(self.config.get("timezone", "Asia/Seoul"))
            
            # 현재 요일에 맞는 스케줄 선택
            if is_sunday(zone):
                self.current_schedule = SUNDAY_SCHEDULE
                schedule_name = "일요일 스케줄"
            else:
                self.current_schedule = WEEKDAY_SCHEDULE
                schedule_name = "평일 스케줄 (월~토)"
            
            # 라벨 업데이트
            self.index_labels = [
                f"{idx:02d}-{time} {description}" 
                for idx, time, description in self.current_schedule
            ]
            
            # 체크박스 변수 개수 맞춤
            current_count = len(self.manual_check_vars)
            needed_count = len(self.current_schedule)
            
            if current_count < needed_count:
                # 부족한 만큼 추가
                for _ in range(needed_count - current_count):
                    self.manual_check_vars.append(tk.BooleanVar(value=True))
            elif current_count > needed_count:
                # 초과하는 것은 제거
                self.manual_check_vars = self.manual_check_vars[:needed_count]
            
            logging.info(f"스케줄 업데이트: {schedule_name} ({needed_count}개 항목)")
            
            # 체크박스 위젯이 이미 생성되어 있다면 텍스트 업데이트
            if hasattr(self, 'checkbox_widgets'):
                self.update_checkbox_widgets()
                
        except Exception as e:
            logging.error(f"스케줄 업데이트 중 오류: {e}")

    def update_checkbox_widgets(self):
        """체크박스 위젯들의 텍스트를 업데이트합니다."""
        try:
            if not hasattr(self, 'checkbox_widgets'):
                return
                
            # 기존 위젯들 제거
            for widget in self.checkbox_widgets:
                widget.destroy()
            
            # 새로운 체크박스 생성
            self.checkbox_widgets = []
            for i in range(len(self.current_schedule)):
                index, time_str, description = self.current_schedule[i]
                
                # 프레임 생성 (일요일 탭과 유사하게)
                row = i // 2
                col = i % 2
                
                frame = tk.Frame(self.grid)
                frame.grid(row=row, column=col, sticky="w", padx=5, pady=2)
                self.checkbox_widgets.append(frame)
                
                # 체크박스
                cb = tk.Checkbutton(frame, variable=self.manual_check_vars[i], width=2)
                cb.grid(row=0, column=0)
                
                # 인덱스 레이블
                index_label = tk.Label(frame, text=f"{index:2d}.", width=3, anchor="w", font=("Courier New", 9))
                index_label.grid(row=0, column=1, sticky="w")
                
                # 시간 레이블
                time_label = tk.Label(frame, text=time_str, width=6, anchor="w", font=("Courier New", 9, "bold"), fg="#1e90ff")
                time_label.grid(row=0, column=2, sticky="w")
                
                # 설명 레이블
                desc_label = tk.Label(frame, text=description, width=15, anchor="w", font=("맑은 고딕", 9))
                desc_label.grid(row=0, column=3, sticky="w")
                
                # 재생시간 레이블
                duration_label = tk.Label(frame, text="--", width=8, anchor="w", font=("Courier New", 8), fg="#666")
                duration_label.grid(row=0, column=4, sticky="w")

                # 마우스 휠 바인딩 추가
                def _on_mousewheel_main_local(event):
                    if hasattr(self, 'grid') and hasattr(self.grid, 'master'):
                        canvas = self.grid.master
                        if event.delta:
                            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                        else:
                            direction = -1 if getattr(event, "num", None) == 4 else 1
                            canvas.yview_scroll(direction, "units")

                # 프레임과 모든 자식 위젯에 바인딩
                for widget in [frame, cb, index_label, time_label, desc_label, duration_label]:
                    widget.bind("<MouseWheel>", _on_mousewheel_main_local)
                    widget.bind("<Button-4>", _on_mousewheel_main_local)
                    widget.bind("<Button-5>", _on_mousewheel_main_local)
            
            # 체크박스 생성 후 재생시간 새로고침
            self.root.after(100, self.refresh_durations)
                
        except Exception as e:
            logging.error(f"체크박스 위젯 업데이트 중 오류: {e}")

    def create_schedule_checkboxes(self):
        """현재 스케줄에 맞는 체크박스들을 생성합니다."""
        try:
            # 기존 체크박스들 제거
            for widget in self.checkbox_widgets:
                widget.destroy()
            self.checkbox_widgets = []
            
            # 현재 스케줄에 맞는 체크박스 생성
            for i in range(len(self.current_schedule)):
                if i < len(self.manual_check_vars):
                    cb = tk.Checkbutton(
                        self.grid,
                        text=self.index_labels[i],
                        variable=self.manual_check_vars[i],
                        anchor="w",
                        justify="left",
                    )
                    cb.grid(row=i, column=0, padx=4, pady=2, sticky="w")
                    self.checkbox_widgets.append(cb)
                    
        except Exception as e:
            logging.error(f"체크박스 생성 중 오류: {e}")

    def refresh_schedule(self):
        """현재 요일에 맞게 스케줄을 새로고침합니다."""
        try:
            self.update_schedule_display()
            self.create_schedule_checkboxes()
            self.refresh_durations()
            
            zone = get_tz(self.config.get("timezone", "Asia/Seoul"))
            if is_sunday(zone):
                self.var_status.set("일요일 스케줄로 업데이트됨")
            else:
                self.var_status.set("평일 스케줄로 업데이트됨 (월~토)")
        except Exception as e:
            self.var_status.set(f"스케줄 새로고침 오류: {e}")

    # ---------- Menu & basic actions ----------
    def on_exit(self):
        try:
            self.stop_manual()
            self.stop_main_clock()  # 메인 시계 정리
            stop_scheduler(self.sched)
        except Exception:
            pass
        self.root.destroy()

    def pick_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.var_sounds.set(folder)
            # update config immediately for duration refresh
            self.config["sounds_dir"] = folder
            self.refresh_durations()

    def pick_folder_sunday(self):
        """일요일 전용 사운드 폴더 선택"""
        folder = filedialog.askdirectory(title="일요일 사운드 폴더 선택")
        if folder:
            self.var_sounds_sunday.set(folder)
            # update config immediately for duration refresh
            self.config["sounds_dir_sunday"] = folder
            self.refresh_sunday_durations()

    def save_config(self):
        try:
            from app import validate_config
            
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(self.config)
            cfg["sounds_dir"] = self.var_sounds.get().strip() or None
            cfg["sounds_dir_sunday"] = self.var_sounds_sunday.get().strip() or None
            cfg["test_mode"] = bool(self.var_test.get())
            
            # 볼륨 값 검증
            try:
                v = float(self.var_volume.get())
                cfg["volume"] = v  # validate_config에서 범위 검증
            except ValueError:
                messagebox.showwarning("경고", "잘못된 볼륨 값입니다. 기본값을 사용합니다.")
                cfg["volume"] = 1.0
                self.var_volume.set(1.0)
            
            cfg["prefer_mci"] = bool(self.var_prefer_mci.get())
            
            # 설정 값 검증
            validated_cfg = validate_config(cfg)
            
            # 검증된 값들을 UI에 다시 반영
            if cfg["volume"] != validated_cfg["volume"]:
                self.var_volume.set(validated_cfg["volume"])
            if cfg["sounds_dir"] != validated_cfg.get("sounds_dir"):
                self.var_sounds.set(validated_cfg.get("sounds_dir") or "")
            
            with open(CONFIG_YAML, "w", encoding="utf-8") as f:
                yaml.safe_dump(validated_cfg, f, allow_unicode=True, sort_keys=False)
            self.config = validated_cfg
            self.var_status.set("설정 저장 완료")
            self.refresh_durations()
        except Exception as e:
            messagebox.showerror("오류", f"설정 저장 중 오류 발생: {str(e)}")

    # ---------- Scheduler control ----------
    def start(self):
        self.save_config()
        if self.sched is not None and getattr(self.sched, "running", False):
            self.var_status.set("이미 실행 중")
            return

        def _run():
            try:
                self.sched = start_scheduler(None, self.config, background=True)
                self.var_status.set("스케줄러 실행 중")
            except Exception as e:
                self.var_status.set(f"실행 오류: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def stop(self):
        try:
            stop_scheduler(self.sched)
            self.var_status.set("스케줄러 정지됨")
        except Exception as e:
            self.var_status.set(f"정지 오류: {e}")

    # ---------- Manual playback ----------
    def selected_indices(self):
        """선택된 체크박스에 해당하는 실제 스케줄 인덱스를 반환합니다."""
        selected = []
        for i, var in enumerate(self.manual_check_vars):
            if var.get() and i < len(self.current_schedule):
                # 현재 스케줄의 실제 인덱스 사용
                actual_index = self.current_schedule[i][0]
                selected.append(actual_index)
        return selected

    def clear_selection(self):
        for var in self.manual_check_vars:
            var.set(False)

    def select_all(self):
        for var in self.manual_check_vars:
            var.set(True)

    def select_defaults(self):
        # 모든 항목을 기본으로 선택
        for var in self.manual_check_vars:
            var.set(True)

    def play_selected(self):
        self.save_config()
        indices = self.selected_indices()
        if not indices:
            self.var_status.set("선택된 번호가 없습니다")
            return
        if self.manual_thread and self.manual_thread.is_alive():
            self.var_status.set("수동 재생 중입니다")
            return
        self.manual_stop_event.clear()

        def _play():
            try:
                zone = get_tz(self.config.get("timezone", "Asia/Seoul"))
                for idx in indices:
                    if self.manual_stop_event.is_set():
                        break
                    self.var_status.set(f"수동 재생: {idx:02d}")
                    play_sound_for_index(idx, self.config, zone)
                self.var_status.set("수동 재생 완료")
            except Exception as e:
                self.var_status.set(f"수동 재생 오류: {e}")
        self.manual_thread = threading.Thread(target=_play, daemon=True)
        self.manual_thread.start()

    def stop_manual(self):
        self.manual_stop_event.set()
        self.var_status.set("수동 재생 중지 요청")

    # ---------- Durations ----------
    def refresh_durations(self):
        """메인 탭의 사운드 재생시간 새로고침"""
        try:
            updated = False
            sounds_dir = self.var_sounds.get()
            logging.info(f"재생시간 새로고침 시작: sounds_dir={sounds_dir}, 스케줄 길이={len(self.current_schedule)}, 체크박스 길이={len(self.checkbox_widgets)}")
            
            # 현재 스케줄에 맞는 길이만 확인
            zone = get_tz(self.config.get("timezone", "Asia/Seoul"))
            for i in range(len(self.current_schedule)):
                if i < len(self.checkbox_widgets):
                    # 현재 스케줄의 실제 인덱스 사용
                    actual_index = self.current_schedule[i][0]
                    secs = get_sound_duration_seconds(actual_index, self.config, zone)
                    logging.debug(f"인덱스 {actual_index}: 재생시간 {secs}초")
                    
                    if secs and secs > 0:
                        duration_text = f"({secs:.1f}초)"
                    else:
                        # 테스트용: 사운드 파일이 없어도 더미 시간 표시
                        duration_text = f"(테스트{actual_index})"
                    
                    # 새로운 프레임 구조에서 duration_label 업데이트 (5번째 자식)
                    frame = self.checkbox_widgets[i]
                    children = frame.winfo_children()
                    logging.debug(f"프레임 {i}: 자식 위젯 개수 {len(children)}")
                    if len(children) >= 5:  # 체크박스, 인덱스, 시간, 설명, 재생시간
                        duration_label = children[4]  # 5번째 위젯
                        current_text = duration_label.cget("text")
                        if current_text != duration_text:
                            duration_label.config(text=duration_text)
                            logging.debug(f"재생시간 업데이트: {current_text} -> {duration_text}")
                            updated = True
                        else:
                            logging.debug(f"재생시간 동일: {current_text}")
                            
            if updated:
                self.var_status.set("길이 갱신 완료")
                logging.info("재생시간 갱신 완료")
            else:
                logging.debug("재생시간 업데이트할 항목 없음")
        except Exception as e:
            logging.debug(f"길이 갱신 중 오류: {e}")

    def refresh_all(self):
        try:
            # Reload config from file
            cfg = load_config(CONFIG_YAML)
            self.config = cfg
            # Reflect to UI controls
            self.var_sounds.set(self.config.get("sounds_dir") or "")
            self.var_sounds_sunday.set(self.config.get("sounds_dir_sunday") or "")
            self.var_test.set(bool(self.config.get("test_mode", False)))
            self.var_volume.set(float(self.config.get("volume", 1.0)))
            self.var_prefer_mci.set(bool(self.config.get("prefer_mci", False)))
            # Refresh durations
            self.refresh_durations()
            self.var_status.set("새로고침 완료")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    # ---------- Clock Window ----------
    def get_current_time(self):
        """현재 시간을 가져옵니다 (외부 동기화 우선, 실패 시 로컬 시간)."""
        from app import get_current_time as app_get_current_time
        
        if self.use_naver_time.get():
            # 외부 시간 동기화 사용
            return app_get_current_time()
        else:
            # 로컬 시간 사용
            return datetime.now()

    def open_clock_window(self):
        if self.clock_win and tk.Toplevel.winfo_exists(self.clock_win):
            try:
                self.clock_win.lift()
                self.clock_win.focus_force()
            except Exception:
                pass
            return

        self.clock_win = tk.Toplevel(self.root)
        self.clock_win.title("현재 시간")
        try:
            self.clock_win.attributes("-topmost", True)
        except Exception:
            pass
        self.clock_win.geometry("400x180")
        self.clock_win.resizable(False, False)

        # 네이버 시계 사용 체크박스
        clock_frame = tk.Frame(self.clock_win)
        clock_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Checkbutton(clock_frame, text="외부 시간 동기화 사용 (NTP/API)", 
                       variable=self.use_naver_time).pack(anchor="w")

        self.clock_label = tk.Label(self.clock_win, text="--:--:--", font=("Segoe UI", 28), padx=12, pady=12)
        self.clock_label.pack(fill=tk.BOTH, expand=True)

        def tick():
            try:
                now = self.get_current_time()
                time_str = now.strftime("%Y-%m-%d\n%H:%M:%S")
                if self.use_naver_time.get():
                    time_str += "\n(외부 동기화)"
                else:
                    time_str += "\n(로컬 시계)"
                self.clock_label.configure(text=time_str)
                if self.clock_win and tk.Toplevel.winfo_exists(self.clock_win):
                    self.clock_win.after(500, tick)
            except Exception:
                pass

        tick()

    def start_main_clock(self):
        """메인 화면 시계 업데이트 시작"""
        self.update_main_clock()

    def update_main_clock(self):
        """메인 화면 시계 및 날짜 업데이트"""
        try:
            # 현재 시간 가져오기 (기존 get_current_time 메서드 사용)
            now = self.get_current_time()
            
            # 시계 표시 (시:분:초)
            time_str = now.strftime("%H:%M:%S")
            if self.main_clock_label:
                self.main_clock_label.config(text=time_str)
            
            # 날짜 및 요일 표시
            date_str = now.strftime("%Y년 %m월 %d일")
            weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
            weekday = weekday_names[now.weekday()]
            
            # 요일 색상 설정 (일요일만 빨간색)
            if now.weekday() == 6:  # 일요일
                weekday_color = "#ff0000"  # 빨간색
                full_date_str = f"{date_str} ({weekday}요일)"
            else:
                weekday_color = "#333333"  # 기본 검은색
                full_date_str = f"{date_str} ({weekday}요일)"
            
            if self.main_date_label:
                self.main_date_label.config(text=full_date_str, fg=weekday_color)
            
            # 동기화 상태 표시
            if self.use_naver_time.get():
                sync_text = "NTP/API 동기화 활성"
                sync_color = "#008000"  # 녹색
            else:
                sync_text = "로컬 시계 사용"
                sync_color = "#666666"  # 회색
            
            if self.sync_status_label:
                self.sync_status_label.config(text=sync_text, fg=sync_color)
            
        except Exception as e:
            logging.warning(f"메인 시계 업데이트 실패: {e}")
        
        # 500ms 후 다시 업데이트
        if self.main_clock_label:
            self.clock_update_job = self.root.after(500, self.update_main_clock)

    def stop_main_clock(self):
        """메인 화면 시계 업데이트 정지"""
        if self.clock_update_job:
            self.root.after_cancel(self.clock_update_job)
            self.clock_update_job = None

    def on_sync_toggle(self):
        """외부 시간 동기화 토글 시 호출"""
        # 즉시 시계 업데이트하여 변경사항 반영
        self.update_main_clock()

    def setup_sunday_tab(self, tab_sunday):
        """일요일 전용 탭 설정"""
        frm_sunday = tk.Frame(tab_sunday)
        frm_sunday.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)

        # 일요일 사운드 폴더 설정 섹션
        tk.Label(frm_sunday, text="일요일 사운드 폴더", font=("맑은 고딕", 10, "bold")).grid(row=0, column=0, sticky="w")
        ent_sunday = tk.Entry(frm_sunday, textvariable=self.var_sounds_sunday, width=50)
        ent_sunday.grid(row=0, column=1, padx=5)
        tk.Button(frm_sunday, text="찾기", command=self.pick_folder_sunday).grid(row=0, column=2)
        
        # 수동 재생 섹션
        tk.Label(frm_sunday, text="수동 재생 (체크된 번호만)", font=("맑은 고딕", 11, "bold")).grid(row=1, column=0, columnspan=3, sticky="w")

        # 스크롤 가능한 컨테이너
        scroll_container_sunday = tk.Frame(frm_sunday)
        scroll_container_sunday.grid(row=2, column=0, columnspan=3, sticky="nsew")
        frm_sunday.grid_rowconfigure(2, weight=1)

        canvas_sunday = tk.Canvas(scroll_container_sunday, highlightthickness=0, width=520, height=300)
        vbar_sunday = tk.Scrollbar(scroll_container_sunday, orient="vertical", command=canvas_sunday.yview)
        canvas_sunday.configure(yscrollcommand=vbar_sunday.set)
        vbar_sunday.pack(side="right", fill="y")
        canvas_sunday.pack(side="left", fill="both", expand=True)

        self.grid_sunday = tk.Frame(canvas_sunday)
        canvas_sunday.create_window((0, 0), window=self.grid_sunday, anchor="nw")

        # 일요일 스케줄 체크박스들 생성
        self.sunday_checkbox_widgets = []
        self.sunday_index_labels = []
        self.create_sunday_checkboxes()

        def _on_configure_sunday(event):
            canvas_sunday.configure(scrollregion=canvas_sunday.bbox("all"))

        def _on_mousewheel_sunday(event):
            if event.delta:
                canvas_sunday.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                direction = -1 if getattr(event, "num", None) == 4 else 1
                canvas_sunday.yview_scroll(direction, "units")

        def _bind_mousewheel_sunday(event):
            canvas_sunday.bind_all("<MouseWheel>", _on_mousewheel_sunday)
            canvas_sunday.bind_all("<Button-4>", _on_mousewheel_sunday)
            canvas_sunday.bind_all("<Button-5>", _on_mousewheel_sunday)

        def _unbind_mousewheel_sunday(event):
            canvas_sunday.unbind_all("<MouseWheel>")
            canvas_sunday.unbind_all("<Button-4>")
            canvas_sunday.unbind_all("<Button-5>")

        self.grid_sunday.bind("<Configure>", _on_configure_sunday)
        
        # 일요일 탭 마우스 휠 바인딩
        canvas_sunday.bind("<Enter>", _bind_mousewheel_sunday)
        canvas_sunday.bind("<Leave>", _unbind_mousewheel_sunday)
        scroll_container_sunday.bind("<Enter>", _bind_mousewheel_sunday)
        scroll_container_sunday.bind("<Leave>", _unbind_mousewheel_sunday)

        # 일요일 전용 컨트롤 버튼들
        ctrl_sunday = tk.Frame(frm_sunday)
        ctrl_sunday.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))
        tk.Button(ctrl_sunday, text="선택 재생", command=self.play_selected_sunday).grid(row=0, column=0, padx=(0, 6))
        tk.Button(ctrl_sunday, text="선택 해제", command=self.clear_selection_sunday).grid(row=0, column=1, padx=(0, 6))
        tk.Button(ctrl_sunday, text="모두 선택", command=self.select_all_sunday).grid(row=0, column=2, padx=(0, 6))
        tk.Button(ctrl_sunday, text="수동 정지", command=self.stop_manual_sunday).grid(row=0, column=3, padx=(0, 6))
        tk.Button(ctrl_sunday, text="디폴트 선택", command=self.select_defaults_sunday).grid(row=0, column=4)

        for i in range(3):
            frm_sunday.grid_columnconfigure(i, weight=1)

    def create_sunday_checkboxes(self):
        """일요일 스케줄용 체크박스들 생성"""
        # 기존 위젯들 제거
        for widget in self.sunday_checkbox_widgets:
            widget.destroy()
        self.sunday_checkbox_widgets.clear()
        
        # 기존 변수들 제거
        self.sunday_check_vars.clear()
        self.sunday_index_labels.clear()

        # SUNDAY_SCHEDULE에 맞게 체크박스 생성 (1열 배치)
        for i, (index, time_str, description) in enumerate(SUNDAY_SCHEDULE):
            var = tk.BooleanVar()
            self.sunday_check_vars.append(var)
            
            frame = tk.Frame(self.grid_sunday)
            frame.grid(row=i, column=0, sticky="w", padx=5, pady=2)
            self.sunday_checkbox_widgets.append(frame)
            
            cb = tk.Checkbutton(frame, variable=var, width=2)
            cb.grid(row=0, column=0)
            
            # 인덱스 레이블
            index_label = tk.Label(frame, text=f"{index:2d}.", width=3, anchor="w", font=("Courier New", 9))
            index_label.grid(row=0, column=1, sticky="w")
            self.sunday_index_labels.append(index_label)
            
            # 시간 레이블
            time_label = tk.Label(frame, text=time_str, width=6, anchor="w", font=("Courier New", 9, "bold"), fg="#1e90ff")
            time_label.grid(row=0, column=2, sticky="w")
            
            # 설명 레이블
            desc_label = tk.Label(frame, text=description, width=15, anchor="w", font=("맑은 고딕", 9))
            desc_label.grid(row=0, column=3, sticky="w")
            
            # 재생시간 레이블 (나중에 업데이트됨)
            duration_label = tk.Label(frame, text="--", width=8, anchor="w", font=("Courier New", 8), fg="#666")
            duration_label.grid(row=0, column=4, sticky="w")

            # 새로 생성된 프레임과 자식 위젯들에 마우스 휠 바인딩 추가
            def _on_mousewheel_sunday_local(event):
                if hasattr(self, 'grid_sunday') and hasattr(self.grid_sunday, 'master'):
                    canvas_sunday = self.grid_sunday.master
                    if event.delta:
                        canvas_sunday.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    else:
                        direction = -1 if getattr(event, "num", None) == 4 else 1
                        canvas_sunday.yview_scroll(direction, "units")

            # 프레임과 모든 자식 위젯에 바인딩
            for widget in [frame, cb, index_label, time_label, desc_label, duration_label]:
                widget.bind("<MouseWheel>", _on_mousewheel_sunday_local)
                widget.bind("<Button-4>", _on_mousewheel_sunday_local)
                widget.bind("<Button-5>", _on_mousewheel_sunday_local)

        # 재생시간 업데이트
        self.root.after(300, self.refresh_sunday_durations)

    def refresh_sunday_durations(self):
        """일요일 스케줄의 사운드 재생시간 새로고침"""
        sounds_dir = self.var_sounds.get()
        if not sounds_dir or not os.path.exists(sounds_dir):
            return
            
        zone = get_tz(self.config.get("timezone", "Asia/Seoul"))
        for i, (index, time_str, description) in enumerate(SUNDAY_SCHEDULE):
            try:
                duration = get_sound_duration_seconds(index, self.config, zone)
                if duration and duration > 0:
                    duration_text = f"({duration:.1f}초)"
                else:
                    duration_text = "(없음)"
                
                # duration_label 업데이트 (각 프레임의 5번째 자식)
                if i < len(self.sunday_checkbox_widgets):
                    frame = self.sunday_checkbox_widgets[i]
                    children = frame.winfo_children()
                    if len(children) >= 5:  # 체크박스, 인덱스, 시간, 설명, 재생시간
                        duration_label = children[4]  # 5번째 위젯
                        duration_label.config(text=duration_text)
            except Exception as e:
                logging.warning(f"일요일 사운드 {index} 재생시간 확인 실패: {e}")

    def play_selected_sunday(self):
        """일요일 선택된 종소리 재생"""
        if self.sunday_manual_thread and self.sunday_manual_thread.is_alive():
            messagebox.showwarning("알림", "이미 일요일 수동 재생이 실행 중입니다.")
            return

        selected = [i for i, var in enumerate(self.sunday_check_vars) if var.get()]
        if not selected:
            messagebox.showwarning("알림", "일요일 스케줄에서 재생할 항목을 선택하세요.")
            return

        sounds_dir = self.var_sounds.get()
        if not sounds_dir or not os.path.exists(sounds_dir):
            messagebox.showerror("오류", "사운드 폴더를 먼저 설정하세요.")
            return

        self.sunday_manual_stop_event.clear()
        self.sunday_manual_thread = threading.Thread(
            target=self._play_sunday_worker, 
            args=(selected, sounds_dir),
            daemon=True
        )
        self.sunday_manual_thread.start()

    def _play_sunday_worker(self, selected_indices, sounds_dir):
        """일요일 수동 재생 작업 스레드"""
        try:
            for i in selected_indices:
                if self.sunday_manual_stop_event.is_set():
                    break
                    
                if i < len(SUNDAY_SCHEDULE):
                    index, time_str, description = SUNDAY_SCHEDULE[i]
                    logging.info(f"일요일 수동 재생: {index}. {time_str} {description}")
                    
                    # UI 업데이트
                    self.root.after(0, lambda: self.var_status.set(f"일요일 재생 중: {index}. {description}"))
                    
                    play_sound_for_index_sunday(index, self.config)
                    
                    # 다음 재생까지 1초 대기 (정지 이벤트 확인)
                    if not self.sunday_manual_stop_event.wait(1.0):
                        continue
                    else:
                        break
        except Exception as e:
            logging.error(f"일요일 수동 재생 오류: {e}")
        finally:
            self.root.after(0, lambda: self.var_status.set("대기"))

    def clear_selection_sunday(self):
        """일요일 선택 해제"""
        for var in self.sunday_check_vars:
            var.set(False)

    def select_all_sunday(self):
        """일요일 모두 선택"""
        for var in self.sunday_check_vars:
            var.set(True)

    def stop_manual_sunday(self):
        """일요일 수동 재생 정지"""
        self.sunday_manual_stop_event.set()
        if self.sunday_manual_thread and self.sunday_manual_thread.is_alive():
            self.sunday_manual_thread.join(timeout=2.0)

    def select_defaults_sunday(self):
        """일요일 디폴트 선택 (주요 시간대만)"""
        self.clear_selection_sunday()
        # 기상, 입실, 시작, 식사시간종, 하루일과 종료 등 주요 항목만 선택
        important_times = ["07:00", "10:50", "11:00", "12:10", "13:00", "17:30", "18:30", "22:30"]
        for i, (index, time_str, description) in enumerate(SUNDAY_SCHEDULE):
            if time_str in important_times and i < len(self.sunday_check_vars):
                self.sunday_check_vars[i].set(True)


def main():
    root = tk.Tk()
    app = BellRegularGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
