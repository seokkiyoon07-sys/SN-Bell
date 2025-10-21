# 평상시 종소리 프로그램 배포용 패키지 생성 스크립트

Write-Host "평상시 종소리 프로그램 배포용 패키지 생성 중..." -ForegroundColor Green

# 배포용 폴더 생성
$distFolder = "BellPlayerRegular_배포용"
if (Test-Path $distFolder) {
    Remove-Item $distFolder -Recurse -Force
}
New-Item -ItemType Directory -Path $distFolder

# exe 파일 복사
Copy-Item "dist\BellPlayerRegular.exe" -Destination "$distFolder\"

# 설정 파일 복사
Copy-Item "config.yaml" -Destination "$distFolder\"

# README 파일 복사
Copy-Item "README.md" -Destination "$distFolder\"

# 사운드 폴더 생성
New-Item -ItemType Directory -Path "$distFolder\sounds"

# 로그 폴더 생성
New-Item -ItemType Directory -Path "$distFolder\logs"

# 사용자 가이드 생성
$userGuide = @"
# 평상시 종소리 프로그램 사용 가이드

## 🚀 빠른 시작

1. **BellPlayerRegular.exe** 파일을 더블클릭하여 실행
2. 사운드 폴더 경로를 설정 (기본: sounds 폴더)
3. "스케줄러 시작" 버튼 클릭

## 📁 파일 구성

- **BellPlayerRegular.exe**: 메인 프로그램
- **config.yaml**: 설정 파일
- **sounds/**: 종소리 파일 폴더 (01.mp3 ~ 20.mp3)
- **logs/**: 로그 파일 폴더
- **README.md**: 상세 사용 설명서

## 🎵 종소리 파일 준비

sounds 폴더에 다음 파일들을 준비하세요:
- 01.mp3 (06:00 기상종소리)
- 02.mp3 (07:20 시작종)
- 03.mp3 (08:30 쉬는시간종)
- ... (총 20개 파일)

## ⚙️ 기본 설정

- **볼륨**: 0~1 사이 값
- **MCI 우선 사용**: Windows 내장 오디오 (권장)
- **테스트 모드**: 모든 종소리를 3초 간격으로 재생

## 🎮 사용법

1. **자동 재생**: "스케줄러 시작" → 고정된 시간에 자동 재생
2. **수동 재생**: 체크박스 선택 → "선택 재생"
3. **테스트**: "테스트 모드" 체크 후 시작

## 📞 문의

개발: SN독학기숙학원
버전: v1.0
"@

$userGuide | Out-File -FilePath "$distFolder\사용가이드.txt" -Encoding UTF8

Write-Host "배포용 패키지가 생성되었습니다: $distFolder" -ForegroundColor Green
Write-Host "포함된 파일들:" -ForegroundColor Yellow
Get-ChildItem $distFolder | ForEach-Object { Write-Host "  - $($_.Name)" -ForegroundColor Cyan }
