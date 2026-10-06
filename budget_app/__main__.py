"""`python -m budget_app` 실행 지점."""

def main() -> int:
    from .cli import run_cli

    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
