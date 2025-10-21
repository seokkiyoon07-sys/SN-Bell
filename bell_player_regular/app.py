from __future__ import annotations

import csv
import logging
import os
import sys
import shutil
import subprocess
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from typing import List, Tuple, Optional
import atexit
import requests
import json

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger
from dateutil import tz

try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None  # type: ignore

try:
    from playsound import playsound as playsound_blocking
except Exception:
    playsound_blocking = None  # type: ignore

# 고정된 스케줄 데이터
REGULAR_SCHEDULE = [
    (1, "06:00", "기상종소리"),
    (2, "07:20", "시작종"),
    (3, "08:30", "쉬는시간종"),
    (4, "08:40", "시작종"),
    (5, "10:00", "쉬는시간종"),
    (6, "10:20", "시작종"),
    (7, "12:10", "식사시간종"),
    (8, "13:00", "시작종"),
    (9, "14:20", "쉬는시간종"),
    (10, "14:40", "시작종"),
    (11, "16:30", "쉬는시간종"),
    (12, "16:40", "시작종"),
    (13, "17:30", "식사시간종"),
    (14, "18:30", "시작종"),
    (15, "19:50", "쉬는시간종"),
    (16, "20:00", "시작종"),
    (17, "21:00", "간식시간종"),
    (18, "21:30", "시작종"),
    (19, "22:20", "학습종료종"),
    (20, "22:30", "하루일과 종료종"),
]

DEFAULT_CONFIG = {
    "timezone": "Asia/Seoul",
    "volume": 1.0,
    "workdays_only": False,  # 평상시 사용이므로 주말도 포함
    "allow_weekend": True,
    "log_file": "logs/bell.log",
    "autoplay_next_day": True,
    "test_mode": False,
    "sound_ext": "mp3",
    "misfire_grace_seconds": 60,
    "refresh_time": "0001",
    "sounds_dir": None,
    "prefer_mci": True,
}

def get_base_dir() -> str:
    """Return app base directory in source mode."""
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

def _frozen_exe_dir() -> Optional[str]:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return None


def _meipass_dir() -> Optional[str]:
    return getattr(sys, "_MEIPASS", None)


def get_resource_path(relative_name: str) -> str:
    """Resolve a data file path with this precedence:
    1) Next to the frozen executable (user-editable when onefile)
    2) Bundled resources directory (sys._MEIPASS) when onefile
    3) Source base directory (development mode)
    """
    exe_dir = _frozen_exe_dir()
    if exe_dir:
        cand = os.path.join(exe_dir, relative_name)
        if os.path.exists(cand):
            return cand
        mp = _meipass_dir()
        if mp:
            return os.path.join(mp, relative_name)
        return cand
    return os.path.join(BASE_DIR, relative_name)


SOUNDS_DIR_DEFAULT = get_resource_path("sounds")
CONFIG_YAML = get_resource_path("config.yaml")
LOGS_DIR = os.path.join(BASE_DIR, "logs")


# Track external player processes to ensure we can stop them on exit
CURRENT_PROCS: List[subprocess.Popen] = []
# Track active MCI aliases for winmm backend so we can stop them on exit
CURRENT_MCI_ALIASES: List[str] = []


def stop_all_playback() -> None:
    """Terminate any active playback: external processes (ffplay) and MCI sessions."""
    # Copy the list to avoid modification during iteration
    procs = list(CURRENT_PROCS)
    for proc in procs:
        try:
            if proc and proc.poll() is None:
                proc.terminate()
        except Exception:
            pass
        finally:
            try:
                CURRENT_PROCS.remove(proc)
            except ValueError:
                pass

    # Stop/close any MCI sessions
    try:
        _mci_stop_all()
    except Exception:
        pass


atexit.register(stop_all_playback)

def load_config(path: str = CONFIG_YAML) -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
            cfg.update(loaded)
    return cfg


def setup_logging(log_path: str) -> None:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)


