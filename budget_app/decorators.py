"""CLI의 공통 예외 처리를 분리하는 데코레이터. 프로그램 실행 중 오류 발생 시 사용자에게 안내."""

import functools
import sys
from collections.abc import Callable
from typing import ParamSpec

from .errors import AppError


P = ParamSpec("P")


# 오류 발생 시 오류 내용과 해결 방법을 사용자에게 안내
def print_error(error: AppError) -> None:
    print(f"[오류] {error.message}", file=sys.stderr) # 오류 종류 설명
    print(f"[힌트] {error.hint}", file=sys.stderr) # 해결 방법 안내


# 명령어 실행 시 오류가 발생하는지 확인
def handle_cli_errors(function: Callable[P, int]) -> Callable[P, int]:
    @functools.wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> int:
        try:
            return function(*args, **kwargs)
        except AppError as exc: # 가계부 프로그램에서 정의한 오류
            print_error(exc)
        except (KeyboardInterrupt, EOFError): # 사용자가 입력을 중단하거나 입력을 더 받을 수 없는 상황
            print_error(AppError("입력이 중단되었습니다.", "명령을 다시 실행하세요."))
        except (OSError, UnicodeError) as exc: # 파일 처리 또는 문자 인코딩 문제
            print_error(
                AppError(
                    f"파일을 처리할 수 없습니다: {exc}",
                    "파일 경로, 접근 권한, UTF-8 인코딩과 남은 디스크 공간을 확인하세요.",
                )
            )
        except Exception as exc: # 위에서 처리하지 못한 일반적인 오류
            print_error(
                AppError(
                    f"명령을 완료하지 못했습니다: {type(exc).__name__}",
                    "입력값과 저장 파일을 확인한 뒤 다시 시도하세요.",
                )
            )
        return 1

    return wrapped

