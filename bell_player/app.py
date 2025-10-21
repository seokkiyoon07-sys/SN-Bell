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

DEFAULT_CONFIG = {
    "timezone": "Asia/Seoul",
    "volume": 1.0,
    "workdays_only": True,
    "allow_weekend": False,
    "log_file": "logs/bell.log",
    "start_time": "0805",
    "end_time": "1637",
    "autoplay_next_day": True,
    "test_mode": False,
    "sound_ext": "mp3",
    "misfire_grace_seconds": 60,
    "refresh_time": "00:01",
    "sounds_dir": None,
    "default_manual_indices": [5, 7, 11, 13, 16, 18, 22, 24, 27, 29, 31],
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
SCHEDULE_CSV = get_resource_path("schedule.csv")
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


def get_tz(tz_name: str):
    zone = tz.gettz(tz_name)
    if zone is None:
        raise ValueError(f"Invalid timezone: {tz_name}")
    return zone


def load_schedule(csv_path: str = SCHEDULE_CSV) -> List[Tuple[int, str]]:
    items: List[Tuple[int, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = int(row["index"])  # may raise if invalid
            hhmm = str(row["time"]).zfill(4)
            items.append((idx, hhmm))
    return items


def hhmm_to_today(hhmm: str, zone) -> datetime:
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
    """Get duration in seconds for the sound mapped to index (01..31)."""
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


def schedule_today(sched, items: List[Tuple[int, str]], zone, config: dict) -> int:
    now = datetime.now(tz=zone)
    count = 0
    for idx, hhmm in items:
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
    logging.info(f"Scheduled {count} jobs for today (remaining only)")
    return count


def schedule_test_mode(sched, config: dict, zone) -> None:
    base = datetime.now(tz=zone) + timedelta(seconds=2)
    for i in range(1, 32):
        run_at = base + timedelta(seconds=3 * (i - 1))
        sched.add_job(
            play_sound_for_index,
            trigger=DateTrigger(run_date=run_at),
            args=[i, config],
            id=f"test-bell-{i}",
            replace_existing=True,
        )
    logging.info("TEST MODE: 1..31 scheduled at 3s intervals")


def schedule_next_day_refresh(sched, config: dict, zone) -> None:
    hh, mm = map(int, str(config.get("refresh_time", "00:01")).split(":"))
    now = datetime.now(tz=zone)
    refresh = datetime(now.year, now.month, now.day, hh, mm, tzinfo=zone)
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

    if config.get("workdays_only", True) and not config.get("allow_weekend", False):
        if not is_workday(zone):
            logging.info("Weekend detected; skipping schedule (workdays_only=true)")
            return None

    if sched is None:
        sched = BackgroundScheduler(timezone=zone) if background else BlockingScheduler(timezone=zone)

    if bool(config.get("test_mode", False)):
        schedule_test_mode(sched, config, zone)
    else:
        items = load_schedule(SCHEDULE_CSV)
        schedule_today(sched, items, zone, config)
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
