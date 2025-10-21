## SN-Bell Bell Player 프로젝트 가이드 (KO)

### 개요
이 프로젝트는 수능/일반 학교 종 운영을 위한 Windows용 Python GUI 애플리케이션입니다. `tkinter` GUI, `APScheduler` 스케줄링, 윈도우 내장 MCI(기본) + ffplay(옵션) 기반 오디오 재생, `PyInstaller`로 배포를 지원합니다.

### 주요 기능
- **스케줄러 재생**: CSV 시간표에 따라 자동 재생 (스케줄러 시작/정지)
- **수동 재생**: 1~31 체크박스 선택 후 수동 시작/정지, 스크롤 지원
- **체크박스 라벨**: 한국어 라벨 + 각 음원 길이(mm:ss) 자동 표시
- **디폴트 선택**: [5,7,11,13,16,18,22,24,27,29,31]
- **(개발자전용 새로고침)**: 설정/길이 재스캔
- **시계 창**: 항상 위 작은 시계(0.5초 업데이트)
- **설명서 탭**: 사용법/설치/종료 안내, 폰트 ‘맑은 고딕’ 적용
- **안전 종료**: 앱 종료 시 재생 리소스 정리(MCI 세션, `ffplay` 프로세스)
- **브랜딩/타이틀**: 메인 문구 및 "수능_ bell_player_ver.1 by SN독학기숙학원"

### 폴더 구조
```
SN-Bell/
  bell_player/
    app.py           # 재생 로직, FFmpeg/경로 처리, 프로세스 관리
    gui.py           # tkinter GUI, 수동 재생, 시계, 설명서 탭 등
    config.yaml      # 설정(폴더 경로, 테스트 모드, 볼륨, 디폴트 인덱스)
    schedule.csv     # 스케줄(예: 0805,1) 형식
    sounds/          # 음원 폴더(01.mp3 ~ 31.mp3)
    scripts/         # 배포 보조 스크립트(ps1)
    dist/            # PyInstaller 산출물
    build/           # PyInstaller 중간 산출물
    README.md        # 빌드 개요 및 사용법
    PROJECT_GUIDE_KO.md  # 본 문서
```

### 요구 사항
- OS: Windows 10+
- Python: 3.13 (venv 권장)
- 필수 패키지: `requirements.txt` 참고
- 오디오 재생: MCI(기본, 별도 설치 불필요). ffplay(FFmpeg)는 옵션(동봉/자동감지 지원)

### 개발 환경 설정
```powershell
cd C:\code\SN-Bell\bell_player
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 실행 (개발)
```powershell
cd C:\code\SN-Bell\bell_player
venv\Scripts\python.exe gui.py
```
- 소리 미출력 시 `config.yaml`의 `ffplay_path` 지정 또는 FFmpeg PATH 추가
 - 기본은 MCI 재생입니다. 특정 코덱 문제 시 ffplay(FFmpeg) 보완을 사용할 수 있습니다.
 - 소리 미출력 시: 파일 형식 확인 → (옵션) ffplay 준비 → `ffplay_path` 지정 또는 PATH 등록

### 설정 파일 (`config.yaml`)
- `sounds_dir`: 음원 폴더 경로 (예: `C:\code\SN-Bell\bell_sound`)
- `test_mode`: true/false (테스트 시간표 사용)
- `volume`: 0.0~1.0 (pydub로 증감)
- `default_manual_indices`: 디폴트 수동 재생 인덱스 배열
- (선택) `ffplay_path`: `ffplay.exe` 절대경로
 - `prefer_mci`: true/false (MCI 우선 사용. 기본 true)

### 시간표 (`schedule.csv`)
- 형식: `index,time` (time은 HHMM, 예: `0805`)
- 예시:
```
1,0805
5,0840
11,1030
```

### GUI 사용법 요약
- 메인 탭
  - 사운드 폴더 선택, 볼륨 조절, 테스트 모드 토글
  - 스케줄러 시작/정지 버튼으로 자동 재생 제어
  - 수동 재생 영역: 1~31 체크박스, 선택 재생/수동 정지/모두 선택/선택 해제/디폴트 선택
  - (개발자전용 새로고침)으로 설정과 길이(mm:ss) 갱신
  - 시계 버튼: 항상 위 작은 시계 창 열기
- 설명서 탭
  - 설치/사용/종료/문제 해결 가이드, FFmpeg 다운로드 안내

### FFmpeg 사용/동봉(옵션)
- 기본 재생은 MCI입니다. ffplay는 보완용으로 자동 감지됩니다.
- 자동 감지 우선순위: `config.yaml.ffplay_path` > 시스템 PATH > `exe 옆 ffmpeg\bin\ffplay.exe`
- 포터블 동봉(선택):
  1) FFmpeg 포터블을 준비하여 `dist\BellPlayer\ffmpeg\bin\ffplay.exe` 위치에 복사
  2) 아래 스크립트 사용 가능
```powershell
# FFmpeg bin 복사
PowerShell -ExecutionPolicy Bypass -File .\scripts\bundle_ffmpeg.ps1 -Source "C:\Path\To\ffmpeg\bin"
# 포터블 ZIP 생성
PowerShell -ExecutionPolicy Bypass -File .\scripts\make_portable_zip.ps1
```
  - FFmpeg 공식/빌드 페이지: [`https://ffmpeg.org/download.html`](https://ffmpeg.org/download.html), [`https://www.gyan.dev/ffmpeg/builds/`](https://www.gyan.dev/ffmpeg/builds/)

