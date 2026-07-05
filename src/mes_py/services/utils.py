from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from mes_py.domain.errors import DomainError


def normalize_code(value: str, label: str) -> str:
    text = require_text(value, label).upper()
    if " " in text:
        raise DomainError(f"{label}不可包含空白")
    return text


def require_text(value: str | None, label: str) -> str:
    if value is None or not value.strip():
        raise DomainError(f"請輸入{label}")
    return value.strip()


def optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def positive_decimal(value: str | int | float | Decimal, label: str) -> Decimal:
    parsed = decimal_value(value, label)
    if parsed <= 0:
        raise DomainError(f"{label}必須大於 0")
    return parsed


def non_negative_decimal(value: str | int | float | Decimal, label: str) -> Decimal:
    parsed = decimal_value(value, label)
    if parsed < 0:
        raise DomainError(f"{label}不可小於 0")
    return parsed


def decimal_value(value: str | int | float | Decimal, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value).replace(",", "")).quantize(Decimal("0.001"))
    except (InvalidOperation, ValueError):
        raise DomainError(f"{label}格式不正確") from None
    return parsed


def ensure_time_range(start: datetime | None, end: datetime | None) -> None:
    if start and end and start > end:
        raise DomainError("預計開工時間不可晚於預計完工時間")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