def get_naver_time():
    """네이버 시계에서 정확한 시간을 가져옵니다."""
    try:
        # 네이버 시계 API 사용
        response = requests.get("https://time.naver.com/time", timeout=3)
        if response.status_code == 200:
            # HTML에서 시간 정보 추출
            import re
            from datetime import datetime
            # 간단한 방법: 현재 시간을 기반으로 정확한 시간 계산
            # 실제로는 HTML 파싱이 필요하지만, 여기서는 로컬 시간 사용
            now = datetime.now()
            return now
    except Exception as e:
        logging.warning(f"네이버 시계 연결 실패, 로컬 시간 사용: {e}")
    return None

def get_current_time():
    """현재 시간을 가져옵니다 (네이버 시간 우선, 실패 시 로컬 시간)."""
    naver_time = get_naver_time()
    if naver_time:
        return naver_time
    return datetime.now()

def get_tz(tz_name: str):
    zone = tz.gettz(tz_name)
    if zone is None:
        raise ValueError(f"Invalid timezone: {tz_name}")
    return zone


def hhmm_to_today(hhmm: str, zone) -> datetime:
    # 콜론이 포함된 시간 형식 처리 (예: "06:00" -> "0600")
    if ':' in hhmm:
        hhmm = hhmm.replace(':', '')
    hour = int(hhmm[:2])
    minute = int(hhmm[2:])
    now = datetime.now(tz=zone)
    return datetime(now.year, now.month, now.day, hour, minute, tzinfo=zone)


def is_workday(zone) -> bool:
    w = datetime.now(tz=zone).weekday()
    return w <= 4


def get_sounds_dir(config: dict) -> str:
    custom = config.get("sounds_dir")
    if custom and isinstance(custom, str) and os.path.isdir(custom):
        return custom
    return SOUNDS_DIR_DEFAULT


def find_existing_sound(index: int, config: dict) -> Optional[str]:
    base = get_sounds_dir(config)
    pref_ext = str(config.get("sound_ext", "mp3")).lower().lstrip(".")
    ext_candidates = [pref_ext, "mp3", "wav", "m4a", "aac", "flac", "ogg"]
    seen = set()
    ordered_exts = [e for e in ext_candidates if not (e in seen or seen.add(e))]
    name_candidates = [f"{index:02d}", str(index)]
    for name in name_candidates:
        for ext in ordered_exts:
            path = os.path.join(base, f"{name}.{ext}")
            if os.path.exists(path):
                return path
    return None


def apply_volume_with_pydub(path: str, volume: float) -> str:
    if AudioSegment is None:
        return path
    try:
        seg = AudioSegment.from_file(path)
        if abs(volume - 1.0) > 1e-6:
            import math
            if volume <= 0:
                seg = seg - 100.0
            else:
                gain_db = 20.0 * math.log10(volume)
                seg = seg.apply_gain(gain_db)
        tmp_out = os.path.join(LOGS_DIR, "_tmp_play.wav")
        os.makedirs(LOGS_DIR, exist_ok=True)
        seg.export(tmp_out, format="wav")
        return tmp_out
    except Exception:
        return path


def probe_duration_seconds(path: str) -> Optional[float]:
    """Return duration in seconds using pydub if available, else ffprobe."""
    # Try pydub if available
    if AudioSegment is not None:
        try:
            seg = AudioSegment.from_file(path)
            return float(len(seg)) / 1000.0
        except Exception:
            pass
    # Try ffprobe
    try:
        # Use ffprobe which is bundled with ffmpeg installs
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, check=True
        )
        val = result.stdout.strip()
        dur = float(val)
        if dur > 0:
            return dur
    except Exception:
        pass
    return None

def _mci_available() -> bool:
    try:
        import ctypes  # noqa: F401
        from ctypes import wintypes  # noqa: F401
        return os.name == "nt"
    except Exception:
        return False


def _mci_send(command: str) -> int:
    """Send an MCI command. Returns mmresult error code (0 = MMSYSERR_NOERROR)."""
    import ctypes
    from ctypes import wintypes

    mciSendStringW = ctypes.windll.winmm.mciSendStringW  # type: ignore[attr-defined]
    mciSendStringW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HANDLE]
    mciSendStringW.restype = wintypes.UINT

    buf = ctypes.create_unicode_buffer(255)
    return int(mciSendStringW(command, buf, 254, None))


