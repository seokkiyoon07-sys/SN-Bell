#!/usr/bin/env python3
"""
Bell Player Regular 테스트 실행 스크립트
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """테스트 실행 메인 함수"""
    # 현재 디렉토리를 프로젝트 루트로 설정
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print("🧪 Bell Player Regular 테스트 실행")
    print("=" * 50)
    
    # Python 경로에 현재 디렉토리 추가
    sys.path.insert(0, str(project_root))
    
    try:
        # pytest 사용 가능한지 확인
        result = subprocess.run([sys.executable, "-m", "pytest", "--version"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ pytest가 설치되지 않았습니다.")
            print("다음 명령으로 설치하세요: pip install pytest pytest-cov pytest-mock")
            return False
        
        # 테스트 실행
        print("📋 테스트 목록:")
        test_files = list(Path("tests").glob("test_*.py"))
        for i, test_file in enumerate(test_files, 1):
            print(f"  {i}. {test_file.name}")
        
        print("\n🚀 테스트 실행 중...")
        
        # pytest 실행
        cmd = [
            sys.executable, "-m", "pytest", 
            "tests/", 
            "-v",  # verbose
            "--tb=short",  # 간단한 traceback
            "--color=yes"  # 색상 출력
        ]
        
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print("\n✅ 모든 테스트가 성공적으로 완료되었습니다!")
        else:
            print("\n❌ 일부 테스트가 실패했습니다.")
            
        return result.returncode == 0
        
    except FileNotFoundError:
        print("❌ Python이 PATH에 없거나 pytest 모듈을 찾을 수 없습니다.")
        return False
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류 발생: {e}")
        return False

def run_specific_test():
    """특정 테스트 파일만 실행"""
    test_files = list(Path("tests").glob("test_*.py"))
    
    print("\n📋 사용 가능한 테스트:")
    for i, test_file in enumerate(test_files, 1):
        print(f"  {i}. {test_file.name}")
    
    try:
        choice = input("\n실행할 테스트 번호를 입력하세요 (엔터=모든 테스트): ").strip()
        
        if not choice:
            return main()
        
        choice_num = int(choice)
        if 1 <= choice_num <= len(test_files):
            test_file = test_files[choice_num - 1]
            print(f"\n🚀 {test_file.name} 테스트 실행 중...")
            
            cmd = [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"]
            result = subprocess.run(cmd)
            return result.returncode == 0
        else:
            print("❌ 잘못된 번호입니다.")
            return False
            
    except ValueError:
        print("❌ 숫자를 입력해주세요.")
        return False
    except KeyboardInterrupt:
        print("\n🚫 사용자가 테스트를 취소했습니다.")
        return False

if __name__ == "__main__":
    print("🔬 Bell Player Regular 테스트 도구")
    print("=" * 40)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--select":
        success = run_specific_test()
    else:
        success = main()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 테스트 완료!")
    else:
        print("⚠️  테스트에 문제가 있습니다. 로그를 확인해주세요.")
        sys.exit(1)