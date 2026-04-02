"""Normalized query execution models."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from sqldbagent.safety.models import QueryGuardResult


class QueryExecutionResult(BaseModel):
    """Guarded query execution result.

    Attributes:
        mode: Execution mode used by the service.
        executed_at: Query execution timestamp.
        guard: Guard evaluation result for the submitted SQL.
        columns: Result column names.
        rows: JSON-friendly result rows.
        row_count: Number of rows returned.
        rows_affected: Number of rows affected for writable statements when
            returned by the database driver.
        truncated: Whether the result was truncated by policy.
        duration_ms: Execution duration in milliseconds.
        summary: Generated short summary.
    """

    mode: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    guard: QueryGuardResult
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, object | None]] = Field(default_factory=list)
    row_count: int = 0
    rows_affected: int | None = None
    truncated: bool = False
    duration_ms: float | None = None
    summary: str | None = None
