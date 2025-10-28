"""
모든 단위 테스트를 실행하는 메인 스크립트
"""

import unittest
import sys
import os
from pathlib import Path

def run_all_tests():
    """모든 테스트를 실행합니다."""
    # 현재 디렉토리를 테스트 디렉토리로 설정
    test_dir = Path(__file__).parent
    os.chdir(test_dir)
    
    # 테스트 로더 생성
    loader = unittest.TestLoader()
    
    # 테스트 스위트 생성
    suite = unittest.TestSuite()
    
    # 테스트 모듈들을 추가
    test_modules = [
        'test_config',
        'test_time_handling', 
        'test_resource_management'
    ]
    
    print("=" * 60)
    print("SN-Bell 평상시 종소리 프로그램 - 단위 테스트")
    print("=" * 60)
    
    for module_name in test_modules:
        try:
            # 테스트 모듈 로드
            module_suite = loader.loadTestsFromName(module_name)
            suite.addTest(module_suite)
            print(f"✓ {module_name} 모듈 로드 완료")
        except Exception as e:
            print(f"✗ {module_name} 모듈 로드 실패: {e}")
    
    print("-" * 60)
    
    # 테스트 실행
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        descriptions=True,
        failfast=False
    )
    
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    print(f"실행된 테스트: {result.testsRun}")
    print(f"실패: {len(result.failures)}")
    print(f"오류: {len(result.errors)}")
    print(f"건너뜀: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
    
    if result.failures:
        print("\n실패한 테스트:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\n오류가 발생한 테스트:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100) if result.testsRun > 0 else 0
    print(f"\n성공률: {success_rate:.1f}%")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)