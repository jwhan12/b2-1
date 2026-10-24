"""사용자 명령과 대화형 입력. 사용자에게 입력받고 해당 서비스 메서드를 호출하여 결과 출력."""

import argparse # 터미널 명령어를 쉽게 분석할 수 있도록 도와주는 표준 라이브러리
from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import TypeVar

from .decorators import handle_cli_errors, print_error
from .errors import AppError
from .models import Transaction
from .repositories import Storage
from .services import BudgetService
from .validators import validate_amount, validate_date, validate_type


T = TypeVar("T")


# 사용자가 터미널에 명령어나 옵션을 잘못 작성했을 경우 오류 메세지 보기 쉽게 출력
class UserArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None: # 명령어를 해석하는 과정에서 오류 발생했을 때 호출
        print_error(
            AppError(
                f"명령 인자가 올바르지 않습니다: {message}",
                "해당 명령에 --help를 붙여 사용법을 확인하세요.",
            )
        )
        raise SystemExit(2) # 명령어 사용 오류 코드


# 사용자가 입력한 값이 올바른 양의 정수인지 검사
def _positive_argument(raw: str) -> int: # 문자열로 받은 입력값을 정수로 반환
    try:
        return validate_amount(raw) # 전달받은 값이 올바른 양의 정수인지 검사
    except AppError as exc: # AppError 발생 시 ArgumentTypeError로 바꿔 argparse가 처리
        raise argparse.ArgumentTypeError(exc.message) from exc


# 사용자가 가계부 데이터를 저장하거나 불러올 폴더 경로 지정
# 여러 명령어가 공통으로 사용할 데이터 저장 경로 옵션 등록
def _add_data_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("./data"),
        help="JSONL 저장 폴더 (기본값: 현재 디렉터리의 ./data)",
    )


