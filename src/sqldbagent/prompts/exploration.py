"""Live read-only exploration helpers for prompt enhancement."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Protocol

from sqldbagent.core.models.catalog import TableModel
from sqldbagent.core.models.profile import ColumnProfileModel, ColumnUniqueValuesModel
from sqldbagent.prompts.models import PromptExplorationModel
from sqldbagent.prompts.tokens import estimate_text_tokens
from sqldbagent.snapshot.models import SnapshotBundleModel

_MAX_TABLES = 6
_MAX_CATEGORICAL_COLUMNS = 3
_COLUMN_NAME_PRIORITY_TOKENS = (
    "status",
    "segment",
    "category",
    "priority",
    "tier",
    "country",
    "state",
    "type",
    "region",
)
_BOOLEAN_DATA_TYPE_TOKENS = ("bool",)
_SKIP_DATA_TYPE_TOKENS = ("json", "blob", "binary")


class SupportsPromptExplorationProfiling(Protocol):
    """Profiling interface required for live prompt exploration."""

    def get_unique_values(
        self,
        table_name: str,
        column_name: str,
        schema: str | None = None,
        *,
        limit: int = 20,
    ) -> ColumnUniqueValuesModel:
        """Return distinct values for a table column."""


class PromptExplorationService:
    """Build concise prompt-ready context from live read-only exploration."""

    def create_exploration(
        self,
        snapshot: SnapshotBundleModel,
        *,
        profiler: SupportsPromptExplorationProfiling,
        table_names: Iterable[str] | None = None,
        max_tables: int = 4,
        unique_value_limit: int = 8,
    ) -> PromptExplorationModel:
        """Create one live exploration block for a stored schema snapshot.

        Args:
            snapshot: Stored snapshot used as the schema baseline.
            profiler: Read-only profiling service used for distinct-value lookups.
            table_names: Optional explicit table focus list.
            max_tables: Maximum number of tables to explore.
            unique_value_limit: Maximum number of distinct values per column.

        Returns:
            PromptExplorationModel: Prompt-ready exploration artifact.
        """

        resolved_max_tables = max(1, min(max_tables, _MAX_TABLES))
        schema_name = snapshot.regenerate.schema_name
        table_lookup = {
            _qualify_name(table.schema_name, table.name): table
            for table in snapshot.schema_metadata.tables
        }
        profile_lookup = {
            _qualify_name(profile.schema_name, profile.table_name): profile
            for profile in snapshot.profiles
        }
        focus_names = self._resolve_focus_tables(
            snapshot=snapshot,
            table_lookup=table_lookup,
            profile_lookup=profile_lookup,
            table_names=table_names,
            max_tables=resolved_max_tables,
        )

        table_sections: list[str] = []
        explored_tables: list[str] = []
        for qualified_name in focus_names:
            table = table_lookup.get(qualified_name)
            if table is None:
                continue
            explored_tables.append(qualified_name)
            profile = profile_lookup.get(qualified_name)
            categorical_lines = self._build_categorical_lines(
                table=table,
                profile_columns=[] if profile is None else profile.columns,
                profiler=profiler,
                schema_name=schema_name,
                unique_value_limit=unique_value_limit,
            )
            table_sections.extend(
                self._build_table_section(
                    qualified_name=qualified_name,
                    table=table,
                    profile=profile,
                    categorical_lines=categorical_lines,
                )
            )

        if not table_sections:
            table_sections.append(
                "- No eligible tables were available for live prompt exploration."
            )

        context = "\n".join(
            [
                (
                    "Live read-only exploration was generated from the active "
                    "datasource to supplement the stored snapshot with high-signal "
                    "filter values, identifiers, and access-path hints."
                ),
                "Explored table context:",
                *table_sections,
            ]
        )
        token_estimates = estimate_text_tokens(context)
        token_estimates["character_count"] = len(context)
        summary = (
            f"Explored {len(explored_tables)} table(s) for datasource "
            f"'{snapshot.datasource_name}' schema '{schema_name}'."
        )
        return PromptExplorationModel(
            datasource_name=snapshot.datasource_name,
            schema_name=schema_name,
            snapshot_id=snapshot.snapshot_id,
            generated_at=datetime.now(UTC),
            focus_tables=explored_tables,
            summary=summary,
            context=context,
            token_estimates=token_estimates,
        )

    def _resolve_focus_tables(
        self,
        *,
        snapshot: SnapshotBundleModel,
        table_lookup: dict[str, TableModel],
        profile_lookup: dict[str, object],
        table_names: Iterable[str] | None,
        max_tables: int,
    ) -> list[str]:
        """Resolve the table list used for prompt exploration."""

        requested = [
            _normalize_requested_table_name(
                table_name=name,
                schema_name=snapshot.regenerate.schema_name,
            )
            for name in ([] if table_names is None else list(table_names))
        ]
        explicit = [name for name in requested if name in table_lookup]
        if explicit:
            return explicit[:max_tables]

        scored: list[tuple[tuple[int, int, int, int], str]] = []
        for qualified_name, table in table_lookup.items():
            profile = profile_lookup.get(qualified_name)
            row_count = (
                0 if profile is None else int(getattr(profile, "row_count", 0) or 0)
            )
            relationship_count = (
                0
                if profile is None
                else int(getattr(profile, "relationship_count", 0) or 0)
            )
            storage_bytes = (
                0 if profile is None else int(getattr(profile, "storage_bytes", 0) or 0)
            )
            score = (
                relationship_count,
                storage_bytes,
                row_count,
                len(table.columns),
            )
            scored.append((score, qualified_name))
        scored.sort(reverse=True)
        return [name for _, name in scored[:max_tables]]

    def _build_table_section(
        self,
        *,
        qualified_name: str,
        table: TableModel,
        profile: object | None,
        categorical_lines: list[str],
    ) -> list[str]:
        """Build prompt lines for one explored table."""

        parts = [qualified_name]
        row_count = None if profile is None else getattr(profile, "row_count", None)
        if row_count is not None:
            parts.append(f"rows={row_count}")
        entity_kind = None if profile is None else getattr(profile, "entity_kind", None)
        if entity_kind:
            parts.append(f"role={entity_kind}")
        storage_bytes = (
            None if profile is None else getattr(profile, "storage_bytes", None)
        )
        if storage_bytes is not None:
            parts.append(f"storage_bytes={storage_bytes}")
        if table.primary_key:
            parts.append(f"pk={', '.join(table.primary_key)}")
        business_keys = [
            ", ".join(constraint.columns)
            for constraint in table.unique_constraints
            if constraint.columns
        ]
        if business_keys:
            parts.append(f"business_keys={'; '.join(business_keys[:2])}")
        indexed_columns = [
            ", ".join(index.columns) for index in table.indexes if index.columns
        ]
        if indexed_columns:
            parts.append(f"indexes={'; '.join(indexed_columns[:2])}")

        lines = [f"- {'; '.join(parts)}"]
        relationship_lines = [
            _format_relationship_hint(
                table_name=qualified_name, foreign_key=foreign_key
            )
            for foreign_key in table.foreign_keys
        ]
        if relationship_lines:
            lines.extend(f"  - {line}" for line in relationship_lines[:2])
        if categorical_lines:
            lines.extend(f"  - {line}" for line in categorical_lines)
        return lines

    def _build_categorical_lines(
        self,
        *,
        table: TableModel,
        profile_columns: Iterable[ColumnProfileModel],
        profiler: SupportsPromptExplorationProfiling,
        schema_name: str,
        unique_value_limit: int,
    ) -> list[str]:
        """Build filter-friendly distinct-value lines for one table."""

        profile_lookup = {column.name: column for column in profile_columns}
        candidates = [
            column
            for column in table.columns
            if self._is_categorical_candidate(profile_lookup.get(column.name))
        ]
        candidates.sort(
            key=lambda column: self._categorical_sort_key(
                profile_lookup.get(column.name),
            )
        )
        lines: list[str] = []
        for column in candidates[:_MAX_CATEGORICAL_COLUMNS]:
            unique_values = profiler.get_unique_values(
                table_name=table.name,
                column_name=column.name,
                schema=schema_name,
                limit=unique_value_limit,
            )
            formatted_values = _format_unique_values(unique_values)
            if formatted_values is None:
                continue
            lines.append(f"filters.{column.name}={formatted_values}")
        return lines

    def _is_categorical_candidate(
        self,
        profile: ColumnProfileModel | None,
    ) -> bool:
        """Return whether a profiled column is worth exploring for prompts."""

        if profile is None:
            return False
        data_type = profile.data_type.lower()
        if any(token in data_type for token in _SKIP_DATA_TYPE_TOKENS):
            return False
        unique_count = profile.unique_value_count
        if unique_count is None or unique_count < 2:
            return any(token in data_type for token in _BOOLEAN_DATA_TYPE_TOKENS)
        if unique_count > 12:
            return False
        if profile.unique_ratio is not None and profile.unique_ratio >= 0.85:
            return False
        return True

    def _categorical_sort_key(
        self,
        profile: ColumnProfileModel | None,
    ) -> tuple[int, int, str]:
        """Return a stable sort key for candidate categorical columns."""

        if profile is None:
            return (10, 10, "")
        name = profile.name.lower()
        name_priority = (
            0 if any(token in name for token in _COLUMN_NAME_PRIORITY_TOKENS) else 1
        )
        unique_count = int(profile.unique_value_count or 99)
        return (name_priority, unique_count, name)


def _normalize_requested_table_name(*, table_name: str, schema_name: str) -> str:
    """Normalize a user-supplied table name into qualified form."""

    normalized = table_name.strip()
    if "." in normalized:
        return normalized
    return f"{schema_name}.{normalized}"


def _qualify_name(schema_name: str | None, table_name: str) -> str:
    """Return a schema-qualified table name."""

    if schema_name:
        return f"{schema_name}.{table_name}"
    return table_name


def _format_relationship_hint(*, table_name: str, foreign_key: object) -> str:
    """Format one relationship hint line for prompt exploration."""

    target_schema = getattr(foreign_key, "referred_schema", None)
    target_table = getattr(foreign_key, "referred_table", "")
    target_columns = ", ".join(getattr(foreign_key, "referred_columns", []) or [])
    source_columns = ", ".join(getattr(foreign_key, "columns", []) or [])
    return (
        f"join_path={table_name}.{source_columns} -> "
        f"{_qualify_name(target_schema, target_table)}.{target_columns}"
    )


def _format_unique_values(values: ColumnUniqueValuesModel) -> str | None:
    """Format one distinct-value payload into a concise inline summary."""

    if not values.values:
        return None
    rendered = []
    for entry in values.values:
        rendered.append(f"{entry.get('value')}({entry.get('count')})")
    suffix = " +" if values.truncated else ""
    return "[" + ", ".join(rendered) + f"]{suffix}"