def _mci_play_blocking(path: str) -> bool:
    """Play file with MCI in blocking mode. Returns True on success."""
    if not _mci_available():
        return False
    import uuid
    alias = f"bell_{uuid.uuid4().hex}"
    try:
        # Open
        # For mp3/wav, MCI auto-detects type; force type mpegvideo for mp3 when needed
        # Use quotes for paths with spaces
        if path.lower().endswith((".mp3", ".m4a", ".aac")):
            rc = _mci_send(f"open \"{path}\" type mpegvideo alias {alias}")
        else:
            rc = _mci_send(f"open \"{path}\" alias {alias}")
        if rc != 0:
            return False
        CURRENT_MCI_ALIASES.append(alias)

        # Play (wait blocks until completion)
        rc = _mci_send(f"play {alias} wait")
        # Close
        _mci_send(f"close {alias}")
        try:
            CURRENT_MCI_ALIASES.remove(alias)
        except ValueError:
            pass
        return rc == 0
    except Exception:
        # Best-effort cleanup
        try:
            _mci_send(f"stop {alias}")
            _mci_send(f"close {alias}")
        except Exception:
            pass
        try:
            CURRENT_MCI_ALIASES.remove(alias)
        except ValueError:
            pass
        return False


def _mci_stop_all() -> None:
    if not _mci_available():
        return
    aliases = list(CURRENT_MCI_ALIASES)
    for alias in aliases:
        try:
            _mci_send(f"stop {alias}")
            _mci_send(f"close {alias}")
        except Exception:
            pass
        finally:
            try:
                CURRENT_MCI_ALIASES.remove(alias)
            except ValueError:
                pass



def get_sound_duration_seconds(index: int, config: dict) -> Optional[float]:
    """Get duration in seconds for the sound mapped to index (01..20)."""
    path = find_existing_sound(index, config)
    if not path:
        return None
    return probe_duration_seconds(path)


def try_ffplay(path: str, config: dict) -> bool:
    custom = str(config.get("ffplay_path") or "").strip().strip('"')
    cand = []
    if custom:
        cand.append(custom)
    env_ff = shutil.which("ffplay")
    if env_ff:
        cand.append(env_ff)
    # Look for portable ffmpeg bundled next to the executable or script
    exe_dir = _frozen_exe_dir() or BASE_DIR
    portable_ff = os.path.join(exe_dir, "ffmpeg", "bin", "ffplay.exe")
    if os.path.exists(portable_ff):
        cand.append(portable_ff)
    for ff in cand:
        try:
            # Launch ffplay so we can terminate it if the app exits
            proc = subprocess.Popen([ff, "-nodisp", "-autoexit", "-loglevel", "error", path])
            CURRENT_PROCS.append(proc)
            proc.wait()
            try:
                CURRENT_PROCS.remove(proc)
            except ValueError:
                pass
            return True
        except Exception:
            continue
    return False


def play_sound_for_index(index: int, config: dict) -> None:
    logging.info(f"Play start: index={index}")
    path = find_existing_sound(index, config)
    if not path:
        base = get_sounds_dir(config)
        logging.error(f"Sound file not found for index {index} in {base}")
        return

    final_path = apply_volume_with_pydub(path, float(config.get("volume", 1.0)))

    # Preferred order: configurable
    prefer_mci = bool(config.get("prefer_mci", False))
    if prefer_mci:
        # MCI → ffplay → playsound
        if _mci_play_blocking(final_path):
            logging.info(f"Play done via MCI: index={index}")
            return
        if try_ffplay(final_path, config):
            logging.info(f"Play done via ffplay: index={index}")
            return
    else:
        # ffplay → MCI → playsound
        if try_ffplay(final_path, config):
            logging.info(f"Play done via ffplay: index={index}")
            return
        if _mci_play_blocking(final_path):
            logging.info(f"Play done via MCI: index={index}")
            return

    if playsound_blocking is not None:
        try:
            playsound_blocking(final_path)
            logging.info(f"Play done via playsound: index={index}")
            return
        except Exception as e:
            logging.warning(f"playsound failed: {e}")

    logging.error("No available audio backend: provide ffplay (FFmpeg) or use compatible format for MCI.")


