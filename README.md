# SN-Bell Bell Player Project

## 🎵 프로젝트 개요

SN-Bell은 교육기관을 위한 자동 종소리 시스템입니다. 두 가지 버전으로 구성되어 있습니다:

- **bell_player**: 사용자 정의 스케줄을 지원하는 유연한 종소리 시스템
- **bell_player_regular**: 고정된 20개 시간표를 사용하는 정규 종소리 시스템

## 🏗️ 프로젝트 구조

```
SN-Bell/
├── bell_player/                 # 사용자 정의 스케줄 버전
│   ├── app.py                   # 핵심 로직
│   ├── gui.py                   # GUI 인터페이스
│   ├── config.yaml             # 설정 파일
│   ├── requirements.txt         # Python 의존성
│   ├── README.md               # 사용자 가이드
│   └── PROJECT_GUIDE_KO_251020ver.1.md  # 개발자 가이드
├── bell_player_regular/         # 고정 스케줄 버전
│   ├── app.py                   # 핵심 로직
│   ├── gui.py                   # GUI 인터페이스
│   ├── config.yaml             # 설정 파일
│   ├── requirements.txt         # Python 의존성
│   ├── README.md               # 사용자 가이드
│   ├── PROJECT_GUIDE_KO.md     # 개발자 가이드
│   └── ERROR_SOLUTIONS.md      # 오류 해결 가이드
├── bell_sound/                 # bell_player용 사운드 파일
├── bell_sound_regular/         # bell_player_regular용 사운드 파일
└── README.md                   # 이 파일
```

## 🚀 주요 기능

### bell_player (사용자 정의 버전)
- ✅ **유연한 스케줄링**: 사용자가 시간과 설명을 직접 설정
- ✅ **CSV 파일 지원**: 스케줄을 CSV 파일로 관리
- ✅ **테스트 모드**: 빠른 테스트를 위한 간격 조정
- ✅ **다중 오디오 백엔드**: MCI, FFplay, playsound 지원

### bell_player_regular (고정 스케줄 버전)
- ✅ **고정 20개 스케줄**: 미리 정의된 시간표 사용
- ✅ **네이버 시간 동기화**: 더 정확한 시간 기준
- ✅ **자동 전환**: 네트워크 실패 시 로컬 시간 사용
- ✅ **테스트 모드**: 3초 간격으로 빠른 테스트

## 🎯 공통 기능

### 오디오 시스템
- **MCI (Windows Media Control Interface)**: Windows 기본 오디오 시스템
- **FFplay (FFmpeg)**: 고품질 오디오 재생
- **playsound**: Python 라이브러리 기반 재생
- **자동 감지**: 사용 가능한 시스템 자동 선택

### 스케줄링 시스템
- **APScheduler**: 고성능 Python 스케줄러
- **자동 갱신**: 매일 자동으로 다음날 스케줄 설정
- **오류 처리**: 스케줄 실패 시 자동 재시도

### GUI 시스템
- **Tkinter**: 크로스 플랫폼 GUI 프레임워크
- **실시간 시계**: 네이버 시간/로컬 시간 선택 가능
- **상태 모니터링**: 스케줄러 상태 실시간 확인

## 📋 시스템 요구사항

### 필수 요구사항
- **운영체제**: Windows 10/11
- **Python**: 3.13+ (개발용)
- **메모리**: 최소 4GB RAM
- **저장공간**: 100MB 이상

### 선택 요구사항
- **인터넷 연결**: 네이버 시간 동기화용 (bell_player_regular)
- **FFmpeg**: 고품질 오디오 재생용
- **사운드 카드**: 오디오 출력용

## 🛠️ 설치 및 실행

### 개발 환경 설정
```bash
# 저장소 클론
git clone https://github.com/your-username/SN-Bell.git
cd SN-Bell

# bell_player 설정
cd bell_player
pip install -r requirements.txt
python gui.py

# bell_player_regular 설정
cd ../bell_player_regular
pip install -r requirements.txt
python gui.py
```

### 배포용 실행 파일
```bash
# PyInstaller로 빌드
python -m PyInstaller BellPlayer.spec --clean
python -m PyInstaller BellPlayerRegular.spec --clean

# 배포용 폴더에서 실행
./BellPlayer_Distribution/BellPlayer.exe
./BellPlayerRegular_Distribution/BellPlayerRegular_v2.exe
```

## 📁 사운드 파일 준비

### bell_player용
- **위치**: `bell_sound/` 폴더
- **형식**: MP3, WAV 지원
- **이름**: `01.mp3`, `02.mp3`, ... (순서대로)

### bell_player_regular용
- **위치**: `bell_sound_regular/` 폴더
- **형식**: MP3, WAV 지원
- **이름**: `1.mp3`, `2.mp3`, ... `20.mp3` (1-20번)

## 🔧 설정 파일

### config.yaml 주요 설정
```yaml
timezone: Asia/Seoul          # 시간대
test_mode: false              # 테스트 모드
autoplay_next_day: true       # 다음날 자동 스케줄링
refresh_time: "0001"          # 새벽 1시에 스케줄 갱신
sounds_dir: C:\path\to\sounds # 사운드 파일 경로
prefer_mci: true             # MCI 우선 사용
```

## 🐛 문제 해결

### 일반적인 문제들
1. **오디오 재생 실패**: MCI, FFplay, playsound 순서로 시도
2. **스케줄 오류**: `refresh_time` 형식 확인
3. **네트워크 연결 실패**: 자동으로 로컬 시간 사용
4. **파일 경로 오류**: 절대 경로 사용 권장

### 로그 확인
- **로그 파일**: `logs/bell.log`
- **실시간 로그**: 콘솔 출력
- **로그 레벨**: INFO, WARNING, ERROR

## 📊 성능 정보

### 메모리 사용량
- **기본**: ~50MB
- **오디오 로딩**: +10MB per file
- **스케줄러**: +5MB

### CPU 사용량
- **대기 상태**: <1%
- **오디오 재생**: 5-10%
- **네이버 시간 동기화**: 일시적 10%

## 🤝 기여하기

### 개발 참여
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

### 코드 스타일
- **PEP 8** 준수
- **타입 힌트** 사용
- **독스트링** 작성

### 커밋 메시지
```
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 업데이트
style: 코드 스타일 변경
refactor: 코드 리팩토링
```

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 📞 지원 및 문의

- **개발자**: SN독학기숙학원
- **버전**: 1.0.0
- **최종 업데이트**: 2025-10-21

## 🎵 사용 예시

### 교육기관에서의 활용
- **기상 종소리**: 06:00
- **수업 시작**: 07:20, 08:40, 10:20, 13:00, 14:40, 16:40, 18:30, 21:30
- **쉬는 시간**: 08:30, 10:00, 14:20, 16:30, 19:50
- **식사 시간**: 12:10, 17:30
- **간식 시간**: 21:00
- **학습 종료**: 22:20
- **하루 일과 종료**: 22:30

---

*SN-Bell은 교육기관의 효율적인 시간 관리를 위한 종소리 시스템입니다.*
