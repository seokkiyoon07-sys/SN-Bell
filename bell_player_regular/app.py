from __future__ import annotations

import csv
import logging
import os
import sys
import shutil
import subprocess
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from typing import List, Tuple, Optional, Union
import atexit
import requests
import json
from contextlib import contextmanager
import threading
import time

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

# 요일별 스케줄 데이터
# 월~토요일 (평상시) 스케줄
WEEKDAY_SCHEDULE = [
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

# 일요일 스케줄
SUNDAY_SCHEDULE = [
    (1, "07:00", "기상종"),
    (2, "10:50", "입실종"),
    (3, "11:00", "시작종"),
    (4, "12:10", "식사시간종"),
    (5, "13:00", "시작종"),
    (6, "14:20", "쉬는시간종"),
    (7, "14:40", "시작종"),
    (8, "16:30", "쉬는시간종"),
    (9, "16:40", "시작종"),
    (10, "17:30", "식사시간종"),
    (11, "18:30", "시작종"),
    (12, "19:50", "쉬는시간종"),
    (13, "20:00", "시작종"),
    (14, "21:00", "간식시간종"),
    (15, "21:30", "시작종"),
    (16, "22:20", "학습종료종"),
    (17, "22:30", "하루일과 종료종"),
]

# 하위 호환성을 위한 기본 스케줄 (월~토요일과 동일)
REGULAR_SCHEDULE = WEEKDAY_SCHEDULE

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
    "sounds_dir_sunday": None,
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


class AudioResourceManager:
    """오디오 재생 리소스를 안전하게 관리하는 클래스"""
    
    def __init__(self):
        self._procs: List[subprocess.Popen] = []
        self._mci_aliases: List[str] = []
        self._lock = threading.RLock()
    
    def add_process(self, proc: subprocess.Popen) -> None:
        """프로세스를 관리 목록에 추가"""
        with self._lock:
            self._procs.append(proc)
    
    def remove_process(self, proc: subprocess.Popen) -> None:
        """프로세스를 관리 목록에서 제거"""
        with self._lock:
            try:
                self._procs.remove(proc)
            except ValueError:
                pass
    
    def add_mci_alias(self, alias: str) -> None:
        """MCI 별칭을 관리 목록에 추가"""
        with self._lock:
            self._mci_aliases.append(alias)
    
    def remove_mci_alias(self, alias: str) -> None:
        """MCI 별칭을 관리 목록에서 제거"""
        with self._lock:
            try:
                self._mci_aliases.remove(alias)
            except ValueError:
                pass
    
    def cleanup_all(self) -> None:
        """모든 활성 리소스를 정리"""
        with self._lock:
            # 프로세스 정리
            procs = list(self._procs)
            for proc in procs:
                try:
                    if proc and proc.poll() is None:
                        proc.terminate()
                        # 2초 대기 후 강제 종료
                        try:
                            proc.wait(timeout=2.0)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            logging.warning("프로세스를 강제 종료했습니다")
                except Exception as e:
                    logging.debug(f"프로세스 정리 중 오류: {e}")
                finally:
                    self.remove_process(proc)
            
            # MCI 세션 정리
            aliases = list(self._mci_aliases)
            for alias in aliases:
                try:
                    self._cleanup_mci_alias(alias)
                except Exception as e:
                    logging.debug(f"MCI 정리 중 오류: {e}")
                finally:
                    self.remove_mci_alias(alias)
    
    def _cleanup_mci_alias(self, alias: str) -> None:
        """MCI 별칭을 정리"""
        try:
            _mci_send(f"stop {alias}")
            _mci_send(f"close {alias}")
        except Exception:
            pass

    @contextmanager
    def managed_process(self, *args, **kwargs):
        """프로세스를 안전하게 관리하는 컨텍스트 매니저"""
        proc = None
        try:
            proc = subprocess.Popen(*args, **kwargs)
            self.add_process(proc)
            yield proc
        finally:
            if proc:
                self.remove_process(proc)
                try:
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                except Exception:
                    pass

    @contextmanager 
    def managed_mci_alias(self, alias: str):
        """MCI 별칭을 안전하게 관리하는 컨텍스트 매니저"""
        try:
            self.add_mci_alias(alias)
            yield alias
        finally:
            self._cleanup_mci_alias(alias)
            self.remove_mci_alias(alias)

# 전역 리소스 매니저 인스턴스
resource_manager = AudioResourceManager()

# 하위 호환성을 위한 전역 리스트들 (deprecated)
CURRENT_PROCS: List[subprocess.Popen] = []
CURRENT_MCI_ALIASES: List[str] = []


def stop_all_playback() -> None:
    """모든 활성 재생을 중단합니다: 외부 프로세스(ffplay)와 MCI 세션."""
    global resource_manager
    try:
        resource_manager.cleanup_all()
        logging.info("모든 오디오 리소스가 정리되었습니다")
    except Exception as e:
        logging.error(f"리소스 정리 중 오류 발생: {e}")
    
    # 하위 호환성을 위한 기존 방식도 유지
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

    try:
        _mci_stop_all()
    except Exception:
        pass


atexit.register(stop_all_playback)

def load_config(path: str = CONFIG_YAML) -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if not os.path.exists(path):
        logging.info(f"설정 파일이 없어 기본값을 사용합니다: {path}")
        return cfg
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
            if not isinstance(loaded, dict):
                logging.warning("설정 파일 형식이 잘못되어 기본값을 사용합니다")
                return cfg
            cfg.update(loaded)
            logging.info(f"설정 파일을 성공적으로 로드했습니다: {path}")
    except FileNotFoundError:
        logging.warning(f"설정 파일을 찾을 수 없어 기본값을 사용합니다: {path}")
    except PermissionError:
        logging.error(f"설정 파일에 접근할 수 없어 기본값을 사용합니다: {path}")
    except yaml.YAMLError as e:
        logging.error(f"YAML 파싱 오류로 기본값을 사용합니다: {e}")
    except UnicodeDecodeError as e:
        logging.error(f"파일 인코딩 오류로 기본값을 사용합니다: {e}")
    except Exception as e:
        logging.error(f"설정 파일 로드 중 오류가 발생해 기본값을 사용합니다: {e}")
    
    # 설정 값 검증
    validated_cfg = validate_config(cfg)
    return validated_cfg


def validate_config(config: dict) -> dict:
    """설정 값들을 검증하고 필요시 기본값으로 수정합니다."""
    validated = config.copy()
    
    # 볼륨 검증 (0.0 ~ 1.0)
    volume = config.get("volume", 1.0)
    try:
        volume = float(volume)
        if not 0.0 <= volume <= 1.0:
            logging.warning(f"볼륨 값이 범위를 벗어남 ({volume}), 기본값 사용")
            validated["volume"] = 1.0
        else:
            validated["volume"] = volume
    except (TypeError, ValueError):
        logging.warning(f"잘못된 볼륨 형식 ({volume}), 기본값 사용")
        validated["volume"] = 1.0
    
    # 사운드 디렉토리 검증
    sounds_dir = config.get("sounds_dir")
    if sounds_dir:
        if not isinstance(sounds_dir, str):
            logging.warning("사운드 디렉토리가 문자열이 아님, 기본값 사용")
            validated["sounds_dir"] = None
        elif not os.path.isdir(sounds_dir):
            logging.warning(f"사운드 디렉토리가 존재하지 않음: {sounds_dir}")
            # 존재하지 않아도 설정은 유지 (나중에 생성될 수 있음)
        else:
            # 디렉토리가 읽기 가능한지 확인
            try:
                os.listdir(sounds_dir)
            except PermissionError:
                logging.warning(f"사운드 디렉토리에 접근할 수 없음: {sounds_dir}")
    
    # 일요일 사운드 디렉토리 검증
    sounds_dir_sunday = config.get("sounds_dir_sunday")
    if sounds_dir_sunday:
        if not isinstance(sounds_dir_sunday, str):
            logging.warning("일요일 사운드 디렉토리가 문자열이 아님, 기본값 사용")
            validated["sounds_dir_sunday"] = None
        elif not os.path.isdir(sounds_dir_sunday):
            logging.warning(f"일요일 사운드 디렉토리가 존재하지 않음: {sounds_dir_sunday}")
            # 존재하지 않아도 설정은 유지 (나중에 생성될 수 있음)
        else:
            # 디렉토리가 읽기 가능한지 확인
            try:
                os.listdir(sounds_dir_sunday)
            except PermissionError:
                logging.warning(f"일요일 사운드 디렉토리에 접근할 수 없음: {sounds_dir_sunday}")
    
    # 타임존 검증
    timezone = config.get("timezone", "Asia/Seoul")
    try:
        get_tz(timezone)
        validated["timezone"] = timezone
    except ValueError:
        logging.warning(f"잘못된 타임존 ({timezone}), 기본값 사용")
        validated["timezone"] = "Asia/Seoul"
    
    # 리프레시 시간 형식 검증
    refresh_time = config.get("refresh_time", "0001")
    try:
        if isinstance(refresh_time, str) and len(refresh_time) == 4 and refresh_time.isdigit():
            hour = int(refresh_time[:2])
            minute = int(refresh_time[2:])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                validated["refresh_time"] = refresh_time
            else:
                raise ValueError("시간 범위 초과")
        else:
            raise ValueError("형식 오류")
    except ValueError:
        logging.warning(f"잘못된 리프레시 시간 형식 ({refresh_time}), 기본값 사용")
        validated["refresh_time"] = "0001"
    
    # 미스파이어 유예 시간 검증
    misfire_grace = config.get("misfire_grace_seconds", 60)
    try:
        misfire_grace = int(misfire_grace)
        if misfire_grace < 0:
            raise ValueError("음수 값")
        validated["misfire_grace_seconds"] = misfire_grace
    except (TypeError, ValueError):
        logging.warning(f"잘못된 미스파이어 유예 시간 ({misfire_grace}), 기본값 사용")
        validated["misfire_grace_seconds"] = 60
    
    # FFplay 경로 검증
    ffplay_path = config.get("ffplay_path", "")
    if ffplay_path and isinstance(ffplay_path, str):
        ffplay_path = ffplay_path.strip().strip('"')
        if ffplay_path and not os.path.isfile(ffplay_path):
            logging.warning(f"FFplay 파일이 존재하지 않음: {ffplay_path}")
        validated["ffplay_path"] = ffplay_path
    
    # 부울 값들 검증
    bool_keys = ["test_mode", "workdays_only", "allow_weekend", "autoplay_next_day", "prefer_mci"]
    for key in bool_keys:
        value = config.get(key, DEFAULT_CONFIG.get(key, False))
        if not isinstance(value, bool):
            try:
                # 문자열로 된 부울 값 처리
                if isinstance(value, str):
                    validated[key] = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    validated[key] = bool(value)
            except Exception:
                logging.warning(f"잘못된 부울 값 ({key}: {value}), 기본값 사용")
                validated[key] = DEFAULT_CONFIG.get(key, False)
    
    # 사운드 확장자 검증
    sound_ext = config.get("sound_ext", "mp3")
    if isinstance(sound_ext, str):
        sound_ext = sound_ext.lower().lstrip(".")
        if sound_ext in ["mp3", "wav", "m4a", "aac", "flac", "ogg"]:
            validated["sound_ext"] = sound_ext
        else:
            logging.warning(f"지원하지 않는 사운드 확장자 ({sound_ext}), 기본값 사용")
            validated["sound_ext"] = "mp3"
    else:
        validated["sound_ext"] = "mp3"
    
    return validated


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


def get_ntp_time():
    """NTP 서버에서 정확한 시간을 가져옵니다."""
    try:
        import ntplib
        import socket
        
        # 여러 NTP 서버 시도
        ntp_servers = [
            'time.windows.com',
            'pool.ntp.org',
            'time.google.com',
            'time.cloudflare.com'
        ]
        
        for server in ntp_servers:
            try:
                client = ntplib.NTPClient()
                response = client.request(server, version=3, timeout=3)
                ntp_time = datetime.fromtimestamp(response.tx_time)
                logging.info(f"NTP 시간 동기화 성공: {server}")
                return ntp_time
            except (socket.timeout, socket.gaierror, ntplib.NTPException) as e:
                logging.debug(f"NTP 서버 {server} 연결 실패: {e}")
                continue
                
    except ImportError:
        logging.warning("ntplib 모듈을 찾을 수 없습니다. pip install ntplib로 설치하세요.")
    except Exception as e:
        logging.warning(f"NTP 시간 동기화 실패: {e}")
    
    return None

def get_worldtime_api():
    """WorldTimeAPI를 사용해 정확한 시간을 가져옵니다."""
    try:
        # 한국 시간대로 API 요청
        response = requests.get("http://worldtimeapi.org/api/timezone/Asia/Seoul", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # ISO 8601 형식의 시간 파싱
            time_str = data.get('datetime', '')
            if time_str:
                # 2025-10-28T15:30:45.123456+09:00 형식
                import re
                # 마이크로초 제거 (파싱 호환성을 위해)
                time_str = re.sub(r'\.\d+', '', time_str)
                parsed_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                logging.info("WorldTimeAPI 시간 동기화 성공")
                return parsed_time.replace(tzinfo=None)  # naive datetime으로 변환
    except (requests.RequestException, ValueError, KeyError) as e:
        logging.debug(f"WorldTimeAPI 연결 실패: {e}")
    except Exception as e:
        logging.warning(f"WorldTimeAPI 시간 동기화 실패: {e}")
    
    return None

def get_current_time():
    """현재 시간을 가져옵니다 (외부 시간 동기화 우선, 실패 시 로컬 시간)."""
    # 1. NTP 서버 시도
    ntp_time = get_ntp_time()
    if ntp_time:
        return ntp_time
    
    # 2. WorldTimeAPI 시도  
    api_time = get_worldtime_api()
    if api_time:
        return api_time
    
    # 3. 로컬 시간 사용
    logging.info("외부 시간 동기화 실패, 로컬 시간 사용")
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


def is_sunday(zone) -> bool:
    """일요일인지 확인합니다."""
    w = datetime.now(tz=zone).weekday()
    return w == 6  # 월요일=0, 일요일=6


def get_schedule_for_today(zone) -> List[Tuple[int, str, str]]:
    """오늘 날짜에 맞는 스케줄을 반환합니다."""
    if is_sunday(zone):
        logging.info("일요일 스케줄을 사용합니다")
        return SUNDAY_SCHEDULE
    else:
        logging.info("평일 스케줄을 사용합니다 (월~토)")
        return WEEKDAY_SCHEDULE


def get_sounds_dir(config: dict) -> str:
    """기본 사운드 디렉토리를 반환합니다 (평일용)."""
    custom = config.get("sounds_dir")
    if custom and isinstance(custom, str) and os.path.isdir(custom):
        return custom
    return SOUNDS_DIR_DEFAULT


def get_sounds_dir_for_day(config: dict, zone) -> str:
    """요일에 따른 사운드 디렉토리를 반환합니다."""
    if is_sunday(zone):
        # 일요일 전용 디렉토리가 설정되어 있으면 사용
        custom_sunday = config.get("sounds_dir_sunday")
        if custom_sunday and isinstance(custom_sunday, str) and os.path.isdir(custom_sunday):
            logging.info(f"일요일 전용 사운드 디렉토리 사용: {custom_sunday}")
            return custom_sunday
        else:
            logging.info("일요일 전용 사운드 디렉토리가 없어서 평일 디렉토리 사용")
            return get_sounds_dir(config)
    else:
        # 평일은 기본 디렉토리 사용
        return get_sounds_dir(config)


def find_existing_sound(index: int, config: dict, zone=None) -> Optional[str]:
    # zone이 없으면 기본 타임존 사용
    if zone is None:
        zone = get_tz(config.get("timezone", "Asia/Seoul"))
    
    base = get_sounds_dir_for_day(config, zone)
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
        logging.debug("PyDub를 사용할 수 없어 원본 파일을 사용합니다")
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
        logging.debug(f"볼륨 조절된 파일 생성: {tmp_out}")
        return tmp_out
    except FileNotFoundError:
        logging.error(f"오디오 파일을 찾을 수 없어 원본을 사용합니다: {path}")
        return path
    except PermissionError:
        logging.error(f"임시 파일 생성 권한이 없어 원본을 사용합니다: {path}")
        return path
    except Exception as e:
        logging.warning(f"볼륨 조절 실패로 원본을 사용합니다: {e}")
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
        # 새로운 리소스 매니저를 사용한 안전한 MCI 관리
        with resource_manager.managed_mci_alias(alias):
            # Open
            if path.lower().endswith((".mp3", ".m4a", ".aac")):
                rc = _mci_send(f"open \"{path}\" type mpegvideo alias {alias}")
            else:
                rc = _mci_send(f"open \"{path}\" alias {alias}")
            if rc != 0:
                return False

            # Play (wait blocks until completion)
            rc = _mci_send(f"play {alias} wait")
            return rc == 0
    except ImportError as e:
        logging.error(f"MCI 모듈을 불러올 수 없습니다: {e}")
        return False
    except FileNotFoundError:
        logging.error(f"오디오 파일을 찾을 수 없습니다: {path}")
        return False
    except PermissionError:
        logging.error(f"오디오 파일에 접근할 수 없습니다: {path}")
        return False
    except Exception as e:
        logging.error(f"MCI 재생 중 오류 발생: {e}")
        # 리소스 매니저가 자동으로 정리하므로 추가 정리 불필요
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



def get_sound_duration_seconds(index: int, config: dict, zone=None) -> Optional[float]:
    """Get duration in seconds for the sound mapped to index (01..20)."""
    path = find_existing_sound(index, config, zone)
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
            # 새로운 리소스 매니저를 사용한 안전한 프로세스 관리
            with resource_manager.managed_process([ff, "-nodisp", "-autoexit", "-loglevel", "error", path]) as proc:
                proc.wait()
            return True
        except FileNotFoundError:
            logging.debug(f"FFplay 실행 파일을 찾을 수 없습니다: {ff}")
            continue
        except PermissionError:
            logging.debug(f"FFplay 실행 권한이 없습니다: {ff}")
            continue
        except subprocess.TimeoutExpired:
            logging.warning(f"FFplay 실행 시간 초과: {ff}")
            continue
        except subprocess.CalledProcessError as e:
            logging.debug(f"FFplay 프로세스 오류 (exit code {e.returncode}): {ff}")
            continue
        except OSError as e:
            logging.debug(f"FFplay 시스템 오류: {e}")
            continue
        except Exception as e:
            logging.warning(f"FFplay 실행 중 예상치 못한 오류: {e}")
            continue
    return False


def play_sound_for_index(index: int, config: dict, zone=None) -> None:
    if zone is None:
        zone = get_tz(config.get("timezone", "Asia/Seoul"))
        
    logging.info(f"Play start: index={index}")
    path = find_existing_sound(index, config, zone)
    if not path:
        base = get_sounds_dir_for_day(config, zone)
        logging.error(f"Sound file not found for index {index} in {base}")
        return

    _play_sound_from_path(index, path, config)


def play_sound_for_index_sunday(index: int, config: dict) -> None:
    """일요일 전용 사운드 재생 (항상 일요일 폴더 사용)"""
    logging.info(f"Play start (Sunday mode): index={index}")
    
    # 일요일 폴더에서 직접 찾기
    sunday_dir = config.get("sounds_dir_sunday")
    if not sunday_dir or not os.path.isdir(sunday_dir):
        # 일요일 폴더가 없으면 평일 폴더 사용
        sunday_dir = get_sounds_dir(config)
    
    path = _find_sound_in_dir(index, sunday_dir, config)
    if not path:
        logging.error(f"Sunday sound file not found for index {index} in {sunday_dir}")
        return

    _play_sound_from_path(index, path, config)


def _find_sound_in_dir(index: int, directory: str, config: dict) -> Optional[str]:
    """특정 디렉토리에서 사운드 파일 찾기"""
    pref_ext = str(config.get("sound_ext", "mp3")).lower().lstrip(".")
    ext_candidates = [pref_ext, "mp3", "wav", "m4a", "aac", "flac", "ogg"]
    seen = set()
    ordered_exts = [e for e in ext_candidates if not (e in seen or seen.add(e))]
    name_candidates = [f"{index:02d}", str(index)]
    
    for name in name_candidates:
        for ext in ordered_exts:
            path = os.path.join(directory, f"{name}.{ext}")
            if os.path.exists(path):
                return path
    return None


def _play_sound_from_path(index: int, path: str, config: dict) -> None:
    """공통 사운드 재생 로직"""

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
    # 외부 시간 동기화 우선 사용
    now = get_current_time()
    if now.tzinfo is None:
        now = now.replace(tzinfo=zone)
    count = 0
    
    # 오늘 날짜에 맞는 스케줄 선택
    today_schedule = get_schedule_for_today(zone)
    schedule_name = "일요일" if is_sunday(zone) else "평일(월~토)"
    
    for idx, hhmm, description in today_schedule:
        run_at = hhmm_to_today(hhmm, zone)
        if run_at > now:
            sched.add_job(
                play_sound_for_index,
                trigger=DateTrigger(run_date=run_at),
                args=[idx, config, zone],
                id=f"bell-{idx}",
                misfire_grace_time=int(config.get("misfire_grace_seconds", 60)),
                replace_existing=True,
            )
            count += 1
            logging.info(f"Scheduled [{schedule_name}]: {hhmm} - {description} (index: {idx})")
    
    logging.info(f"Scheduled {count} jobs for today ({schedule_name}, remaining only)")
    return count


def schedule_test_mode(sched, config: dict, zone) -> None:
    base = datetime.now(tz=zone) + timedelta(seconds=2)
    
    # 오늘 날짜에 맞는 스케줄 선택
    today_schedule = get_schedule_for_today(zone)
    schedule_name = "일요일" if is_sunday(zone) else "평일(월~토)"
    
    for i, (idx, hhmm, description) in enumerate(today_schedule):
        run_at = base + timedelta(seconds=3 * i)
        sched.add_job(
            play_sound_for_index,
            trigger=DateTrigger(run_date=run_at),
            args=[idx, config, zone],
            id=f"test-bell-{idx}",
            replace_existing=True,
        )
    logging.info(f"TEST MODE: {schedule_name} 스케줄을 3초 간격으로 테스트 중")


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
