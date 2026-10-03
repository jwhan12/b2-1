"""가계부의 데이터 계약."""

from dataclasses import asdict, dataclass
from typing import Any

from .errors import AppError
from .validators import validate_amount, validate_category_name, validate_date, validate_type


@dataclass(frozen=True)
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str
    tags: list[str]

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "Transaction":
        try:
            identifier = record["id"]
            transaction_type = record["type"]
            transaction_date = record["date"]
            amount = record["amount"]
            category = record["category"]
            memo = record["memo"]
            tags = record["tags"]
            if not isinstance(identifier, str) or not identifier:
                raise ValueError("id")
            if type(amount) is not int or not isinstance(memo, str) or not isinstance(tags, list):
                raise ValueError("memo/tags")
            if any(not isinstance(tag, str) for tag in tags):
                raise ValueError("tags")
            return cls(
                id=identifier,
                type=validate_type(transaction_type),
                date=validate_date(transaction_date),
                amount=validate_amount(amount),
                category=validate_category_name(category),
                memo=memo,
                tags=tags,
            )
        except (KeyError, TypeError, ValueError, AppError) as exc:
            raise AppError("저장된 거래 형식이 올바르지 않습니다.", "transactions.jsonl의 해당 행을 확인하세요.") from exc

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: int


@dataclass(frozen=True)
class MonthSummary:
    count: int
    income: int
    expense: int
    category_expenses: list[tuple[str, int]]
    budget: int | None

    @property
    def balance(self) -> int:
        return self.income - self.expense
