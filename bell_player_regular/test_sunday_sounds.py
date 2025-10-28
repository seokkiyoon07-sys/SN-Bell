#!/usr/bin/env python3
"""일요일 사운드 폴더 기능 테스트"""

from app import *

def test_sunday_sounds():
    print("=== 일요일 사운드 폴더 기능 테스트 ===")
    
    # 설정 로드
    config = load_config()
    zone = get_tz(config.get("timezone", "Asia/Seoul"))
    
    print(f"1. 평일 사운드 폴더: {get_sounds_dir(config)}")
    print(f"2. 일요일 사운드 폴더 설정: {config.get('sounds_dir_sunday')}")
    print(f"3. 오늘이 일요일인가: {is_sunday(zone)}")
    print(f"4. 현재 요일별 폴더: {get_sounds_dir_for_day(config, zone)}")
    
    # 사운드 파일 찾기 테스트
    print("\n=== 사운드 파일 찾기 테스트 ===")
    for index in [1, 7, 12]:  # 일요일 스케줄에 있는 몇 개 인덱스
        path = find_existing_sound(index, config, zone)
        if path:
            print(f"인덱스 {index}: {path}")
        else:
            print(f"인덱스 {index}: 파일 없음")
    
    print("\n=== 강제로 일요일로 테스트 ===")
    # 직접 일요일 폴더 테스트
    sunday_dir = config.get('sounds_dir_sunday')
    if sunday_dir and os.path.isdir(sunday_dir):
        print(f"일요일 폴더: {sunday_dir}")
        print(f"일요일 폴더 파일 목록: {os.listdir(sunday_dir)}")
        
        # 직접 일요일 폴더에서 파일 찾기
        for index in [1, 7, 12]:
            # 파일 이름 후보들
            name_candidates = [f"{index:02d}", str(index)]
            ext_candidates = ["mp3", "wav", "m4a", "aac", "flac", "ogg"]
            found = False
            for name in name_candidates:
                for ext in ext_candidates:
                    path = os.path.join(sunday_dir, f"{name}.{ext}")
                    if os.path.exists(path):
                        print(f"일요일 인덱스 {index}: {path}")
                        found = True
                        break
                if found:
                    break
            if not found:
                print(f"일요일 인덱스 {index}: 파일 없음")
    else:
        print("일요일 폴더가 설정되지 않았거나 존재하지 않음")

if __name__ == "__main__":
    test_sunday_sounds()