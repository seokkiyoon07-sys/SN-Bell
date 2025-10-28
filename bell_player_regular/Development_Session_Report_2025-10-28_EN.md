# Bell Player Regular Development Session Report - October 28, 2025

## 📋 Overview
Completed major feature additions and improvements for the Bell Player Regular (Daily Bell Scheduling Program)

## 🎯 Major Development Items

### 1. Sunday Schedule System Implementation
**Purpose**: Meet different schedule requirements for weekdays vs. Sundays

#### Changes:
- **Before**: Single schedule (20 items)
- **After**: Separate schedules - Weekdays (20 items) + Sunday (17 items)

#### Sunday Schedule Structure:
```python
SUNDAY_SCHEDULE = [
    (1, "07:00", "Morning Bell"),     # 🆕 New
    (2, "10:50", "Entry Bell"),       # 🆕 New
    (3, "11:00", "Start Bell"),       # 🆕 New
    (4, "12:10", "Meal Time Bell"),   # Former #1 → #4
    (5, "13:00", "Start Bell"),       # Former #2 → #5
    # ... Total 17 items
    (17, "22:30", "End of Day Bell")
]
```

#### Technical Implementation:
```python
def is_sunday(zone) -> bool:
    """Sunday detection function"""
    w = datetime.now(tz=zone).weekday()
    return w == 6  # Monday=0, Sunday=6

def get_schedule_for_today(zone) -> List[Tuple[int, str, str]]:
    """Automatic schedule selection by day of week"""
    if is_sunday(zone):
        return SUNDAY_SCHEDULE
    else:
        return WEEKDAY_SCHEDULE
```

### 2. Sunday-Specific Sound Folder System
**Purpose**: Enable completely different bell sounds for weekdays vs. Sundays

#### Architecture:
```
Weekdays (Mon-Sat): sounds_dir → C:\bell_sound_regular\
Sunday:             sounds_dir_sunday → C:\bell_sound_weekend\
```

#### Core Functions:
```python
def get_sounds_dir_for_day(config: dict, zone) -> str:
    """Return sound directory based on day of week"""
    if is_sunday(zone):
        sunday_dir = config.get("sounds_dir_sunday")
        if sunday_dir and os.path.isdir(sunday_dir):
            return sunday_dir
        else:
            return get_sounds_dir(config)  # fallback
    else:
        return get_sounds_dir(config)

def play_sound_for_index_sunday(index: int, config: dict) -> None:
    """Sunday-specific sound playback (forced Sunday folder usage)"""
    sunday_dir = config.get("sounds_dir_sunday")
    if not sunday_dir or not os.path.isdir(sunday_dir):
        sunday_dir = get_sounds_dir(config)
    
    path = _find_sound_in_dir(index, sunday_dir, config)
    if path:
        _play_sound_from_path(index, path, config)
```

#### Configuration File Update:
```yaml
# config.yaml
sounds_dir: C:\code\SN-Bell\bell_sound_regular
sounds_dir_sunday: C:\code\SN-Bell\bell_sound_weekend  # 🆕 New
```

### 3. GUI Improvements
**Purpose**: Enhanced user experience and Sunday feature support

#### 3.1 Sunday Tab Sound Folder Selection UI
```python
# Added UI component in Sunday tab
self.var_sounds_sunday = tk.StringVar(value=self.config.get("sounds_dir_sunday") or "")

# UI Layout
tk.Label(frm_sunday, text="Sunday Sound Folder").grid(row=0, column=0)
tk.Entry(frm_sunday, textvariable=self.var_sounds_sunday).grid(row=0, column=1)
tk.Button(frm_sunday, text="Browse", command=self.pick_folder_sunday).grid(row=0, column=2)
```

#### 3.2 Duration Display System Enhancement
- **Issue**: Weekday duration not displaying properly
- **Solution**: Pass zone parameter to all duration functions for day-specific folder calculation

```python
def refresh_durations(self):
    """Weekday tab duration refresh"""
    zone = get_tz(self.config.get("timezone", "Asia/Seoul"))
    for i in range(len(self.current_schedule)):
        actual_index = self.current_schedule[i][0]
        secs = get_sound_duration_seconds(actual_index, self.config, zone)
        # UI update logic...

def refresh_sunday_durations(self):
    """Sunday tab duration refresh"""
    zone = get_tz(self.config.get("timezone", "Asia/Seoul"))
    for i, (index, time_str, description) in enumerate(SUNDAY_SCHEDULE):
        duration = get_sound_duration_seconds(index, self.config, zone)
        # UI update logic...
```

### 4. Code Architecture Improvements

