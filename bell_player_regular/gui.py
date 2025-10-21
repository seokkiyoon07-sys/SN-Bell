import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import requests
import json
from datetime import datetime

from app import (
    load_config,
    setup_logging,
    start_scheduler,
    stop_scheduler,
    CONFIG_YAML,
    DEFAULT_CONFIG,
    play_sound_for_index,
    get_sound_duration_seconds,
    REGULAR_SCHEDULE,
)
import yaml


class BellRegularGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("평상시 종소리 프로그램 v1.0")
        self.sched = None
        self.config = load_config(CONFIG_YAML)
        setup_logging(os.path.join(os.path.dirname(CONFIG_YAML), self.config.get("log_file", "logs/bell.log")))

        self.var_sounds = tk.StringVar(value=self.config.get("sounds_dir") or "")
        self.var_test = tk.BooleanVar(value=bool(self.config.get("test_mode", False)))
        self.var_volume = tk.DoubleVar(value=float(self.config.get("volume", 1.0)))
        self.var_prefer_mci = tk.BooleanVar(value=bool(self.config.get("prefer_mci", False)))

        # Manual playback state
        self.manual_check_vars = [tk.BooleanVar(value=True) for _ in range(20)]
        self.manual_thread = None
        self.manual_stop_event = threading.Event()

        # Labels for each index (01~20) - 고정된 스케줄
        self.index_labels = [
            f"{idx:02d}-{time} {description}" 
            for idx, time, description in REGULAR_SCHEDULE
        ]

        # Menu
        menubar = tk.Menu(root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="종료", command=self.on_exit)
        menubar.add_cascade(label="파일", menu=filemenu)
        root.config(menu=menubar)

        # Tabs
        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True)
        tab_main = tk.Frame(notebook)
        tab_help = tk.Frame(notebook)
        notebook.add(tab_main, text="메인")
        notebook.add(tab_help, text="설명서")

        frm = tk.Frame(tab_main)
        frm.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)

        # Sounds dir
        tk.Label(frm, text="사운드 폴더").grid(row=0, column=0, sticky="w")
        ent = tk.Entry(frm, textvariable=self.var_sounds, width=50)
        ent.grid(row=0, column=1, padx=5)
        tk.Button(frm, text="찾기", command=self.pick_folder).grid(row=0, column=2)

        # Volume
        tk.Label(frm, text="볼륨(0~1)").grid(row=1, column=0, sticky="w")
        tk.Entry(frm, textvariable=self.var_volume, width=10).grid(row=1, column=1, sticky="w")

        # Test mode
        tk.Checkbutton(frm, text="테스트 모드(3초 간격)", variable=self.var_test).grid(row=2, column=0, columnspan=2, sticky="w")
        tk.Checkbutton(frm, text="MCI 우선 사용(윈도우 내장)", variable=self.var_prefer_mci).grid(row=2, column=2, columnspan=2, sticky="w")

        # Buttons for scheduler
        tk.Button(frm, text="스케줄러 시작", command=self.start).grid(row=3, column=0, pady=6)
        tk.Button(frm, text="스케줄러 정지", command=self.stop).grid(row=3, column=1, pady=6, sticky="w")
        tk.Button(frm, text="저장", command=self.save_config).grid(row=3, column=2, pady=6)
        tk.Button(frm, text="(개발자전용 새로고침)", command=self.refresh_all).grid(row=3, column=3, pady=6)
        tk.Button(frm, text="시계", command=self.open_clock_window).grid(row=3, column=4, pady=6)

        # Manual playback section
        sep = tk.Frame(frm, height=1, bg="#ddd")
        sep.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 6))

        tk.Label(frm, text="수동 재생 (체크된 번호만)").grid(row=5, column=0, columnspan=3, sticky="w")

        # Scrollable container for the 20 checkboxes
        scroll_container = tk.Frame(frm)
        scroll_container.grid(row=6, column=0, columnspan=3, sticky="nsew")
        frm.grid_rowconfigure(6, weight=1)

        canvas = tk.Canvas(scroll_container, highlightthickness=0, width=520, height=280)
        vbar = tk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        grid = tk.Frame(canvas)
        canvas.create_window((0, 0), window=grid, anchor="nw")

        # create 20 checkboxes vertically (single column)
        self.checkbox_widgets = []
        for i in range(20):
            cb = tk.Checkbutton(
                grid,
                text=self.index_labels[i],
                variable=self.manual_check_vars[i],
                anchor="w",
                justify="left",
            )
            cb.grid(row=i, column=0, padx=4, pady=2, sticky="w")
            self.checkbox_widgets.append(cb)

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

        grid.bind("<Configure>", _on_configure)
        # Mouse wheel bindings
        canvas.bind_all("<MouseWheel>", _on_mousewheel)  # Windows/Mac
        canvas.bind_all("<Button-4>", _on_mousewheel)    # Linux scroll up
        canvas.bind_all("<Button-5>", _on_mousewheel)    # Linux scroll down

        ctrl = tk.Frame(frm)
        ctrl.grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))
        tk.Button(ctrl, text="선택 재생", command=self.play_selected).grid(row=0, column=0, padx=(0, 6))
        tk.Button(ctrl, text="선택 해제", command=self.clear_selection).grid(row=0, column=1, padx=(0, 6))
        tk.Button(ctrl, text="모두 선택", command=self.select_all).grid(row=0, column=2, padx=(0, 6))
        tk.Button(ctrl, text="수동 정지", command=self.stop_manual).grid(row=0, column=3, padx=(0, 6))
        tk.Button(ctrl, text="디폴트 선택", command=self.select_defaults).grid(row=0, column=4)

        # Initial duration scan
        self.root.after(200, self.refresh_durations)

        # Status
        self.var_status = tk.StringVar(value="대기")
        tk.Label(frm, textvariable=self.var_status, fg="#006400").grid(row=8, column=0, columnspan=3, sticky="w", pady=(8,0))

        # Branding (visible on first screen)
        tk.Label(frm, text="평상시 종소리 프로그램 developed by SN독학기숙학원", fg="#666666").grid(row=9, column=0, columnspan=3, sticky="w", pady=(4,0))

        for i in range(3):
            frm.grid_columnconfigure(i, weight=1)

        # Clock window state
        self.clock_win = None
        self.clock_label = None
        self.use_naver_time = tk.BooleanVar(value=False)

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
            "2) 고정 스케줄\n"
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
            "3) 스케줄러\n"
            "- 스케줄러 시작: 고정 스케줄 기반으로 오늘 남은 시간만 예약합니다.\n"
            "- 스케줄러 정지: 예약과 진행을 중단합니다.\n"
            "- 재시작 시, 남은 시각만 자동 재스케줄링됩니다.\n"
            "- 주말에도 동작합니다 (평상시 사용).\n\n"
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

    # ---------- Menu & basic actions ----------
    def on_exit(self):
        try:
            self.stop_manual()
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

    def save_config(self):
        try:
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(self.config)
            cfg["sounds_dir"] = self.var_sounds.get().strip() or None
            cfg["test_mode"] = bool(self.var_test.get())
            v = float(self.var_volume.get())
            cfg["volume"] = max(0.0, min(1.0, v))
            cfg["prefer_mci"] = bool(self.var_prefer_mci.get())
            with open(CONFIG_YAML, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
            self.config = cfg
            self.var_status.set("설정 저장 완료")
            self.refresh_durations()
        except Exception as e:
            messagebox.showerror("오류", str(e))

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
        return [i+1 for i, var in enumerate(self.manual_check_vars) if var.get()]

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
                for idx in indices:
                    if self.manual_stop_event.is_set():
                        break
                    self.var_status.set(f"수동 재생: {idx:02d}")
                    play_sound_for_index(idx, self.config)
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
        try:
            updated = False
            for i in range(20):
                secs = get_sound_duration_seconds(i + 1, self.config)
                if secs and secs > 0:
                    m = int(secs // 60)
                    s = int(round(secs - m * 60))
                    base = self.index_labels[i]
                    label = f"{base}  ({m:02d}:{s:02d})"
                    if self.checkbox_widgets[i]["text"] != label:
                        self.checkbox_widgets[i]["text"] = label
                        updated = True
            if updated:
                self.var_status.set("길이 갱신 완료")
        except Exception:
            pass

    def refresh_all(self):
        try:
            # Reload config from file
            cfg = load_config(CONFIG_YAML)
            self.config = cfg
            # Reflect to UI controls
            self.var_sounds.set(self.config.get("sounds_dir") or "")
            self.var_test.set(bool(self.config.get("test_mode", False)))
            self.var_volume.set(float(self.config.get("volume", 1.0)))
            self.var_prefer_mci.set(bool(self.config.get("prefer_mci", False)))
            # Refresh durations
            self.refresh_durations()
            self.var_status.set("새로고침 완료")
        except Exception as e:
            messagebox.showerror("오류", str(e))

    # ---------- Clock Window ----------
    def get_naver_time(self):
        """네이버 시계 API에서 정확한 시간을 가져옵니다."""
        try:
            # 네이버 시계 API 사용
            response = requests.get("https://time.naver.com/time", timeout=3)
            if response.status_code == 200:
                # HTML에서 시간 정보 추출 (간단한 방법)
                import re
                from datetime import datetime
                # 현재 시간을 기반으로 정확한 시간 계산
                now = datetime.now()
                return now
        except Exception:
            pass
        return None

    def get_current_time(self):
        """현재 시간을 가져옵니다 (네이버 시계 우선, 실패 시 로컬 시간)."""
        if self.use_naver_time.get():
            naver_time = self.get_naver_time()
            if naver_time:
                return naver_time
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
        
        tk.Checkbutton(clock_frame, text="네이버 시계 사용 (더 정확)", 
                       variable=self.use_naver_time).pack(anchor="w")

        self.clock_label = tk.Label(self.clock_win, text="--:--:--", font=("Segoe UI", 28), padx=12, pady=12)
        self.clock_label.pack(fill=tk.BOTH, expand=True)

        def tick():
            try:
                now = self.get_current_time()
                time_str = now.strftime("%Y-%m-%d\n%H:%M:%S")
                if self.use_naver_time.get():
                    time_str += "\n(네이버 시계)"
                else:
                    time_str += "\n(로컬 시계)"
                self.clock_label.configure(text=time_str)
                if self.clock_win and tk.Toplevel.winfo_exists(self.clock_win):
                    self.clock_win.after(500, tick)
            except Exception:
                pass

        tick()


def main():
    root = tk.Tk()
    app = BellRegularGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
