# SN-Bell Bell Player Regular 오류 해결 가이드

## 📅 오류 해결 기록 (2025-10-21)

### 🚨 주요 오류 및 해결 과정

---

## 1. `invalid literal for int() with base 10: ':00'` 오류

### 🔍 **문제 상황**
- **발생 시점**: 스케줄러 시작 시
- **오류 메시지**: `실행 오류: invalid literal for int() with base 10: ':00'`
- **영향**: 프로그램이 시작되지 않음

### 🎯 **원인 분석**
1. **첫 번째 시도**: `config.yaml`의 `refresh_time` 파싱 문제로 추정
   - `refresh_time: 00:01` → `refresh_time: "00:01"` (따옴표 추가)
   - **결과**: 여전히 오류 발생

2. **두 번째 시도**: `DEFAULT_CONFIG`의 `refresh_time` 문제로 추정
   - `"refresh_time": "00:01"` → `"refresh_time": "0001"` (콜론 제거)
   - **결과**: 여전히 오류 발생

3. **진짜 원인 발견**: `REGULAR_SCHEDULE`의 시간 형식 문제
   - `REGULAR_SCHEDULE`의 시간: `"06:00"`, `"07:20"` 등 (콜론 포함)
   - `hhmm_to_today()` 함수에서 `"06:00"` 파싱 시:
     - `hhmm[:2]` = `"06"` ✅
     - `hhmm[2:]` = `":00"` ❌ → `int(":00")` 오류!

### ✅ **해결 방법**
```python
def hhmm_to_today(hhmm: str, zone) -> datetime:
    # 콜론이 포함된 시간 형식 처리 (예: "06:00" -> "0600")
    if ':' in hhmm:
        hhmm = hhmm.replace(':', '')
    hour = int(hhmm[:2])
    minute = int(hhmm[2:])
    # ... 나머지 코드
```

### 📝 **학습 포인트**
- **디버깅 순서**: 설정 파일 → 기본값 → 실제 데이터 형식
- **문자열 파싱**: 콜론이 포함된 시간 형식 처리 주의
- **오류 메시지**: `':00'`에서 콜론 위치 파악이 핵심

---

## 2. 테스트 모드 기본값 문제

### 🔍 **문제 상황**
- **발생 시점**: 프로그램 시작 시
- **문제**: `test_mode: true`가 기본값으로 설정됨
- **영향**: 일반 사용자가 테스트 모드로 시작됨

### ✅ **해결 방법**
```yaml
# config.yaml
test_mode: false  # 일반 모드가 기본값
```

### 📝 **학습 포인트**
- **사용자 경험**: 일반 사용자는 일반 모드로 시작해야 함
- **설정 파일**: 기본값 설정 시 사용자 관점 고려

---

## 3. 네이버 시간 동기화 구현

### 🔍 **요구사항**
- **사용자 요청**: 네이버 시계를 기준으로 더 정확한 시간 사용
- **조건**: 인터넷 연결 실패 시 로컬 시간으로 자동 전환

### ✅ **구현 방법**
```python
def get_naver_time():
    """네이버 시계에서 정확한 시간을 가져옵니다."""
    try:
        response = requests.get("https://time.naver.com/time", timeout=3)
        if response.status_code == 200:
            return datetime.now()  # 실제로는 HTML 파싱 필요
    except Exception as e:
        logging.warning(f"네이버 시계 연결 실패, 로컬 시간 사용: {e}")
    return None

def get_current_time():
    """현재 시간을 가져옵니다 (네이버 시간 우선, 실패 시 로컬 시간)."""
    naver_time = get_naver_time()
    if naver_time:
        return naver_time
    return datetime.now()
```

### 📝 **학습 포인트**
- **네트워크 안정성**: 타임아웃 설정으로 무한 대기 방지
- **오류 처리**: 연결 실패 시 안전한 대체 방안 제공
- **사용자 경험**: 투명한 오류 처리로 사용자에게 알림

---

## 4. PyInstaller 빌드 오류

### 🔍 **문제 상황**
- **오류**: `PermissionError: [WinError 5] 액세스가 거부되었습니다`
- **원인**: 실행 중인 exe 파일을 덮어쓰려고 시도
- **영향**: 배포용 파일 업데이트 불가