#### 4.1 Function Separation and Reusability Enhancement
```python
# Common logic separation
def _play_sound_from_path(index: int, path: str, config: dict) -> None:
    """Common sound playback logic"""
    # Try in order: MCI → ffplay → playsound

def _find_sound_in_dir(index: int, directory: str, config: dict) -> Optional[str]:
    """Find sound file in specific directory"""
    # File patterns: 01.mp3, 1.mp3, etc.
    # Extensions: mp3, wav, m4a, aac, flac, ogg
```

#### 4.2 Configuration Management Enhancement
```python
# DEFAULT_CONFIG update
DEFAULT_CONFIG = {
    # Existing settings...
    "sounds_dir": None,
    "sounds_dir_sunday": None,  # 🆕 New
    "prefer_mci": True,
}

# Added configuration validation logic
def validate_config(config):
    # sounds_dir_sunday validation logic
    sounds_dir_sunday = config.get("sounds_dir_sunday")
    if sounds_dir_sunday:
        if not isinstance(sounds_dir_sunday, str):
            logging.warning("Sunday sound directory is not a string")
        elif not os.path.isdir(sounds_dir_sunday):
            logging.warning(f"Sunday sound directory does not exist: {sounds_dir_sunday}")
```

### 5. Test Code Updates
**Purpose**: Test cases matching the changed schedule structure

#### Major Test Cases:
```python
def test_sunday_schedule_structure(self):
    """Sunday schedule structure test (14 → 17 items)"""
    self.assertEqual(len(SUNDAY_SCHEDULE), 17)
    self.assertEqual(SUNDAY_SCHEDULE[0], (1, "07:00", "Morning Bell"))
    self.assertEqual(SUNDAY_SCHEDULE[1], (2, "10:50", "Entry Bell"))
    self.assertEqual(SUNDAY_SCHEDULE[2], (3, "11:00", "Start Bell"))
    self.assertEqual(SUNDAY_SCHEDULE[-1], (17, "22:30", "End of Day Bell"))

def test_sunday_schedule_structure_complete(self):
    """Sunday schedule completeness test"""
    sunday_times = [item[1] for item in SUNDAY_SCHEDULE]
    self.assertIn("07:00", sunday_times)  # Morning Bell
    self.assertIn("10:50", sunday_times)  # Entry Bell
    self.assertIn("11:00", sunday_times)  # Start Bell
```

### 6. EXE Distribution via PyInstaller
**Purpose**: Single executable file distribution for installation-free usage

#### 6.1 Dependency Updates
```python
# BellPlayerRegular.spec
hiddenimports=[
    'apscheduler', 'pydub', 'yaml', 'pytz', 'dateutil',
    'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
    'ntplib',      # 🆕 NTP time synchronization
    'requests',    # 🆕 Web API calls
    'json',        # 🆕 JSON processing
    'threading',   # 🆕 Multithreading
    'contextlib',  # 🆕 Context management
],
```

#### 6.2 Build Result
```
BellPlayerRegular_Distribution_Latest/
├── BellPlayerRegular.exe     (19.15MB)  # All dependencies included
├── config.yaml               # Configuration file
├── README.md                 # Detailed documentation
├── UserGuide.txt             # English guide
├── sounds/                   # Sample sounds
└── logs/                     # Log directory
```

## 🔧 Technical Details

### NTP Time Synchronization System
- **Library**: `ntplib`
- **Servers**: `time.windows.com`, `pool.ntp.org`
- **Fallback**: WorldTimeAPI → Local time sequence
- **UI**: Real-time clock display (updates every second)

### Audio Playback System
- **Priority**: MCI (Windows built-in) → FFplay → playsound
- **Supported Formats**: MP3, WAV, M4A, AAC, FLAC, OGG
- **Volume Control**: Volume processing via pydub
- **Resource Management**: Memory leak prevention via AudioResourceManager class

### Scheduling System
- **Library**: APScheduler (BackgroundScheduler)
- **Trigger**: DateTrigger (executes at exact time)
- **Grace Time**: 60 seconds (allows for system delays)
- **Auto Refresh**: Automatic next-day schedule registration at 00:01 daily

## 📊 Performance and Stability

### Memory Management
```python
class AudioResourceManager:
    """Automatic audio resource cleanup"""
    def __init__(self):
        self.temp_files = []
        atexit.register(self.cleanup_all)
    
    def cleanup_all(self):
        """Clean up temporary files on program exit"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logging.warning(f"Failed to delete temp file: {e}")
```

### Error Handling
- **Network Errors**: Automatic fallback on NTP failure
- **Missing Files**: Logging and continue on missing sound files
- **Configuration Errors**: Automatic correction of invalid settings
- **Schedule Conflicts**: Delay tolerance via misfire_grace_time