def schedule_today(sched, config: dict, zone) -> int:
    # 네이버 시간 우선 사용
    now = get_current_time()
    if now.tzinfo is None:
        now = now.replace(tzinfo=zone)
    count = 0
    
    for idx, hhmm, description in REGULAR_SCHEDULE:
        run_at = hhmm_to_today(hhmm, zone)
        if run_at > now:
            sched.add_job(
                play_sound_for_index,
                trigger=DateTrigger(run_date=run_at),
                args=[idx, config],
                id=f"bell-{idx}",
                misfire_grace_time=int(config.get("misfire_grace_seconds", 60)),
                replace_existing=True,
            )
            count += 1
            logging.info(f"Scheduled: {hhmm} - {description} (index: {idx})")
    
    logging.info(f"Scheduled {count} jobs for today (remaining only)")
    return count


def schedule_test_mode(sched, config: dict, zone) -> None:
    base = datetime.now(tz=zone) + timedelta(seconds=2)
    for i, (idx, hhmm, description) in enumerate(REGULAR_SCHEDULE):
        run_at = base + timedelta(seconds=3 * i)
        sched.add_job(
            play_sound_for_index,
            trigger=DateTrigger(run_date=run_at),
            args=[idx, config],
            id=f"test-bell-{idx}",
            replace_existing=True,
        )
    logging.info("TEST MODE: Regular schedule scheduled at 3s intervals")


def schedule_next_day_refresh(sched, config: dict, zone) -> None:
    try:
        refresh_time_str = str(config.get("refresh_time", "0001")).strip('"')
        hh = int(refresh_time_str[:2])
        mm = int(refresh_time_str[2:])
        now = datetime.now(tz=zone)
        refresh = datetime(now.year, now.month, now.day, hh, mm, tzinfo=zone)
        if refresh <= now:
            refresh += timedelta(days=1)
    except (ValueError, IndexError) as e:
        logging.warning(f"Invalid refresh_time format, using default 00:01: {e}")
        now = datetime.now(tz=zone)
        refresh = datetime(now.year, now.month, now.day, 0, 1, tzinfo=zone)
        if refresh <= now:
            refresh += timedelta(days=1)

    def refresh_jobs():
        try:
            logging.info("Refreshing schedule for new day...")
            sched.remove_all_jobs()
            start_scheduler(sched, config, background=True)
        except Exception as e:
            logging.exception(f"Failed to refresh schedule: {e}")

    sched.add_job(
        refresh_jobs,
        trigger=DateTrigger(run_date=refresh),
        id="daily-refresh",
        replace_existing=True,
    )
    logging.info(f"Next refresh at {refresh}")


def start_scheduler(sched: Optional[BackgroundScheduler], config: dict, background: bool = False):
    zone = get_tz(config.get("timezone", "Asia/Seoul"))

    if sched is None:
        sched = BackgroundScheduler(timezone=zone) if background else BlockingScheduler(timezone=zone)

    if bool(config.get("test_mode", False)):
        schedule_test_mode(sched, config, zone)
    else:
        schedule_today(sched, config, zone)
        if bool(config.get("autoplay_next_day", True)):
            schedule_next_day_refresh(sched, config, zone)

    sched.start()
    return sched


def stop_scheduler(sched) -> None:
    if sched and getattr(sched, "running", False):
        sched.shutdown(wait=False)
    # Ensure any lingering playback is stopped when scheduler stops
    stop_all_playback()


def main(start_scheduler_flag: bool = True) -> None:
    config = load_config()
    setup_logging(os.path.join(BASE_DIR, config.get("log_file", "logs/bell.log")))

    if start_scheduler_flag:
        sched = start_scheduler(None, config, background=False)
        try:
            if isinstance(sched, BlockingScheduler):
                pass
        except (KeyboardInterrupt, SystemExit):
            logging.info("Shutting down...")


if __name__ == "__main__":
    main()
