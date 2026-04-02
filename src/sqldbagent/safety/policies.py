"""Safety policy helpers."""

from __future__ import annotations

from sqldbagent.core.config import SafetySettings
from sqldbagent.core.enums import Dialect

SQLGLOT_DIALECTS: dict[Dialect, str] = {
    Dialect.POSTGRES: "postgres",
    Dialect.MSSQL: "tsql",
    Dialect.SQLITE: "sqlite",
}


def to_sqlglot_dialect(dialect: Dialect) -> str:
    """Return the SQLGlot dialect name for an internal dialect.

    Args:
        dialect: Internal dialect enum.

    Returns:
        str: SQLGlot dialect name.
    """

    return SQLGLOT_DIALECTS[dialect]


def should_apply_row_limit(policy: SafetySettings, has_limit: bool) -> bool:
    """Return whether a row limit should be enforced.

    Args:
        policy: Safety policy settings.
        has_limit: Whether the statement already has a recognized limit.

    Returns:
        bool: True when the guard should inject a limit.
    """

    return policy.max_rows > 0 and not has_limit
