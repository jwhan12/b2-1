"""CLI, CSV, 저장 파일에 공통으로 적용하는 입력 검증."""

import re
from datetime import date

from .errors import AppError


_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_MONTH_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}\Z")
_AMOUNT_PATTERN = re.compile(r"[0-9]+\Z")
VALID_TYPES = {"income", "expense"}


def validate_date(value: str) -> str:
    if not isinstance(value, str) or not _DATE_PATTERN.fullmatch(value):
        raise AppError("날짜 형식이 올바르지 않습니다.", "YYYY-MM-DD 형식으로 입력하세요. 예: 2024-01-15")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise AppError("존재하지 않는 날짜입니다.", "실제 달력에 있는 날짜를 입력하세요.") from exc
    return value


def validate_month(value: str) -> str:
    if not isinstance(value, str) or not _MONTH_PATTERN.fullmatch(value):
        raise AppError("월 형식이 올바르지 않습니다.", "YYYY-MM 형식으로 입력하세요. 예: 2024-01")
    try:
        date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise AppError("존재하지 않는 월입니다.", "01부터 12까지의 월을 입력하세요.") from exc
    return value


def validate_amount(value: str | int) -> int:
    if type(value) is int:
        amount = value
    elif isinstance(value, str) and _AMOUNT_PATTERN.fullmatch(value):
        amount = int(value)
    else:
        raise AppError("금액은 양수 정수여야 합니다.", "0보다 큰 정수를 입력하세요. 예: 15000")
    if amount <= 0:
        raise AppError("금액은 0보다 커야 합니다.", "0보다 큰 정수를 입력하세요. 예: 15000")
    return amount


def validate_type(value: str) -> str:
    if value not in VALID_TYPES:
        raise AppError("허용되지 않은 거래 타입입니다.", "income 또는 expense를 입력하세요.")
    return value


def validate_category_name(value: str) -> str:
    if not isinstance(value, str):
        raise AppError("카테고리 이름이 올바르지 않습니다.", "비어 있지 않은 이름을 입력하세요.")
    name = value.strip()
    if not name:
        raise AppError("카테고리 이름이 비어 있습니다.", "비어 있지 않은 이름을 입력하세요.")
    if "\n" in name or "\r" in name:
        raise AppError("카테고리 이름에 줄바꿈이 있습니다.", "한 줄로 된 이름을 입력하세요.")
    return name


def parse_tags(value: str) -> list[str]:
    if not isinstance(value, str):
        raise AppError("태그 형식이 올바르지 않습니다.", "태그를 쉼표로 구분해 입력하세요.")
    return [tag for part in value.split(",") if (tag := part.strip())]

