"""사용자에게 보여 줄 오류와 해결 방법."""

from dataclasses import dataclass


@dataclass
class AppError(Exception):
    message: str
    hint: str

    def __str__(self) -> str:
        return self.message

