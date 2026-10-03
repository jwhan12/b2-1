"""JSONL 저장소. 거래는 한 행씩 읽으며 수정·삭제는 전체 재작성한다."""

import json
import shutil
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, TextIO

from .errors import AppError
from .models import Transaction
from .validators import validate_amount, validate_category_name, validate_month


DEFAULT_CATEGORIES = ("food", "transport", "rent", "salary", "etc")


def _iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AppError(
                    f"{path.name} {line_number}행의 JSONL 형식이 올바르지 않습니다.",
                    f"{path} 파일의 해당 행을 확인하세요.",
                ) from exc
            if not isinstance(value, dict):
                raise AppError(
                    f"{path.name} {line_number}행은 JSON 객체여야 합니다.",
                    f"{path} 파일의 해당 행을 확인하세요.",
                )
            yield line_number, value


def _write_record(destination: TextIO, record: dict[str, Any]) -> None:
    destination.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


class TransactionRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def iter_transactions(self) -> Iterator[tuple[int, Transaction]]:
        for line_number, record in _iter_jsonl(self.path):
            try:
                yield line_number, Transaction.from_record(record)
            except AppError as exc:
                raise AppError(
                    f"{self.path.name} {line_number}행의 거래 데이터가 올바르지 않습니다.",
                    f"{self.path} 파일의 해당 행을 확인하세요. ({exc.message})",
                ) from exc

    def append(self, transaction: Transaction) -> None:
        with self.path.open("a", encoding="utf-8", newline="\n") as destination:
            _write_record(destination, transaction.to_record())

    def rewrite_one(
        self, identifier: str, transform: Callable[[Transaction], Transaction | None]
    ) -> None:
        found = False
        # 작업 스트림은 검증 중 원본을 건드리지 않기 위한 것이며 원자적 교체나 백업이 아니다.
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", newline="\n") as staged:
            for _, transaction in self.iter_transactions():
                if transaction.id == identifier:
                    if found:
                        raise AppError("중복된 거래 ID가 저장되어 있습니다.", "거래 파일의 ID를 확인하세요.")
                    found = True
                    transaction = transform(transaction)
                if transaction is not None:
                    _write_record(staged, transaction.to_record())
            if not found:
                raise AppError("해당 ID의 거래가 없습니다.", "list 또는 search로 ID를 확인하세요.")
            staged.seek(0)
            with self.path.open("w", encoding="utf-8", newline="\n") as destination:
                shutil.copyfileobj(staged, destination)


class CategoryRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def list_names(self) -> list[str]:
        names: list[str] = []
        for line_number, record in _iter_jsonl(self.path):
            if set(record) != {"name"}:
                raise AppError(
                    f"{self.path.name} {line_number}행의 카테고리 형식이 올바르지 않습니다.",
                    "name 속성을 가진 JSON 객체로 저장하세요.",
                )
            try:
                names.append(validate_category_name(record["name"]))
            except AppError as exc:
                raise AppError(
                    f"{self.path.name} {line_number}행의 카테고리가 올바르지 않습니다.",
                    f"해당 행을 확인하세요. ({exc.message})",
                ) from exc
        if len(names) != len(set(names)):
            raise AppError("중복된 카테고리가 저장되어 있습니다.", "categories.jsonl의 중복 행을 확인하세요.")
        return names

    def save_names(self, names: list[str]) -> None:
        with self.path.open("w", encoding="utf-8", newline="\n") as destination:
            for name in names:
                _write_record(destination, {"name": name})


class BudgetRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def list_budgets(self) -> dict[str, int]:
        budgets: dict[str, int] = {}
        for line_number, record in _iter_jsonl(self.path):
            if set(record) != {"month", "amount"}:
                raise AppError(
                    f"{self.path.name} {line_number}행의 예산 형식이 올바르지 않습니다.",
                    "month와 amount 속성을 가진 JSON 객체로 저장하세요.",
                )
            try:
                month = validate_month(record["month"])
                amount = validate_amount(record["amount"])
            except AppError as exc:
                raise AppError(
                    f"{self.path.name} {line_number}행의 예산이 올바르지 않습니다.",
                    f"해당 행을 확인하세요. ({exc.message})",
                ) from exc
            if month in budgets:
                raise AppError("중복된 월 예산이 저장되어 있습니다.", "budgets.jsonl의 중복 월을 확인하세요.")
            budgets[month] = amount
        return budgets

    def save_budgets(self, budgets: dict[str, int]) -> None:
        with self.path.open("w", encoding="utf-8", newline="\n") as destination:
            for month in sorted(budgets):
                _write_record(destination, {"month": month, "amount": budgets[month]})


class Storage:
    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir
        for filename in ("transactions.jsonl", "categories.jsonl", "budgets.jsonl"):
            (data_dir / filename).touch(exist_ok=True)
        self.transactions = TransactionRepository(data_dir / "transactions.jsonl")
        self.categories = CategoryRepository(data_dir / "categories.jsonl")
        self.budgets = BudgetRepository(data_dir / "budgets.jsonl")
        if (data_dir / "categories.jsonl").stat().st_size == 0:
            self.categories.save_names(list(DEFAULT_CATEGORIES))