# 사용자가 터미널에서 사용할 수 있는 명령어와 옵션 정의 후 그 규칙을 담은 객체 반환
def build_parser() -> UserArgumentParser:
    parser = UserArgumentParser(prog="python -m budget_app", description="파일 기반 콘솔 가계부") # 명령어 규칙 담을 parser 객체 생성
    commands = parser.add_subparsers(dest="command", required=True, parser_class=UserArgumentParser)

    add_parser = commands.add_parser("add", help="거래를 대화형으로 추가") # 사용 가능한 명령어 정의
    _add_data_dir(add_parser)

    list_parser = commands.add_parser("list", help="최신순 거래 목록")
    list_parser.add_argument("--limit", type=_positive_argument, default=20, help="출력 건수 (기본값: 20)")
    _add_data_dir(list_parser)

    search_parser = commands.add_parser("search", help="조건에 맞는 거래 검색")
    search_parser.add_argument("--from", dest="date_from", help="시작일 YYYY-MM-DD") # dest: 분석한 값을 어떤 이름으로 저장할지 지정
    search_parser.add_argument("--to", dest="date_to", help="종료일 YYYY-MM-DD")
    search_parser.add_argument("--category", help="카테고리")
    search_parser.add_argument("--type", dest="transaction_type", help="income 또는 expense")
    search_parser.add_argument("--q", help="메모에 포함된 문자열")
    search_parser.add_argument("--tag", help="태그 이름")
    _add_data_dir(search_parser)

    update_parser = commands.add_parser("update", help="ID로 거래 수정")
    update_parser.add_argument("--id", required=True, help="수정할 거래 ID")
    update_parser.add_argument("--date", help="날짜 YYYY-MM-DD")
    update_parser.add_argument("--type", help="income 또는 expense")
    update_parser.add_argument("--category", help="등록된 카테고리")
    update_parser.add_argument("--amount", help="양수 정수")
    update_parser.add_argument("--memo", help="메모; 빈 문자열은 삭제")
    update_parser.add_argument("--tags", help="쉼표로 구분; 빈 문자열은 삭제")
    _add_data_dir(update_parser)

    delete_parser = commands.add_parser("delete", help="ID로 거래 삭제")
    delete_parser.add_argument("--id", required=True, help="삭제할 거래 ID")
    _add_data_dir(delete_parser)

    summary_parser = commands.add_parser("summary", help="월별 요약")
    summary_parser.add_argument("--month", required=True, help="월 YYYY-MM")
    summary_parser.add_argument("--top", type=_positive_argument, default=3, help="지출 카테고리 건수 (기본값: 3)")
    _add_data_dir(summary_parser)

    budget_parser = commands.add_parser("budget", help="월 예산 관리")
    budget_commands = budget_parser.add_subparsers(dest="action", required=True, parser_class=UserArgumentParser)
    budget_set = budget_commands.add_parser("set", help="월 예산 저장 또는 갱신")
    budget_set.add_argument("--month", required=True, help="월 YYYY-MM")
    budget_set.add_argument("--amount", required=True, help="양수 정수")
    _add_data_dir(budget_set)
    budget_show = budget_commands.add_parser("show", help="월 예산 조회")
    budget_show.add_argument("--month", required=True, help="월 YYYY-MM")
    _add_data_dir(budget_show)

    category_parser = commands.add_parser("category", help="카테고리 관리")
    category_commands = category_parser.add_subparsers(dest="action", required=True, parser_class=UserArgumentParser)
    for action, help_text in (
        ("add", "카테고리를 대화형으로 추가"),
        ("list", "카테고리 목록"),
        ("remove", "카테고리를 대화형으로 삭제"),
    ):
        child = category_commands.add_parser(action, help=help_text)
        _add_data_dir(child)

    import_parser = commands.add_parser("import", help="CSV 거래 가져오기")
    import_parser.add_argument("--from", dest="source", type=Path, required=True, help="UTF-8 CSV 파일")
    _add_data_dir(import_parser)

    export_parser = commands.add_parser("export", help="CSV 거래 내보내기")
    export_parser.add_argument("--out", type=Path, required=True, help="출력 CSV 파일")
    export_parser.add_argument("--month", help="월 YYYY-MM")
    export_parser.add_argument("--from", dest="date_from", help="시작일 YYYY-MM-DD")
    export_parser.add_argument("--to", dest="date_to", help="종료일 YYYY-MM-DD")
    _add_data_dir(export_parser)
    return parser # 완성된 명령어 규칙 run_cli()에서 사용할 수 있도록 parser 객체 반환


# 사용자에게 값을 입력받고, 입력한 값이 올바른지 검사하는 함수. 만약 잘못된 값 입력 시 다시 입력받도록 반복
def _ask(prompt: str, parse: Callable[[str], T]) -> T:
    while True: 
        raw = input(prompt)
        try:
            return parse(raw)
        except AppError as exc: # 잘못된 값일 경우 AppError 발생
            print_error(exc)


# 가계부 거래 내역을 사용자가 읽기 편한 문자열 형태로 변환
def _format_transaction(transaction: Transaction) -> str:
    text = (
        f"{transaction.id} | {transaction.date} | {transaction.type} | "
        f"{transaction.category} | {transaction.amount} | {transaction.memo}"
    )
    if transaction.tags: # 태그가 있을 경우 
        text += " | " + ",".join(transaction.tags)
    return text


# 검색된 거래 내역을 하나씩 꺼내어 실제 터미널에 출력
def _print_transactions(transactions: Iterable[Transaction]) -> None:
    found = False
    for transaction in transactions: # 조회된 거래 내역 하나씩 꺼냄
        found = True
        print(_format_transaction(transaction)) # 거래 데이터를 보기 좋은 문자열로 변환한 다음 출력
    if not found: # 거래 내역이 없을 경우
        print("데이터 없음")


