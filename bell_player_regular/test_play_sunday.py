#!/usr/bin/env python3
"""일요일 사운드 재생 직접 테스트"""

from app import *
import sys

def test_sunday_playback():
    print("=== 일요일 사운드 재생 테스트 ===")
    
    config = load_config()
    zone = get_tz(config.get("timezone", "Asia/Seoul"))
    
    # 일요일 폴더 확인
    sunday_dir = config.get('sounds_dir_sunday')
    if not sunday_dir or not os.path.isdir(sunday_dir):
        print("❌ 일요일 사운드 폴더가 설정되지 않았거나 존재하지 않습니다.")
        return False
        
    print(f"✅ 일요일 사운드 폴더: {sunday_dir}")
    
    # 일요일 스케줄 첫 번째 항목 재생 (12:10 식사시간종)
    first_item = SUNDAY_SCHEDULE[0]
    index, time_str, description = first_item
    
    print(f"\n일요일 스케줄 첫 번째 항목 재생:")
    print(f"  {index}. {time_str} - {description}")
    
    # 강제로 일요일 모드로 전환해서 재생
    # 임시로 is_sunday 함수 교체
    def fake_is_sunday(zone):
        return True
    
    original_is_sunday = globals()['is_sunday']
    globals()['is_sunday'] = fake_is_sunday
    
    try:
        # 일요일 폴더에서 사운드 파일 찾기
        path = find_existing_sound(index, config, zone)
        if path:
            print(f"✅ 사운드 파일 발견: {path}")
            
            # 사운드 재생
            print("🔊 사운드 재생 시작...")
            play_sound_for_index(index, config, zone)
            print("✅ 재생 완료!")
            return True
        else:
            print("❌ 사운드 파일을 찾을 수 없습니다.")
            return False
            
    except Exception as e:
        print(f"❌ 재생 중 오류 발생: {e}")
        return False
    finally:
        # 원래 함수 복원
        globals()['is_sunday'] = original_is_sunday

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "play":
        test_sunday_playback()
    else:
        print("일요일 사운드 재생을 테스트하려면:")
        print("  python test_play_sunday.py play")
        print("\n현재 설정 확인:")
        config = load_config()
        print(f"  평일 폴더: {get_sounds_dir(config)}")
        print(f"  일요일 폴더: {config.get('sounds_dir_sunday')}")