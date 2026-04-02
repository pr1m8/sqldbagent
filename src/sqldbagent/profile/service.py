"""Generic SQLAlchemy-backed profiling service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Engine, MetaData, Table, func, select, text
from sqlalchemy.sql.sqltypes import JSON, LargeBinary

from sqldbagent.core.config import ProfilingSettings
from sqldbagent.core.models.profile import (
    ColumnProfileModel,
    ColumnUniqueValuesModel,
    TableProfileModel,
)
from sqldbagent.core.serialization import to_jsonable
from sqldbagent.introspect.service import SQLAlchemyInspectionService


class SQLAlchemyProfilingService:
    """Profiling service backed by SQLAlchemy queries."""

    def __init__(
        self,
        engine: Engine,
        inspector: SQLAlchemyInspectionService,
        settings: ProfilingSettings | None = None,
    ) -> None:
        """Initialize the profiling service.

        Args:
            engine: SQLAlchemy engine used for profiling queries.
            inspector: Inspection service used for normalized metadata and relationships.
            settings: Profiling defaults and limits.
        """

        self._engine = engine
        self._inspector = inspector
        self._settings = settings or ProfilingSettings()

    def profile_table(
        self,
        table_name: str,
        schema: str | None = None,
        *,
        sample_size: int = 5,
        top_value_limit: int = 5,
    ) -> TableProfileModel:
        """Build a normalized table profile.

        Args:
            table_name: Table name to profile.
            schema: Optional schema name.
            sample_size: Number of sample rows to include.
            top_value_limit: Number of top values to include per column.

        Returns:
            TableProfileModel: Profile result for the table.
        """

        resolved_sample_size = min(sample_size, self._settings.max_sample_size)
        table_metadata = self._inspector.describe_table(table_name, schema=schema)
        table = self._load_table(table_name=table_name, schema=schema)

        with self._engine.connect() as connection:
            row_count = int(
                connection.execute(select(func.count()).select_from(table)).scalar_one()
            )
            sample_rows = [
                {str(key): to_jsonable(value) for key, value in row.items()}
                for row in connection.execute(
                    select(table).limit(resolved_sample_size)
                ).mappings()
            ]
            column_profiles = [
                self._profile_column(
                    connection=connection,
                    table=table,
                    column=column,
                    row_count=row_count,
                    top_value_limit=top_value_limit,
                )
                for column in table.columns
            ]
            storage_bytes, storage_scope, storage_source = self._storage_stats(
                connection=connection,
                table_name=table_name,
                schema=schema,
            )

        related_tables = sorted(
            {
                self._qualify_name(
                    relationship.referred_schema,
                    relationship.referred_table,
                )
                for relationship in table_metadata.foreign_keys
            }
        )
        entity_kind = self._classify_entity(table_metadata)

        return TableProfileModel(
            database=self._engine.url.database,
            schema_name=schema,
            table_name=table_name,
            row_count=row_count,
            row_count_exact=True,
            storage_bytes=storage_bytes,
            storage_scope=storage_scope,
            storage_source=storage_source,
            entity_kind=entity_kind,
            related_tables=related_tables,
            relationships=table_metadata.foreign_keys,
            relationship_count=len(table_metadata.foreign_keys),
            columns=column_profiles,
            sample_rows=sample_rows,
            summary=self._summarize_table_profile(
                table_name=table_name,
                schema=schema,
                row_count=row_count,
                column_count=len(column_profiles),
                entity_kind=entity_kind,
                relationship_count=len(table_metadata.foreign_keys),
                storage_bytes=storage_bytes,
                storage_scope=storage_scope,
            ),
        )

    def sample_table(
        self,
        table_name: str,
        schema: str | None = None,
        *,
        limit: int = 5,
    ) -> list[dict[str, object | None]]:
        """Return sample rows from a table.

        Args:
            table_name: Table name to sample.
            schema: Optional schema name.
            limit: Maximum number of rows to return.

        Returns:
            list[dict[str, object | None]]: Sample rows.
        """

        resolved_limit = min(limit, self._settings.max_sample_size)
        table = self._load_table(table_name=table_name, schema=schema)
        with self._engine.connect() as connection:
            return [
                {str(key): to_jsonable(value) for key, value in row.items()}
                for row in connection.execute(
                    select(table).limit(resolved_limit)
                ).mappings()
            ]

    def get_unique_values(
        self,
        table_name: str,
        column_name: str,
        schema: str | None = None,
        *,
        limit: int = 20,
    ) -> ColumnUniqueValuesModel:
        """Return distinct values and counts for one column.

        Args:
            table_name: Table name to inspect.
            column_name: Column name whose distinct values should be returned.
            schema: Optional schema name.
            limit: Maximum number of distinct values to return.

        Returns:
            ColumnUniqueValuesModel: Distinct-value distribution for the column.
        """

        resolved_limit = max(1, min(limit, 1_000))
        table = self._load_table(table_name=table_name, schema=schema)
        try:
            column = table.columns[column_name]
        except KeyError as exc:
            raise KeyError(
                f"unknown column '{column_name}' on table '{self._qualify_name(schema, table_name)}'"
            ) from exc

        with self._engine.connect() as connection:
            row_count = int(
                connection.execute(select(func.count()).select_from(table)).scalar_one()
            )
            null_count = int(
                connection.execute(
                    select(func.count()).select_from(table).where(column.is_(None))
                ).scalar_one()
            )
            non_null_count = max(row_count - null_count, 0)
            unique_value_count = int(
                connection.execute(
                    select(func.count(func.distinct(column)))
                    .select_from(table)
                    .where(column.is_not(None))
                ).scalar_one()
            )
            values = self._top_values(
                connection=connection,
                table=table,
                column=column,
                top_value_limit=resolved_limit,
                include_nulls=False,
            )

        return ColumnUniqueValuesModel(
            database=self._engine.url.database,
            schema_name=schema,
            table_name=table_name,
            column_name=column_name,
            row_count=row_count,
            null_count=null_count,
            non_null_count=non_null_count,
            unique_value_count=unique_value_count,
            values=values,
            truncated=unique_value_count > resolved_limit,
            summary=self._summarize_unique_values(
                table_name=table_name,
                column_name=column_name,
                schema=schema,
                unique_value_count=unique_value_count,
                null_count=null_count,
                returned_count=len(values),
                truncated=unique_value_count > resolved_limit,
            ),
        )

    def _profile_column(
        self,
        *,
        connection: Any,
        table: Table,
        column: Any,
        row_count: int,
        top_value_limit: int,
    ) -> ColumnProfileModel:
        """Profile one reflected column.

        Args:
            connection: Active SQLAlchemy connection.
            table: Reflected table.
            column: SQLAlchemy column object.
            row_count: Exact table row count.
            top_value_limit: Number of top values to include.

        Returns:
            ColumnProfileModel: Per-column profile.
        """

        null_count = int(
            connection.execute(
                select(func.count()).select_from(table).where(column.is_(None))
            ).scalar_one()
        )
        non_null_count = max(row_count - null_count, 0)
        unique_value_count = None
        if self._settings.exact_unique_counts:
            unique_value_count = int(
                connection.execute(
                    select(func.count(func.distinct(column))).select_from(table)
                ).scalar_one()
            )

        min_value = self._aggregate_extreme_value(
            connection=connection,
            table=table,
            column=column,
            aggregate="min",
        )
        max_value = self._aggregate_extreme_value(
            connection=connection,
            table=table,
            column=column,
            aggregate="max",
        )

        return ColumnProfileModel(
            name=column.name,
            data_type=str(column.type),
            null_count=null_count,
            non_null_count=non_null_count,
            null_ratio=None if row_count == 0 else round(null_count / row_count, 6),
            unique_value_count=unique_value_count,
            unique_ratio=(
                None
                if row_count == 0 or unique_value_count is None
                else round(unique_value_count / row_count, 6)
            ),
            min_value=min_value,
            max_value=max_value,
            sample_values=self._sample_values(
                connection=connection,
                table=table,
                column=column,
            ),
            top_values=self._top_values(
                connection=connection,
                table=table,
                column=column,
                top_value_limit=top_value_limit,
            ),
            summary=self._summarize_column_profile(
                column_name=column.name,
                null_count=null_count,
                row_count=row_count,
                unique_value_count=unique_value_count,
            ),
        )

    def _sample_values(
        self,
        *,
        connection: Any,
        table: Table,
        column: Any,
    ) -> list[object]:
        """Return distinct sample values for one column.

        Args:
            connection: Active SQLAlchemy connection.
            table: Reflected table.
            column: SQLAlchemy column object.

        Returns:
            list[object]: JSON-friendly sample values.
        """

        statement = (
            select(column)
            .select_from(table)
            .where(column.is_not(None))
            .distinct()
            .limit(min(3, self._settings.default_sample_size))
        )
        return [
            self._scalar_value(value)
            for value in connection.execute(statement).scalars().all()
        ]

    def _top_values(
        self,
        *,
        connection: Any,
        table: Table,
        column: Any,
        top_value_limit: int,
        include_nulls: bool = True,
    ) -> list[dict[str, object]]:
        """Return top values and counts for one column.

        Args:
            connection: Active SQLAlchemy connection.
            table: Reflected table.
            column: SQLAlchemy column object.
            top_value_limit: Number of top values to include.
            include_nulls: Whether null values should be returned.

        Returns:
            list[dict[str, object]]: JSON-friendly top value payloads.
        """

        statement = (
            select(column.label("value"), func.count().label("count"))
            .select_from(table)
            .group_by(column)
            .order_by(func.count().desc())
            .limit(top_value_limit)
        )
        if not include_nulls:
            statement = statement.where(column.is_not(None))
        return [
            {
                "value": self._scalar_value(row.value),
                "count": int(row.count),
            }
            for row in connection.execute(statement)
        ]

    def _load_table(self, table_name: str, schema: str | None) -> Table:
        """Load a reflected SQLAlchemy table.

        Args:
            table_name: Table name to load.
            schema: Optional schema name.

        Returns:
            Table: Reflected SQLAlchemy table object.
        """

        metadata = MetaData()
        return Table(table_name, metadata, schema=schema, autoload_with=self._engine)

    def _aggregate_extreme_value(
        self,
        *,
        connection: Any,
        table: Table,
        column: Any,
        aggregate: str,
    ) -> object | None:
        """Return a best-effort minimum or maximum value for one column.

        Args:
            connection: Active SQLAlchemy connection.
            table: Reflected SQLAlchemy table.
            column: SQLAlchemy column object.
            aggregate: Either `"min"` or `"max"`.

        Returns:
            object | None: JSON-friendly extreme value when supported.
        """

        if not self._supports_extreme_aggregates(column):
            return None

        aggregate_fn = func.min if aggregate == "min" else func.max
        value = connection.execute(
            select(aggregate_fn(column)).select_from(table)
        ).scalar_one()
        return self._scalar_value(value)

    def _supports_extreme_aggregates(self, column: Any) -> bool:
        """Return whether a column should use `min` and `max` aggregation.

        Args:
            column: SQLAlchemy column object.

        Returns:
            bool: Whether `min` and `max` are a safe default for this column.
        """

        column_type = column.type
        return not isinstance(column_type, (Boolean, JSON, LargeBinary))

    def _storage_stats(
        self,
        *,
        connection: Any,
        table_name: str,
        schema: str | None,
    ) -> tuple[int | None, str | None, str | None]:
        """Return best-effort storage metadata for one relation.

        Args:
            connection: Active SQLAlchemy connection.
            table_name: Table name.
            schema: Optional schema name.

        Returns:
            tuple[int | None, str | None, str | None]:
                Storage bytes, storage scope, and storage source.
        """

        if self._engine.url.drivername.startswith("postgresql"):
            relation_name = self._quoted_relation_name(schema=schema, name=table_name)
            storage_bytes = connection.execute(
                text("SELECT pg_total_relation_size(to_regclass(:relation_name))"),
                {"relation_name": relation_name},
            ).scalar_one()
            if storage_bytes is None:
                return None, None, None
            return int(storage_bytes), "table_and_indexes", "pg_total_relation_size"

        if not self._engine.url.drivername.startswith("sqlite"):
            return None, None, None

        database_path = self._engine.url.database
        if not database_path or database_path == ":memory:":
            return None, None, None

        path = Path(database_path)
        if not path.exists():
            return None, None, None

        return path.stat().st_size, "database", "sqlite_file_size"

    def _classify_entity(self, table_metadata: Any) -> str:
        """Classify a table into a coarse entity kind.

        Args:
            table_metadata: Normalized table metadata.

        Returns:
            str: Entity kind heuristic.
        """

        foreign_key_count = len(table_metadata.foreign_keys)
        column_count = len(table_metadata.columns)
        primary_key_count = len(table_metadata.primary_key)

        if (
            foreign_key_count >= 2
            and column_count <= foreign_key_count + primary_key_count + 2
        ):
            return "association"
        if foreign_key_count > 0:
            return "child_entity"
        if primary_key_count > 0:
            return "entity"
        return "relation"

    def _summarize_column_profile(
        self,
        *,
        column_name: str,
        null_count: int,
        row_count: int,
        unique_value_count: int | None,
    ) -> str:
        """Build a short human-readable summary for one column profile.

        Args:
            column_name: Column name.
            null_count: Exact null count.
            row_count: Exact table row count.
            unique_value_count: Exact unique count when available.

        Returns:
            str: Short summary text.
        """

        unique_text = (
            f"{unique_value_count} distinct values"
            if unique_value_count is not None
            else "distinct count skipped"
        )
        return (
            f"Column '{column_name}' has {null_count} nulls across {row_count} rows and "
            f"{unique_text}."
        )

    def _summarize_table_profile(
        self,
        *,
        table_name: str,
        schema: str | None,
        row_count: int,
        column_count: int,
        entity_kind: str,
        relationship_count: int,
        storage_bytes: int | None,
        storage_scope: str | None,
    ) -> str:
        """Build a short human-readable summary for one table profile.

        Args:
            table_name: Table name.
            schema: Optional schema name.
            row_count: Exact row count.
            column_count: Number of profiled columns.
            entity_kind: Heuristic entity kind.
            relationship_count: Number of foreign-key relationships.
            storage_bytes: Best-effort storage bytes.
            storage_scope: Scope represented by `storage_bytes`.

        Returns:
            str: Short summary text.
        """

        qualified_name = self._qualify_name(schema, table_name)
        storage_text = (
            f"{storage_bytes} bytes of {storage_scope} storage"
            if storage_bytes is not None and storage_scope is not None
            else "no storage estimate"
        )
        return (
            f"Profile for '{qualified_name}' shows {row_count} rows, {column_count} "
            f"columns, entity kind '{entity_kind}', {relationship_count} relationships, "
            f"and {storage_text}."
        )

    def _summarize_unique_values(
        self,
        *,
        table_name: str,
        column_name: str,
        schema: str | None,
        unique_value_count: int,
        null_count: int,
        returned_count: int,
        truncated: bool,
    ) -> str:
        """Build a short summary for a distinct-value result.

        Args:
            table_name: Table name containing the column.
            column_name: Column name being summarized.
            schema: Optional schema name.
            unique_value_count: Exact number of distinct non-null values.
            null_count: Exact null count.
            returned_count: Number of values returned in the payload.
            truncated: Whether the result set was capped.

        Returns:
            str: Human-readable summary.
        """

        qualified_name = self._qualify_name(schema, table_name)
        truncation_text = (
            f" Returning the top {returned_count} values by frequency."
            if truncated
            else f" Returning all {returned_count} captured values."
        )
        return (
            f"Column '{qualified_name}.{column_name}' has {unique_value_count} distinct "
            f"non-null values and {null_count} nulls.{truncation_text}"
        )

    def _scalar_value(self, value: object) -> object:
        """Normalize a scalar value into a JSON-friendly shape.

        Args:
            value: Raw Python value.

        Returns:
            object: JSON-friendly value.
        """

        return to_jsonable(value)

    def _qualify_name(self, schema: str | None, name: str) -> str:
        """Return a schema-qualified name when a schema is present.

        Args:
            schema: Optional schema name.
            name: Unqualified object name.

        Returns:
            str: Qualified name.
        """

        if schema:
            return f"{schema}.{name}"
        return name

    def _quoted_relation_name(self, *, schema: str | None, name: str) -> str:
        """Return a quoted relation name for relation-size helpers.

        Args:
            schema: Optional schema name.
            name: Unqualified relation name.

        Returns:
            str: Quoted relation name safe for helpers such as `to_regclass`.
        """

        preparer = self._engine.dialect.identifier_preparer
        if schema:
            return (
                f"{preparer.quote_identifier(schema)}."
                f"{preparer.quote_identifier(name)}"
            )
        return preparer.quote_identifier(name)