### 빌드/배포 (PyInstaller)
1) 의존성 설치 후 실행
```powershell
cd C:\code\SN-Bell\bell_player
pyinstaller --noconfirm --noconsole --name BellPlayer `
  --add-data "config.yaml;." `
  --add-data "schedule.csv;." `
  --add-data "sounds;.\sounds" `
  gui.py
```
2) 산출물 위치
- 폴더형: `dist\BellPlayer\BellPlayer.exe`
- 폴더형 ZIP(예시): `dist\BellPlayer-folder.zip`
- 단일 파일(옵션): `--onefile` 사용 시 `dist\BellPlayer.exe`

### 종료/프로세스 정리
- GUI 종료 시 재생 리소스 정리: 열린 MCI 세션 종료, `ffplay` 프로세스 자동 종료
- 문제 시 수동 종료(관리자 불필요):
```powershell
Get-Process python,pythonw,ffplay -ErrorAction SilentlyContinue | Stop-Process -Force
```

### 문제 해결(Troubleshooting)
- 소리가 나지 않음
  - 기본 MCI에서 재생 불가한 특수 포맷인지 확인(MP3/WAV는 일반적으로 OK)
  - (옵션) ffplay 준비 후 PATH 또는 `ffplay_path` 설정
  - 음원 경로/파일 존재 여부 확인
  - 볼륨 0 아님 확인, 테스트 모드/스케줄 시간 확인
- PyInstaller 빌드 실패
  - 가상환경 재구축, `pip install -r requirements.txt` 재시도
  - `playsound`는 선택적이며, 기본은 MCI → ffplay 순입니다.
- dist가 비어 보임
  - 폴더형인 경우 `dist\BellPlayer\` 내부 확인

### 개발 규칙(간단)
- 코드 스타일: 가독성 우선, 명확한 변수명/함수명 사용, 불필요한 중첩 회피
- 예외 처리: 실제로 발생 가능 시에만 `try/except`, 의미 있는 처리 필수
- 주석: 비자명한 의도/제약/성능 고려점만 간결히
- 타입: 공개 API/함수 시그니처에 명시(가능한 경우)

### 버전/릴리스 제안
- 태깅: `vMajor.Minor.Patch`
- 변경 기록: 주요 UI/기능/배포 스크립트 변경은 `README.md` 또는 릴리스 노트에 기록

### 라이선스/크레딧
- 메인 화면: "bell-player developed by SN독학기숙학원"
- 사용 라이브러리: APScheduler, PyInstaller, PyYAML, pydub, tkinter(표준), FFmpeg(별도)

### 사용자 안내(간단)
1) 폴더형 배포 ZIP 압축 해제
2) `BellPlayer\BellPlayer.exe` 실행
3) 필요 시 `설명서` 탭 참고

### 문의/지원
- 버그/요청 사항: 내부 담당자 또는 저장소 이슈 트래커 활용(내부 정책에 따름)


