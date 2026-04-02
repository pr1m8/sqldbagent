"""Helpers for normalizing values into JSON-friendly structures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

JsonScalar = str | int | float | bool | None


def to_jsonable(
    value: object,
    *,
    max_string_length: int = 200,
) -> JsonScalar | list[object] | dict[str, object]:
    """Convert a Python value into a JSON-friendly shape.

    Args:
        value: Raw Python value.
        max_string_length: Maximum string length before truncation.

    Returns:
        JsonScalar | list[object] | dict[str, object]: JSON-friendly value.
    """

    if value is None or isinstance(value, bool | int | float):
        return value

    if isinstance(value, str):
        if len(value) <= max_string_length:
            return value
        return f"{value[: max_string_length - 3]}..."

    if isinstance(value, bytes):
        return value.hex()

    if isinstance(value, datetime | date | time | Decimal | UUID | Path):
        return str(value)

    if isinstance(value, Mapping):
        return {
            str(key): to_jsonable(item, max_string_length=max_string_length)
            for key, item in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [
            to_jsonable(item, max_string_length=max_string_length) for item in value
        ]

    return str(value)