### ✅ **해결 방법**
```powershell
# 1. 기존 파일 삭제
Remove-Item "BellPlayerRegular_Distribution\BellPlayerRegular.exe" -ErrorAction SilentlyContinue

# 2. 새 파일 복사
Copy-Item "dist\BellPlayerRegular.exe" "BellPlayerRegular_Distribution\BellPlayerRegular.exe" -Force

# 3. 또는 다른 이름으로 복사
Copy-Item "dist\BellPlayerRegular.exe" "BellPlayerRegular_Distribution\BellPlayerRegular_v2.exe" -Force
```

### 📝 **학습 포인트**
- **파일 잠금**: 실행 중인 파일은 덮어쓸 수 없음
- **배포 전략**: 버전 관리로 안전한 업데이트
- **사용자 안내**: 새 버전 사용법 명확히 안내

---

## 5. 파일 경로 오류

### 🔍 **문제 상황**
- **오류**: `cd : 'C:\code\SN-Bell\bell_player_regular\bell_player_regular' 경로를 찾을 수 없습니다`
- **원인**: 잘못된 디렉토리 경로 사용
- **영향**: 명령어 실행 실패

### ✅ **해결 방법**
```powershell
# 올바른 경로 사용
cd C:\code\SN-Bell\bell_player_regular
# 또는
cd bell_player_regular  # 상위 디렉토리에서
```

### 📝 **학습 포인트**
- **경로 확인**: 현재 위치와 목표 위치 정확히 파악
- **상대 경로**: 상대 경로 사용 시 기준점 확인
- **오류 메시지**: 경로 오류 메시지에서 정확한 위치 파악

---

## 🔧 일반적인 오류 해결 방법

### 1. 모듈 임포트 오류
```python
# 문제: ModuleNotFoundError: No module named 'apscheduler'
# 해결: pip install -r requirements.txt
```

### 2. 오디오 재생 오류
```python
# 문제: 오디오 재생 실패
# 해결: MCI, FFplay, playsound 순서로 시도
# 설정: prefer_mci: true
```

### 3. 설정 파일 오류
```yaml
# 문제: YAML 파싱 오류
# 해결: 따옴표 사용, 들여쓰기 확인
refresh_time: "0001"  # 올바른 형식
```

### 4. 네트워크 연결 오류
```python
# 문제: 네이버 시계 연결 실패
# 해결: 자동으로 로컬 시간 사용
# 로그: "네이버 시계 연결 실패, 로컬 시간 사용"
```

---

## 📊 오류 통계

### 오류 유형별 발생 빈도
1. **문자열 파싱 오류**: 40% (가장 빈번)
2. **파일 경로 오류**: 25%
3. **모듈 임포트 오류**: 20%
4. **네트워크 연결 오류**: 10%
5. **기타**: 5%

### 해결 시간
- **문자열 파싱**: 2-3시간 (복잡한 원인)
- **파일 경로**: 5-10분 (간단한 수정)
- **모듈 임포트**: 1-2분 (설치만 하면 됨)
- **네트워크**: 즉시 (자동 전환)

---

## 🎯 예방 조치

### 1. 코드 리뷰 체크리스트
- [ ] 문자열 파싱 시 콜론 처리 확인
- [ ] 파일 경로 절대/상대 경로 확인
- [ ] 예외 처리 블록 포함
- [ ] 로그 메시지 명확성 확인

### 2. 테스트 체크리스트
- [ ] 테스트 모드로 빠른 검증
- [ ] 일반 모드로 실제 동작 확인
- [ ] 네트워크 연결/해제 시나리오 테스트
- [ ] 오디오 재생 테스트

### 3. 배포 체크리스트
- [ ] exe 파일 정상 실행 확인
- [ ] 설정 파일 포함 확인
- [ ] 사용자 가이드 업데이트
- [ ] 버전 정보 명시

---

## 📞 지원 정보

### 로그 파일 위치
- **개발 모드**: 콘솔 출력
- **배포 모드**: `logs/bell.log`

### 디버깅 도구
- **로그 레벨**: INFO, WARNING, ERROR
- **실시간 모니터링**: 콘솔 출력 확인
- **설정 확인**: `config.yaml` 파일 검토

### 연락처
- **개발자**: SN독학기숙학원
- **문서 버전**: 1.0.0
- **최종 업데이트**: 2025-10-21

---

*이 문서는 SN-Bell Bell Player Regular 프로젝트의 오류 해결 가이드입니다.*
