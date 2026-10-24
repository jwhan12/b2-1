"""`python3 -m budget_app` 실행 지점."""

def main() -> int: # 정수 반환
    from .cli import run_cli

    return run_cli() # run_cli가 반환한 값 main 함수가 그대로 반환


# raise: 예외 발생시켜 
# SystemExit(): 파이썬 프로그램 종료를 요청할 때 사용하는 내장 예외 클래스. 0일때 프로그램 정상 종료
# main > SystemExit 실행
if __name__ == "__main__":
    raise SystemExit(main()) 
