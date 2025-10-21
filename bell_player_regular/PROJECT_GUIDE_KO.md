# SN-Bell Bell Player Regular 프로젝트 가이드 (KO)

## 📋 프로젝트 개요

**SN-Bell Bell Player Regular**는 고정된 스케줄에 따라 자동으로 종소리를 재생하는 프로그램입니다. 사용자가 시간을 별도로 설정할 필요 없이 미리 정의된 20개 시간표에 따라 자동으로 동작합니다.

## 🏗️ 프로젝트 구조

```
bell_player_regular/
├── app.py                    # 핵심 로직 (스케줄링, 오디오 재생)
├── gui.py                    # GUI 인터페이스
├── config.yaml              # 설정 파일
├── requirements.txt         # Python 의존성
├── BellPlayerRegular.spec   # PyInstaller 설정
├── README.md               # 사용자 가이드
├── PROJECT_GUIDE_KO.md     # 개발자 가이드 (이 파일)
├── ERROR_SOLUTIONS.md      # 오류 해결 가이드
├── dist/                   # 빌드된 실행 파일
└── BellPlayerRegular_Distribution/  # 배포용 패키지
```

## 🎯 핵심 기능

### 1. 고정 스케줄 시스템
- **20개 시간표**: 미리 정의된 시간에 자동 재생
- **자동 스케줄링**: 매일 자동으로 다음날 스케줄 설정
- **테스트 모드**: 3초 간격으로 빠른 테스트 가능

### 2. 네이버 시간 동기화
- **네이버 시계 우선**: 더 정확한 시간 기준
- **자동 전환**: 네트워크 실패 시 로컬 시간 사용
- **안정성**: 인터넷 문제 시에도 정상 동작

### 3. 오디오 재생 시스템
- **다중 백엔드**: MCI, FFplay, playsound 지원
- **자동 감지**: 사용 가능한 오디오 시스템 자동 선택
- **오류 처리**: 재생 실패 시 대체 방법 시도

## 🔧 개발 환경 설정

### 필수 요구사항
- Python 3.13+
- Windows 10/11
- 인터넷 연결 (네이버 시간 동기화용)

### 의존성 설치
```bash
pip install -r requirements.txt
```

### 개발 모드 실행
```bash
python gui.py
```

## 📁 주요 파일 설명

### app.py
**핵심 로직을 담당하는 메인 모듈**

```python
# 주요 함수들
- get_naver_time()           # 네이버 시계에서 시간 가져오기
- get_current_time()         # 현재 시간 (네이버 우선)
- schedule_today()           # 오늘 스케줄 설정
- schedule_next_day_refresh() # 다음날 스케줄 갱신
- play_sound_for_index()     # 인덱스별 사운드 재생
```

**핵심 상수:**
```python
REGULAR_SCHEDULE = [
    (1, "06:00", "기상종소리"),
    (2, "07:20", "시작종"),
    # ... 20개 항목
]
```

### gui.py
**Tkinter 기반 GUI 인터페이스**

```python
class BellRegularGUI:
    def __init__(self, root):
        # GUI 초기화
    
    def start_scheduler(self):
        # 스케줄러 시작
    
    def stop_scheduler(self):
        # 스케줄러 중지
    
    def open_clock_window(self):
        # 시계 창 열기 (네이버 시간 지원)
```

### config.yaml
**프로그램 설정 파일**

```yaml
timezone: Asia/Seoul
test_mode: false              # 테스트 모드 비활성화
autoplay_next_day: true       # 다음날 자동 스케줄링
refresh_time: "0001"          # 새벽 1시에 스케줄 갱신
sounds_dir: C:\code\SN-Bell\bell_sound_regular
```

## 🚀 빌드 및 배포

### PyInstaller로 실행 파일 생성
```bash
python -m PyInstaller BellPlayerRegular.spec --clean
```

### 배포용 패키지 생성
1. `dist/BellPlayerRegular.exe` 생성
2. `BellPlayerRegular_Distribution/` 폴더에 복사
3. `사용가이드.txt` 포함

## 🐛 디버깅 가이드

### 로그 확인
- **로그 파일**: `logs/bell.log`
- **실시간 로그**: 콘솔 출력
- **로그 레벨**: INFO, WARNING, ERROR

### 일반적인 문제들
1. **오디오 재생 실패**: MCI, FFplay, playsound 순서로 시도
2. **네트워크 연결 실패**: 자동으로 로컬 시간 사용
3. **스케줄 오류**: `refresh_time` 형식 확인

## 🔄 개발 워크플로우

### 1. 기능 추가
1. `app.py`에 핵심 로직 구현
2. `gui.py`에 UI 요소 추가
3. `config.yaml`에 설정 옵션 추가

### 2. 테스트
1. 개발 모드로 실행: `python gui.py`
2. 테스트 모드로 빠른 검증
3. 일반 모드로 실제 동작 확인

### 3. 빌드 및 배포
1. PyInstaller로 exe 생성
2. 배포용 폴더에 복사
3. 사용자 가이드 업데이트

## 📊 성능 최적화

### 메모리 사용량
- **기본**: ~50MB
- **오디오 로딩**: +10MB per file
- **스케줄러**: +5MB

### CPU 사용량
- **대기 상태**: <1%
- **오디오 재생**: 5-10%
- **네이버 시간 동기화**: 일시적 10%

## 🔒 보안 고려사항

### 네트워크 보안
- **HTTPS**: 네이버 시계 API는 HTTPS 사용
- **타임아웃**: 3초 제한으로 무한 대기 방지
- **오류 처리**: 네트워크 실패 시 안전한 대체 방안

### 파일 시스템
- **읽기 전용**: 설정 파일은 읽기만 수행
- **로그 회전**: 로그 파일 크기 제한
- **임시 파일**: 자동 정리

## 📈 향후 개선 방향

### 단기 목표
- [ ] 더 정확한 네이버 시간 파싱
- [ ] 오디오 품질 설정 옵션
- [ ] 스케줄 편집 기능

### 장기 목표
- [ ] 웹 인터페이스
- [ ] 모바일 앱 연동
- [ ] 클라우드 동기화

## 🤝 기여 가이드

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

## 📞 지원 및 문의

- **개발자**: SN독학기숙학원
- **버전**: 1.0.0
- **최종 업데이트**: 2025-10-21

---

*이 문서는 SN-Bell Bell Player Regular 프로젝트의 개발 가이드입니다.*
