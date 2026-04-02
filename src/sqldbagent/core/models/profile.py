"""Normalized profiling models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sqldbagent.core.models.catalog import ForeignKeyModel


class ColumnProfileModel(BaseModel):
    """Normalized column profile.

    Attributes:
        name: Column name.
        data_type: Reflected column data type.
        null_count: Exact null count when available.
        non_null_count: Exact non-null count when available.
        null_ratio: Null ratio when row count is available.
        unique_value_count: Exact unique count when available.
        unique_ratio: Ratio of unique non-null values to total rows when available.
        min_value: Best-effort minimum value.
        max_value: Best-effort maximum value.
        sample_values: Best-effort sample values for the column.
        top_values: Most frequent values and counts.
        summary: Generated short summary.
    """

    name: str
    data_type: str
    null_count: int | None = None
    non_null_count: int | None = None
    null_ratio: float | None = None
    unique_value_count: int | None = None
    unique_ratio: float | None = None
    min_value: object | None = None
    max_value: object | None = None
    sample_values: list[object] = Field(default_factory=list)
    top_values: list[dict[str, object]] = Field(default_factory=list)
    summary: str | None = None


class TableProfileModel(BaseModel):
    """Normalized cheap table profile.

    Attributes:
        database: Optional database name containing the table.
        schema_name: Optional schema name containing the table.
        table_name: Table name.
        row_count: Exact row count when available.
        row_count_exact: Whether the row count is exact.
        storage_bytes: Best-effort storage bytes when available.
        storage_scope: Scope represented by `storage_bytes`.
        storage_source: How storage bytes were obtained.
        entity_kind: Heuristic entity classification for the table.
        related_tables: Related tables inferred from foreign keys.
        relationships: Relationships inferred from foreign keys.
        relationship_count: Number of inferred relationships.
        columns: Per-column profile summaries.
        sample_rows: Sample rows from the table.
        summary: Generated short summary.
    """

    database: str | None = None
    schema_name: str | None = None
    table_name: str
    row_count: int | None = None
    row_count_exact: bool = False
    storage_bytes: int | None = None
    storage_scope: str | None = None
    storage_source: str | None = None
    entity_kind: str | None = None
    related_tables: list[str] = Field(default_factory=list)
    relationships: list[ForeignKeyModel] = Field(default_factory=list)
    relationship_count: int = 0
    columns: list[ColumnProfileModel] = Field(default_factory=list)
    sample_rows: list[dict[str, object | None]] = Field(default_factory=list)
    summary: str | None = None
