"""가계부 규칙과 CSV 입출력."""

import csv
import heapq
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from .errors import AppError
from .models import ImportResult, MonthSummary, Transaction
from .repositories import Storage
from .validators import (
    parse_tags,
    validate_amount,
    validate_category_name,
    validate_date,
    validate_month,
    validate_type,
)


CSV_COLUMNS = ("date", "type", "category", "amount", "memo", "tags")
CSV_REQUIRED = set(CSV_COLUMNS[:4])
SEARCH_BATCH_SIZE = 256


class BudgetService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def category_names(self) -> list[str]:
        return self.storage.categories.list_names()

    def require_category(self, value: str) -> str:
        name = validate_category_name(value)
        if name not in self.category_names():
            raise AppError(
                f"등록되지 않은 카테고리입니다: {name}",
                "category list로 목록을 확인하거나 category add로 먼저 등록하세요.",
            )
        return name

    def add_category(self, value: str) -> str:
        name = validate_category_name(value)
        names = self.category_names()
        if name in names:
            raise AppError("이미 등록된 카테고리입니다.", "category list로 현재 목록을 확인하세요.")
        names.append(name)
        self.storage.categories.save_names(names)
        return name

    def remove_category(self, value: str) -> str:
        name = validate_category_name(value)
        names = self.category_names()
        if name not in names:
            raise AppError("해당 카테고리가 없습니다.", "category list로 현재 목록을 확인하세요.")
        if len(names) == 1:
            raise AppError("마지막 카테고리는 삭제할 수 없습니다.", "다른 카테고리를 먼저 추가하세요.")
        if any(tx.category == name for _, tx in self.storage.transactions.iter_transactions()):
            raise AppError(
                "사용 중인 카테고리는 삭제할 수 없습니다.",
                "거래를 다른 카테고리로 수정하거나 삭제한 뒤 다시 시도하세요.",
            )
        self.storage.categories.save_names([item for item in names if item != name])
        return name

    def _new_transaction(
        self,
        transaction_date: str,
        transaction_type: str,
        category: str,
        amount: str | int,
        memo: str = "",
        tags: str = "",
        *,
        known_categories: set[str] | None = None,
    ) -> Transaction:
        parsed_date = validate_date(transaction_date)
        parsed_type = validate_type(transaction_type)
        parsed_category = validate_category_name(category)
        if known_categories is None:
            parsed_category = self.require_category(parsed_category)
        elif parsed_category not in known_categories:
            raise AppError(
                f"등록되지 않은 카테고리입니다: {parsed_category}",
                "category add로 먼저 등록하세요.",
            )
        parsed_amount = validate_amount(amount)
        return Transaction(
            id="TX-" + uuid4().hex,
            type=parsed_type,
            date=parsed_date,
            amount=parsed_amount,
            category=parsed_category,
            memo=memo,
            tags=parse_tags(tags),
        )

    def add_transaction(
        self,
        transaction_date: str,
        transaction_type: str,
        category: str,
        amount: str | int,
        memo: str = "",
        tags: str = "",
    ) -> Transaction:
        transaction = self._new_transaction(
            transaction_date, transaction_type, category, amount, memo, tags
        )
        self.storage.transactions.append(transaction)
        return transaction

    def list_transactions(self, limit: int = 20) -> list[Transaction]:
        if limit <= 0:
            raise AppError("목록 건수는 양수여야 합니다.", "--limit에 1 이상의 정수를 지정하세요.")
        selected = heapq.nlargest(
            limit,
            self.storage.transactions.iter_transactions(),
            key=lambda item: (item[1].date, item[0]),
        )
        return [transaction for _, transaction in selected]

    def update_transaction(self, identifier: str, **changes: str | None) -> None:
        provided = {key: value for key, value in changes.items() if value is not None}
        if not provided:
            raise AppError("수정할 필드가 없습니다.", "--date, --amount 등 변경할 옵션을 지정하세요.")
        updates: dict[str, str | int | list[str]] = {}
        if "date" in provided:
            updates["date"] = validate_date(provided["date"])
        if "type" in provided:
            updates["type"] = validate_type(provided["type"])
        if "category" in provided:
            updates["category"] = self.require_category(provided["category"])
        if "amount" in provided:
            updates["amount"] = validate_amount(provided["amount"])
        if "memo" in provided:
            updates["memo"] = provided["memo"]
        if "tags" in provided:
            updates["tags"] = parse_tags(provided["tags"])

        def apply(transaction: Transaction) -> Transaction:
            return replace(transaction, **updates)

        self.storage.transactions.rewrite_one(identifier, apply)

    def delete_transaction(self, identifier: str) -> None:
        self.storage.transactions.rewrite_one(identifier, lambda _: None)

    def search_transactions(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        category: str | None = None,
        transaction_type: str | None = None,
        query: str | None = None,
        tag: str | None = None,
    ) -> Iterator[Transaction]:
        if date_from is not None:
            date_from = validate_date(date_from)
        if date_to is not None:
            date_to = validate_date(date_to)
        if date_from is not None and date_to is not None and date_from > date_to:
            raise AppError("시작일이 종료일보다 늦습니다.", "--from과 --to 날짜의 순서를 확인하세요.")
        if category is not None:
            category = self.require_category(category)
        if transaction_type is not None:
            transaction_type = validate_type(transaction_type)
        if tag is not None and not tag.strip():
            raise AppError("검색 태그가 비어 있습니다.", "--tag에 태그 이름을 입력하세요.")

        def matches(transaction: Transaction) -> bool:
            return (
                (date_from is None or transaction.date >= date_from)
                and (date_to is None or transaction.date <= date_to)
                and (category is None or transaction.category == category)
                and (transaction_type is None or transaction.type == transaction_type)
                and (query is None or query in transaction.memo)
                and (tag is None or tag in transaction.tags)
            )

        cursor: tuple[str, int] | None = None
        while True:
            batch = heapq.nlargest(
                SEARCH_BATCH_SIZE,
                (
                    (index, transaction)
                    for index, transaction in self.storage.transactions.iter_transactions()
                    if matches(transaction)
                    and (cursor is None or (transaction.date, index) < cursor)
                ),
                key=lambda item: (item[1].date, item[0]),
            )
            if not batch:
                return
            for _, transaction in batch:
                yield transaction
            last_index, last_transaction = batch[-1]
            cursor = (last_transaction.date, last_index)

    def month_summary(self, month: str, top: int = 3) -> MonthSummary:
        month = validate_month(month)
        if top <= 0:
            raise AppError("TOP 건수는 양수여야 합니다.", "--top에 1 이상의 정수를 지정하세요.")
        income = 0
        expense = 0
        count = 0
        by_category: dict[str, int] = defaultdict(int)
        for _, transaction in self.storage.transactions.iter_transactions():
            if not transaction.date.startswith(month + "-"):
                continue
            count += 1
            if transaction.type == "income":
                income += transaction.amount
            else:
                expense += transaction.amount
                by_category[transaction.category] += transaction.amount
        ranked = sorted(by_category.items(), key=lambda item: (-item[1], item[0]))[:top]
        return MonthSummary(
            count=count,
            income=income,
            expense=expense,
            category_expenses=ranked,
            budget=self.storage.budgets.list_budgets().get(month),
        )

    def set_budget(self, month: str, amount: str | int) -> int:
        month = validate_month(month)
        amount = validate_amount(amount)
        budgets = self.storage.budgets.list_budgets()
        budgets[month] = amount
        self.storage.budgets.save_budgets(budgets)
        return amount

    def get_budget(self, month: str) -> int | None:
        month = validate_month(month)
        return self.storage.budgets.list_budgets().get(month)

    def import_csv(
        self,
        source_path: Path,
        on_invalid: Callable[[int, AppError], None],
    ) -> ImportResult:
        if source_path.resolve() in self._data_file_paths():
            raise AppError("저장 파일을 CSV 가져오기 원본으로 사용할 수 없습니다.", "별도 CSV 파일 경로를 지정하세요.")
        imported = 0
        skipped = 0
        categories = set(self.category_names())
        try:
            with source_path.open("r", encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source, strict=True)
                try:
                    columns = reader.fieldnames
                except csv.Error as exc:
                    raise AppError("CSV 헤더를 읽을 수 없습니다. imported=0, skipped=0", "UTF-8 CSV 헤더를 확인하세요.") from exc
                if (
                    columns is None
                    or not CSV_REQUIRED.issubset(columns)
                    or len(columns) != len(set(columns))
                    or not set(columns).issubset(CSV_COLUMNS)
                ):
                    raise AppError(
                        "CSV 헤더가 올바르지 않습니다. imported=0, skipped=0",
                        "date,type,category,amount 필수 열과 memo,tags 선택 열을 확인하세요.",
                    )
                previous_line = reader.line_num
                while True:
                    try:
                        row = next(reader)
                    except StopIteration:
                        break
                    except csv.Error as exc:
                        raise AppError(
                            f"CSV 구조를 읽을 수 없습니다. imported={imported}, skipped={skipped}",
                            f"{previous_line + 1}행 주변의 따옴표와 구분자를 확인하세요.",
                        ) from exc
                    line_number = previous_line + 1
                    previous_line = reader.line_num
                    try:
                        if None in row:
                            raise AppError("열 개수가 헤더보다 많습니다.", "CSV 열 수와 쉼표를 확인하세요.")
                        transaction = self._new_transaction(
                            row.get("date") or "",
                            row.get("type") or "",
                            row.get("category") or "",
                            row.get("amount") or "",
                            row.get("memo") or "",
                            row.get("tags") or "",
                            known_categories=categories,
                        )
                    except AppError as exc:
                        skipped += 1
                        on_invalid(line_number, exc)
                        continue
                    self.storage.transactions.append(transaction)
                    imported += 1
        except UnicodeError as exc:
            raise AppError(
                f"CSV 인코딩을 읽을 수 없습니다. imported={imported}, skipped={skipped}",
                "파일을 UTF-8 CSV로 저장한 뒤 다시 시도하세요.",
            ) from exc
        return ImportResult(imported=imported, skipped=skipped)

    def export_csv(
        self,
        output_path: Path,
        *,
        month: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> int:
        if month is not None:
            if date_from is not None or date_to is not None:
                raise AppError("월과 기간 조건을 함께 지정할 수 없습니다.", "--month 또는 --from과 --to 중 하나를 선택하세요.")
            month = validate_month(month)
        else:
            if date_from is None or date_to is None:
                raise AppError("내보내기 기간 조건이 부족합니다.", "--month 또는 --from과 --to를 함께 지정하세요.")
            date_from = validate_date(date_from)
            date_to = validate_date(date_to)
            if date_from > date_to:
                raise AppError("시작일이 종료일보다 늦습니다.", "--from과 --to 날짜의 순서를 확인하세요.")
        if output_path.resolve() in self._data_file_paths():
            raise AppError("저장 파일을 CSV 출력 경로로 사용할 수 없습니다.", "별도 CSV 파일 경로를 지정하세요.")
        count = 0
        with output_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(CSV_COLUMNS)
            for _, transaction in self.storage.transactions.iter_transactions():
                if month is not None:
                    selected = transaction.date.startswith(month + "-")
                else:
                    selected = date_from <= transaction.date <= date_to
                if not selected:
                    continue
                writer.writerow(
                    (
                        transaction.date,
                        transaction.type,
                        transaction.category,
                        transaction.amount,
                        transaction.memo,
                        ",".join(transaction.tags),
                    )
                )
                count += 1
        return count

    def _data_file_paths(self) -> set[Path]:
        return {
            self.storage.transactions.path.resolve(),
            self.storage.categories.path.resolve(),
            self.storage.budgets.path.resolve(),
        }