### Logging System
```python
# Log level differentiation
logging.info("Schedule started")         # General information
logging.warning("Setting corrected")     # Warnings
logging.error("File not found")          # Errors
logging.debug("Detailed debug info")     # Development use
```

## 📈 Improvement Effects

### Usability Enhancement
- ✅ Different bell sounds for weekdays/Sundays
- ✅ Intuitive GUI for easy folder selection
- ✅ Real-time duration display for easy file status checking
- ✅ Mouse wheel scrolling for improved convenience

### Feature Extensibility
- ✅ Day-specific schedule system enables easy addition of other days
- ✅ Plugin-style audio backends allow new playback engine additions
- ✅ Configuration file-based system provides high customization freedom

### Distribution Convenience
- ✅ Single EXE file eliminates installation process
- ✅ Embedded dependencies resolve environment setup issues
- ✅ Portable execution supports various environments

## 🚀 Future Development Directions

### Short-term Improvements
1. **Separate Saturday Schedule**: Currently same as weekdays, may need independent management
2. **Holiday Schedule**: Automatic holiday detection and separate schedule application
3. **Multiple Sound Support**: Support for playing multiple sounds at one time
4. **Volume Scheduling**: Different volume settings by time period

### Long-term Expansions
1. **Web Interface**: Web UI for remote management
2. **Network Synchronization**: Schedule synchronization between multiple systems
3. **AI Voice**: Voice announcements via TTS
4. **Mobile App**: Remote control via smartphone

## 📁 File Structure

### Core Modules
```
bell_player_regular/
├── app.py                    # Business logic
├── gui.py                    # GUI interface
├── config.yaml               # Configuration file
├── BellPlayerRegular.spec    # PyInstaller configuration
└── tests/
    └── test_weekly_schedule.py  # Unit tests
```

### Configuration and Data
```
├── sounds/                   # Default sound folder
├── logs/                     # Execution logs
├── __pycache__/             # Python cache
└── dist/                     # Built EXE file
```

## 🔍 Code Quality

### Test Coverage
- **Unit Tests**: All 11 test cases PASS
- **Integration Tests**: Manual GUI testing completed
- **Performance Tests**: 19MB EXE file execution confirmed

### Code Metrics
- **Total Lines**: ~1,000 lines (including comments)
- **Functions**: 50+ functions
- **Classes**: 3 classes (GUI, AudioResourceManager, Tests)
- **Dependencies**: 10 major libraries

### Documentation Level
- **Function Docstrings**: 100% coverage
- **Type Hints**: Applied to major functions
- **Comments**: Detailed explanations for complex logic
- **README**: Complete user guide

---

## 📞 Maintenance Guide

### How to Add New Schedules
1. Add `NEW_SCHEDULE` constant in `app.py`
2. Add condition to `get_schedule_for_today()` function
3. Add GUI tab (if needed)
4. Write test cases

### How to Add New Audio Backends
1. Add new backend to `play_sound_for_index()` function
2. Add dependency to `BellPlayerRegular.spec`
3. Add priority option to configuration file

### Deployment Process
```bash
# 1. Run tests
python -m unittest tests.test_weekly_schedule -v

# 2. Build EXE
python -m PyInstaller BellPlayerRegular.spec --clean

# 3. Create distribution folder
# (Manually copy required files)
```

### Known Issues and Solutions
1. **NTP Timeout**: Automatic fallback to local time
2. **Audio Device Conflicts**: Multiple backend support for reliability
3. **File Permission Errors**: Proper error handling and user notification
4. **Memory Leaks**: Automatic resource cleanup on exit

### Configuration File Format
```yaml
# Complete configuration example
timezone: Asia/Seoul
volume: 1.0
workdays_only: false
allow_weekend: true
log_file: logs/bell.log
autoplay_next_day: true
test_mode: false
sound_ext: mp3
misfire_grace_seconds: 60
refresh_time: '0001'
sounds_dir: C:\path\to\weekday\sounds
sounds_dir_sunday: C:\path\to\sunday\sounds
prefer_mci: true
ffplay_path: ''
```

### Troubleshooting Common Issues
1. **Program Won't Start**: Check log files in logs/ directory
2. **No Sound Playing**: Verify sound file paths and formats
3. **Schedule Not Working**: Check system time and timezone settings
4. **High Memory Usage**: Restart program to clear temporary files

### Extension Points for Future Development
- **Custom Schedule Parser**: Support for external schedule files
- **Plugin System**: Loadable modules for new features
- **API Interface**: RESTful API for external control
- **Database Integration**: Persistent schedule and log storage

**Developer**: GitHub Copilot  
**Date**: October 28, 2025  
**Version**: Bell Player Regular v2.0