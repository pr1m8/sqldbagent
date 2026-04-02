"""Safety models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryGuardResult(BaseModel):
    """Guard evaluation result.

    Attributes:
        allowed: Whether the query passed safety validation.
        statement_type: Root SQL statement type.
        dialect: SQL dialect used for parsing and normalization.
        original_sql: Original SQL text.
        normalized_sql: Normalized SQL text after linting or guarding.
        row_limit_applied: Whether the guard injected or reduced a row limit.
        max_rows: Maximum rows allowed by policy.
        referenced_schemas: Schemas referenced by the statement.
        referenced_tables: Tables referenced by the statement.
        reasons: Validation failure reasons when not allowed.
        summary: Generated short summary.
    """

    allowed: bool
    statement_type: str | None = None
    dialect: str
    original_sql: str
    normalized_sql: str | None = None
    row_limit_applied: bool = False
    max_rows: int | None = None
    referenced_schemas: list[str] = Field(default_factory=list)
    referenced_tables: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    summary: str | None = None