# 해석된 명령어에 따라 가계부 기능 수행
@handle_cli_errors
def run_cli(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv) # 입력한 명령어와 옵션값을 분석 후 args 변수에 저장
    service = BudgetService(Storage(args.data_dir)) # 가계부의 주요 기능 처리할 수 있는 객체 생성(데이터 불러오고 저장(사용자가 지정한 데이터 저장 폴더 경로))

    if args.command == "add": # 거래 내역 저장
        transaction_date = _ask("날짜(YYYY-MM-DD): ", validate_date) # validate_date: 입력받은 날짜 검사하는 함수
        transaction_type = _ask("타입(income/expense): ", validate_type) # validate_type > 함수 자체를 인자로 전달
        category = _ask("카테고리: ", service.require_category)
        amount = _ask("금액(양수 정수): ", validate_amount)
        memo = input("메모(선택): ")
        tags = input("태그(쉼표로 구분, 없으면 엔터): ")
        transaction = service.add_transaction( # service로 가계부 메서드 호출
            transaction_date, transaction_type, category, amount, memo, tags
        )
        print(f"[저장 완료] id={transaction.id}") # 저장한 거래의 고유 ID
    elif args.command == "list": # 저장된 거래 내역 조회
        _print_transactions(service.list_transactions(args.limit)) # 조회한 거래내역 화면에 출력(저장된 거래 내역 조회(조회할 개수 가져옴))
    elif args.command == "search": # 사용자가 지정한 조건에 맞는 거래 찾아서 출력
        _print_transactions(
            service.search_transactions( # 전달받은 조건에 맞는 거래 내역 검색
                date_from=args.date_from,
                date_to=args.date_to,
                category=args.category,
                transaction_type=args.transaction_type,
                query=args.q,
                tag=args.tag,
            )
        )
    elif args.command == "update": # 이미 저장된 거래 내역 수정
        service.update_transaction(
            args.id,
            date=args.date,
            type=args.type,
            category=args.category,
            amount=args.amount,
            memo=args.memo,
            tags=args.tags,
        )
        print(f"[수정 완료] id={args.id}")
    elif args.command == "delete": # 저장된 거래 내역 삭제
        service.delete_transaction(args.id)
        print(f"[삭제 완료] id={args.id}")
    elif args.command == "summary":
        summary = service.month_summary(args.month, args.top)
        if summary.count == 0:
            print(f"{args.month}: 데이터 없음")
        print(f"총 수입: {summary.income}원")
        print(f"총 지출: {summary.expense}원")
        print(f"잔액: {summary.balance}원")
        if summary.budget is not None: 
            usage = Decimal(summary.expense) * 100 / Decimal(summary.budget)
            print(f"예산: {summary.budget}원 (사용률 {usage:.1f}%)") # 예산 사용률 계산 및 출력
            if summary.expense > summary.budget:
                print("[경고] 월 예산을 초과했습니다.") # 예산 초과 시 경고 출력
        if summary.category_expenses:
            print(f"지출 TOP {args.top}")
            for rank, (category, amount) in enumerate(summary.category_expenses, 1):
                print(f"{rank}) {category} {amount}원") # 지출 상위 카테고리 출력
    elif args.command == "budget":
        if args.action == "set":
            amount = service.set_budget(args.month, args.amount)
            print(f"[저장 완료] {args.month} 예산 {amount}원")
        else:
            amount = service.get_budget(args.month)
            print(f"{args.month} 예산: {amount}원" if amount is not None else f"{args.month}: 설정된 예산 없음")
    elif args.command == "category":
        if args.action == "list":
            for name in service.category_names():
                print(f"- {name}")
        elif args.action == "add":
            name = service.add_category(input("카테고리명: "))
            print(f"[저장 완료] category={name}")
        else:
            name = service.remove_category(input("삭제할 카테고리명: "))
            print(f"[삭제 완료] category={name}")
    elif args.command == "import":
        def report_invalid(line: int, error: AppError) -> None:
            print_error(AppError(f"CSV {line}행: {error.message}", error.hint))

        result = service.import_csv(args.source, report_invalid)
        print(f"[완료] imported={result.imported}, skipped={result.skipped}")
        return 1 if result.skipped else 0
    elif args.command == "export":
        count = service.export_csv(
            args.out, month=args.month, date_from=args.date_from, date_to=args.date_to
        )
        print(f"[완료] {args.out} ({count} records)")
    return 0 # 정상적으로 처리 완료
