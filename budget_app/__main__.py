"""`python -m budget_app` 실행 지점."""

import sys


def main() -> int:
    if sys.version_info < (3, 10):
        print("[오류] Python 3.10 이상이 필요합니다.", file=sys.stderr)
        print("[힌트] Python 3.10 이상의 python 명령으로 다시 실행하세요.", file=sys.stderr)
        return 1
    from .cli import run_cli

    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
