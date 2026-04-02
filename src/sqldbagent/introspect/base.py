"""Introspection protocols."""

from __future__ import annotations

from typing import Protocol

from sqldbagent.core.models.catalog import (
    DatabaseModel,
    SchemaModel,
    ServerModel,
    TableModel,
    ViewModel,
)


class InspectionService(Protocol):
    """Minimal shared inspection contract for initial surfaces."""

    def inspect_server(self) -> ServerModel:
        """Return normalized server metadata."""

    def inspect_database(self, database: str | None = None) -> DatabaseModel:
        """Return normalized database metadata."""

    def inspect_schema(self, schema: str) -> SchemaModel:
        """Return normalized schema metadata."""

    def list_databases(self) -> list[str]:
        """Return database names visible to the datasource."""

    def list_schemas(self, database: str | None = None) -> list[str]:
        """Return schema names for an optional database."""

    def list_tables(self, schema: str | None = None) -> list[str]:
        """Return table names for an optional schema."""

    def list_views(self, schema: str | None = None) -> list[str]:
        """Return view names for an optional schema."""

    def describe_table(self, table_name: str, schema: str | None = None) -> TableModel:
        """Return normalized table metadata."""

    def describe_view(self, view_name: str, schema: str | None = None) -> ViewModel:
        """Return normalized view metadata."""
