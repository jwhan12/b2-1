"""CLI의 공통 예외 처리를 분리하는 데코레이터."""

import functools
import sys
from collections.abc import Callable
from typing import ParamSpec

from .errors import AppError


P = ParamSpec("P")


def print_error(error: AppError) -> None:
    print(f"[오류] {error.message}", file=sys.stderr)
    print(f"[힌트] {error.hint}", file=sys.stderr)


def handle_cli_errors(function: Callable[P, int]) -> Callable[P, int]:
    @functools.wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> int:
        try:
            return function(*args, **kwargs)
        except AppError as exc:
            print_error(exc)
        except (KeyboardInterrupt, EOFError):
            print_error(AppError("입력이 중단되었습니다.", "명령을 다시 실행하세요."))
        except (OSError, UnicodeError) as exc:
            print_error(
                AppError(
                    f"파일을 처리할 수 없습니다: {exc}",
                    "파일 경로, 접근 권한, UTF-8 인코딩과 남은 디스크 공간을 확인하세요.",
                )
            )
        except Exception as exc:
            print_error(
                AppError(
                    f"명령을 완료하지 못했습니다: {type(exc).__name__}",
                    "입력값과 저장 파일을 확인한 뒤 다시 시도하세요.",
                )
            )
        return 1

    return wrapped

