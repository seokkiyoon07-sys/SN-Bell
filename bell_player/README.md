## Windows EXE 빌드 (PyInstaller)

사전 준비: 가상환경 활성화 후 의존성 설치

```powershell
cd C:\code\SN-Bell\bell_player
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
```

빌드 실행 (창 있는 GUI 모드, 아이콘 생략):

```powershell
pyinstaller --noconfirm --noconsole --name BellPlayer `
  --add-data "config.yaml;." `
  --add-data "schedule.csv;." `
  --add-data "sounds;.\sounds" `
  gui.py
```

생성 결과: `dist/BellPlayer/BellPlayer.exe`

배치 팁
- exe와 같은 폴더에 `config.yaml`, `schedule.csv`, `sounds/`가 함께 있으면 자동 인식합니다.
- 재생 기본값은 MCI(윈도우 내장)이며, ffplay(FFmpeg)는 선택적 보완 수단입니다.
- ffplay를 쓰려면 포터블 동봉 또는 PATH/`config.yaml`의 `ffplay_path` 지정이 필요합니다.

### FFmpeg 포터블 동봉(옵션, 설치 없이 실행)

1) FFmpeg 바이너리 준비
- https://www.gyan.dev/ffmpeg/builds/ 에서 Windows build 다운로드(Full 추천) → 압축 해제

2) 빌드된 앱 폴더에 동봉
```powershell
cd C:\code\SN-Bell\bell_player
PowerShell -ExecutionPolicy Bypass -File .\scripts\bundle_ffmpeg.ps1 -Source "C:\Path\To\ffmpeg\bin"
```
- 결과: `dist/BellPlayer/ffmpeg/bin/ffplay.exe` 생성
- 앱은 기본적으로 MCI를 사용하며, 동봉된 ffplay가 있을 경우 자동으로 보완 재생에 활용합니다.

3) 포터블 ZIP 만들기
```powershell
PowerShell -ExecutionPolicy Bypass -File .\scripts\make_portable_zip.ps1
```
- 결과: `dist/BellPlayer-portable.zip`
# Bell Player

간단한 시각 기반 벨(음원) 자동 재생기.

## 구조

```
bell_player/
  ├─ sounds/              # 음원 저장 (01.mp3 ~ 31.mp3)
  ├─ schedule.csv         # 시간표 (index,time(HHMM))
  ├─ config.yaml          # 설정 (볼륨/요일/로그 등)
  └─ app.py               # 실행 스크립트
```

## 설치

```bash
python -m venv venv
# Windows
venv\Scripts\activate && pip install -r requirements.txt
# macOS/Linux
source venv/bin/activate && pip install -r requirements.txt
```

- 기본적으로 MCI로 재생하며 MP3/WAV 대부분은 별도 설치 없이 동작합니다.
- ffplay(FFmpeg)를 사용하려면:
  - Windows: `choco install ffmpeg -y` 또는 ffmpeg.org에서 다운로드 후 PATH 등록
  - 또는 포터블 빌드를 앱 폴더에 동봉(`ffmpeg\\bin\\ffplay.exe`)

## 실행

```bash
python app.py
```

- `test_mode: true`이면 1~31을 3초 간격으로 빠르게 재생 스케줄링(검증용)
