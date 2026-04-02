"""Prompt-enhancement helpers built on top of stored snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import orjson

from sqldbagent.core.config import ArtifactSettings
from sqldbagent.core.models.catalog import TableModel
from sqldbagent.core.models.profile import ColumnProfileModel, TableProfileModel
from sqldbagent.prompts.models import (
    PromptEnhancementModel,
    PromptExplorationModel,
)
from sqldbagent.prompts.tokens import estimate_prompt_enhancement_tokens
from sqldbagent.snapshot.models import SnapshotBundleModel

_GENERATED_CONTEXT_VERSION = 3
_MAX_FOCUS_TABLES = 6
_MAX_IDENTIFIER_HINTS = 8
_MAX_INDEX_HINTS = 8
_MAX_RELATIONSHIP_HINTS = 8
_MAX_VIEW_HINTS = 5
_MAX_CATEGORY_HINTS = 8
_MAX_NULLABILITY_HINTS = 6


class PromptEnhancementService:
    """Persist prompt enhancements derived from stored snapshot artifacts."""

    def __init__(self, *, artifacts: ArtifactSettings) -> None:
        """Initialize the prompt-enhancement service.

        Args:
            artifacts: Artifact directory settings.
        """

        self._artifacts = artifacts

    def load_or_create_enhancement(
        self,
        snapshot: SnapshotBundleModel,
        *,
        refresh_generated: bool = False,
    ) -> PromptEnhancementModel:
        """Load or create the prompt enhancement for one schema snapshot.

        Existing user-authored context is preserved when the generated guidance
        is refreshed because the snapshot changed.

        Args:
            snapshot: Snapshot bundle backing the enhancement.
            refresh_generated: Whether to force regeneration of DB-aware guidance.

        Returns:
            PromptEnhancementModel: Loaded or newly generated enhancement artifact.
        """

        path = self.enhancement_path(
            datasource_name=snapshot.datasource_name,
            schema_name=snapshot.regenerate.schema_name,
        )
        if path.exists():
            existing = self.load_prompt_enhancement(path)
            if (
                not refresh_generated
                and existing.snapshot_id == snapshot.snapshot_id
                and existing.generated_context_version >= _GENERATED_CONTEXT_VERSION
                and existing.generated_context
            ):
                return existing
            return self._build_enhancement(
                snapshot,
                active=existing.active,
                user_context=existing.user_context,
                business_rules=existing.business_rules,
                additional_effective_context=existing.additional_effective_context,
                answer_style=existing.answer_style,
                exploration=existing.exploration,
                created_at=existing.created_at,
            )
        return self._build_enhancement(snapshot)

    def update_enhancement(
        self,
        snapshot: SnapshotBundleModel,
        *,
        active: bool,
        user_context: str | None,
        business_rules: str | None,
        additional_effective_context: str | None,
        answer_style: str | None,
        refresh_generated: bool = False,
    ) -> PromptEnhancementModel:
        """Update and persist the prompt enhancement for one schema snapshot.

        Args:
            snapshot: Snapshot bundle backing the enhancement.
            active: Whether the enhancement should be used at runtime.
            user_context: User-provided domain context.
            business_rules: User-provided business rules or caveats.
            additional_effective_context: Extra prompt instructions that should
                be merged directly into the effective system prompt.
            answer_style: User-provided answer-style guidance.
            refresh_generated: Whether DB-aware guidance should be regenerated.

        Returns:
            PromptEnhancementModel: Persisted enhancement artifact.
        """

        enhancement = self.load_or_create_enhancement(
            snapshot,
            refresh_generated=refresh_generated,
        )
        updated = enhancement.model_copy(
            update={
                "active": active,
                "user_context": _normalize_optional_text(user_context),
                "business_rules": _normalize_optional_text(business_rules),
                "additional_effective_context": _normalize_optional_text(
                    additional_effective_context
                ),
                "answer_style": _normalize_optional_text(answer_style),
                "updated_at": datetime.now(UTC),
            }
        )
        return updated.model_copy(
            update={
                "token_estimates": self._build_token_estimates(updated),
                "summary": _build_enhancement_summary(updated),
                "content_hash": self._hash_enhancement(updated),
            }
        )

    def save_exploration_context(
        self,
        snapshot: SnapshotBundleModel,
        *,
        exploration: PromptExplorationModel,
    ) -> PromptEnhancementModel:
        """Persist live exploration context for one schema enhancement.

        Args:
            snapshot: Snapshot bundle backing the enhancement.
            exploration: Live exploration block to save.

        Returns:
            PromptEnhancementModel: Updated prompt enhancement artifact.
        """

        enhancement = self.load_or_create_enhancement(snapshot)
        updated = enhancement.model_copy(
            update={
                "exploration": exploration,
                "updated_at": datetime.now(UTC),
            }
        )
        return updated.model_copy(
            update={
                "token_estimates": self._build_token_estimates(updated),
                "summary": _build_enhancement_summary(updated),
                "content_hash": self._hash_enhancement(updated),
            }
        )

    def save_prompt_enhancement(self, enhancement: PromptEnhancementModel) -> Path:
        """Persist one prompt-enhancement artifact to disk.

        Args:
            enhancement: Enhancement artifact to save.

        Returns:
            Path: Saved enhancement path.
        """

        path = self.enhancement_path(
            datasource_name=enhancement.datasource_name,
            schema_name=enhancement.schema_name,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            orjson.dumps(
                enhancement.model_dump(mode="json"),
                option=orjson.OPT_INDENT_2,
            )
        )
        return path

    @staticmethod
    def load_prompt_enhancement(path: str | Path) -> PromptEnhancementModel:
        """Load one persisted prompt-enhancement artifact.

        Args:
            path: Saved enhancement path.

        Returns:
            PromptEnhancementModel: Parsed enhancement artifact.
        """

        return PromptEnhancementModel.model_validate(
            orjson.loads(Path(path).read_bytes())
        )

    def load_saved_enhancement(
        self,
        *,
        datasource_name: str,
        schema_name: str,
    ) -> PromptEnhancementModel | None:
        """Load a saved prompt enhancement when one exists.

        Args:
            datasource_name: Datasource identifier.
            schema_name: Schema name.

        Returns:
            PromptEnhancementModel | None: Persisted enhancement or `None`.
        """

        path = self.enhancement_path(
            datasource_name=datasource_name,
            schema_name=schema_name,
        )
        if not path.exists():
            return None
        return self.load_prompt_enhancement(path)

    def enhancement_path(self, *, datasource_name: str, schema_name: str) -> Path:
        """Return the persisted path for one datasource/schema enhancement.

        Args:
            datasource_name: Datasource identifier.
            schema_name: Schema name.

        Returns:
            Path: JSON path for the enhancement artifact.
        """

        return (
            Path(self._artifacts.root_dir)
            / self._artifacts.prompt_enhancements_dir
            / datasource_name
            / f"{schema_name}.json"
        )

    def _build_enhancement(
        self,
        snapshot: SnapshotBundleModel,
        *,
        active: bool = True,
        user_context: str | None = None,
        business_rules: str | None = None,
        additional_effective_context: str | None = None,
        answer_style: str | None = None,
        exploration: PromptExplorationModel | None = None,
        created_at: datetime | None = None,
    ) -> PromptEnhancementModel:
        """Build a prompt-enhancement artifact from one snapshot.

        Args:
            snapshot: Snapshot bundle backing the enhancement.
            active: Whether the enhancement is active.
            user_context: User-provided domain context.
            business_rules: User-provided business rules or caveats.
            additional_effective_context: Extra prompt instructions that should
                be merged directly into the effective system prompt.
            answer_style: User-provided answer-style guidance.
            exploration: Optional saved live exploration block.
            created_at: Original creation timestamp when refreshing an artifact.

        Returns:
            PromptEnhancementModel: Generated enhancement artifact.
        """

        enhancement = PromptEnhancementModel(
            datasource_name=snapshot.datasource_name,
            schema_name=snapshot.regenerate.schema_name,
            snapshot_id=snapshot.snapshot_id,
            created_at=created_at or datetime.now(UTC),
            updated_at=datetime.now(UTC),
            generated_context_version=_GENERATED_CONTEXT_VERSION,
            active=active,
            generated_context=self._build_generated_context(snapshot),
            token_estimates={},
            exploration=exploration,
            user_context=_normalize_optional_text(user_context),
            business_rules=_normalize_optional_text(business_rules),
            additional_effective_context=_normalize_optional_text(
                additional_effective_context
            ),
            answer_style=_normalize_optional_text(answer_style),
        )
        enhancement = enhancement.model_copy(
            update={"token_estimates": self._build_token_estimates(enhancement)}
        )
        return enhancement.model_copy(
            update={
                "summary": _build_enhancement_summary(enhancement),
                "content_hash": self._hash_enhancement(enhancement),
            }
        )

    def _build_token_estimates(
        self,
        enhancement: PromptEnhancementModel,
    ) -> dict[str, int | str | None]:
        """Build cached token estimates for one prompt enhancement."""
        return estimate_prompt_enhancement_tokens(
            generated_context=enhancement.generated_context,
            exploration_context=(
                None
                if enhancement.exploration is None
                else enhancement.exploration.context
            ),
            user_context=enhancement.user_context,
            business_rules=enhancement.business_rules,
            additional_effective_context=enhancement.additional_effective_context,
            answer_style=enhancement.answer_style,
        )

    def _build_generated_context(self, snapshot: SnapshotBundleModel) -> str:
        """Build deterministic DB-aware guidance from one snapshot.

        Args:
            snapshot: Snapshot bundle backing the enhancement.

        Returns:
            str: High-signal prompt guidance grounded in stored metadata.
        """

        profiles = {
            f"{profile.schema_name}.{profile.table_name}": profile
            for profile in snapshot.profiles
        }
        tables = {
            _qualify_name(table.schema_name, table.name): table
            for table in snapshot.schema_metadata.tables
        }
        schema_shape = _build_schema_shape_lines(snapshot, profiles)
        focus_tables = _build_focus_table_lines(snapshot, profiles)
        identifier_hints = _build_identifier_hint_lines(snapshot, profiles, tables)
        index_hints = _build_index_hint_lines(snapshot)
        relationship_hints = _build_relationship_lines(snapshot, tables)
        category_hints = _build_category_hint_lines(profiles.values())
        nullability_hints = _build_nullability_hint_lines(profiles.values())
        view_hints = _build_view_lines(snapshot)
        operational_guidance = _build_operational_guidance_lines(snapshot)
        lines = [
            (
                f"Snapshot summary: {snapshot.summary or 'No snapshot summary available.'} "
                f"Snapshot ID={snapshot.snapshot_id}."
            ),
            "Schema shape:",
            *(schema_shape or ["- No schema-shape summary was available."]),
            "Entity priorities:",
            *(focus_tables or ["- No high-signal tables were profiled."]),
            "Identifier hints:",
            *(identifier_hints or ["- No identifier-like columns were detected."]),
            "Index and access-path hints:",
            *(
                index_hints
                or ["- No high-signal indexes were reflected for this schema."]
            ),
            "Relationship paths:",
            *(relationship_hints or ["- No foreign-key relationships were detected."]),
            "Categorical and filter-friendly columns:",
            *(
                category_hints
                or ["- No low-cardinality filter or grouping columns were profiled."]
            ),
            "Nullability and data-quality cues:",
            *(
                nullability_hints
                or ["- No strongly sparse or null-heavy columns were profiled."]
            ),
            "View coverage:",
            *(view_hints or ["- No views were present in the stored snapshot."]),
            "Operational guidance:",
            *(operational_guidance or ["- Use stored metadata before guarded SQL."]),
        ]
        return "\n".join(lines)

    @staticmethod
    def _hash_enhancement(enhancement: PromptEnhancementModel) -> str:
        """Return a deterministic content hash for one enhancement artifact.

        Args:
            enhancement: Enhancement artifact to hash.

        Returns:
            str: Stable SHA-256 hash.
        """

        payload = orjson.dumps(
            enhancement.model_dump(
                mode="json",
                exclude={"content_hash", "summary", "updated_at", "created_at"},
            ),
            option=orjson.OPT_SORT_KEYS,
        )
        return sha256(payload).hexdigest()


def render_prompt_enhancement_text(
    enhancement: PromptEnhancementModel | None,
) -> str | None:
    """Render one prompt enhancement into a system-prompt block.

    Args:
        enhancement: Optional prompt enhancement artifact.

    Returns:
        str | None: Rendered enhancement block when active.
    """

    if enhancement is None or not enhancement.active:
        return None
    sections = [
        "DATABASE-SPECIFIC PROMPT ENHANCEMENT:",
        enhancement.generated_context,
    ]
    if enhancement.exploration is not None and enhancement.exploration.context:
        sections.extend(["LIVE EXPLORED CONTEXT:", enhancement.exploration.context])
    if enhancement.user_context:
        sections.extend(["USER CONTEXT:", enhancement.user_context])
    if enhancement.business_rules:
        sections.extend(["BUSINESS RULES AND CAVEATS:", enhancement.business_rules])
    if enhancement.additional_effective_context:
        sections.extend(
            [
                "ADDITIONAL EFFECTIVE PROMPT CONTEXT:",
                enhancement.additional_effective_context,
            ]
        )
    if enhancement.answer_style:
        sections.extend(["ANSWER STYLE:", enhancement.answer_style])
    return "\n".join(section for section in sections if section.strip())


def merge_prompt_with_enhancement(
    base_prompt: str,
    enhancement: PromptEnhancementModel | None,
) -> str:
    """Merge one prompt enhancement into a base prompt.

    Args:
        base_prompt: Base system prompt text.
        enhancement: Optional prompt enhancement artifact.

    Returns:
        str: Prompt with the enhancement block appended when active.
    """

    enhancement_text = render_prompt_enhancement_text(enhancement)
    if enhancement_text is None:
        return base_prompt
    return f"{base_prompt}\n{enhancement_text}"


def _build_focus_table_lines(
    snapshot: SnapshotBundleModel,
    profiles: dict[str, TableProfileModel],
) -> list[str]:
    """Build table-priority lines from stored profiles.

    Args:
        snapshot: Snapshot bundle backing the enhancement.
        profiles: Profile lookup keyed by qualified table name.

    Returns:
        list[str]: High-signal table lines for prompt guidance.
    """

    qualified_tables = [
        (
            _qualify_name(table.schema_name, table.name),
            table,
            profiles.get(_qualify_name(table.schema_name, table.name)),
        )
        for table in snapshot.schema_metadata.tables
    ]

    def sort_key(
        item: tuple[str, TableModel, TableProfileModel | None],
    ) -> tuple[int, int, int, int]:
        _, table, profile = item
        if profile is None:
            return (0, 0, len(table.columns), len(table.foreign_keys))
        return (
            profile.relationship_count,
            profile.storage_bytes or 0,
            profile.row_count or 0,
            len(table.columns),
        )

    lines: list[str] = []
    for qualified_name, table, profile in sorted(
        qualified_tables,
        key=sort_key,
        reverse=True,
    )[:_MAX_FOCUS_TABLES]:
        parts = [qualified_name]
        if profile is not None and profile.entity_kind:
            parts.append(f"role={profile.entity_kind}")
        if profile is not None and profile.row_count is not None:
            parts.append(f"rows={profile.row_count}")
        if profile is not None and profile.storage_bytes is not None:
            parts.append(f"storage_bytes={profile.storage_bytes}")
        if profile is not None and profile.relationship_count:
            parts.append(f"relationships={profile.relationship_count}")
        if table.primary_key:
            parts.append(f"pk={', '.join(table.primary_key)}")
        business_keys = _build_business_key_summary(table=table, profile=profile)
        if business_keys:
            parts.append(f"business_keys={business_keys}")
        related_summary = _build_related_table_summary(profile)
        if related_summary:
            parts.append(f"related={related_summary}")
        filter_summary = _build_filter_column_summary(profile)
        if filter_summary:
            parts.append(f"filters={filter_summary}")
        lines.append(f"- {'; '.join(parts)}")
    return lines


def _build_identifier_hint_lines(
    snapshot: SnapshotBundleModel,
    profiles: dict[str, TableProfileModel],
    tables: dict[str, TableModel],
) -> list[str]:
    """Build identifier-style hints from table metadata and profiles.

    Args:
        snapshot: Snapshot bundle backing the enhancement.
        profiles: Table profiles captured with the snapshot keyed by table name.
        tables: Table metadata keyed by qualified table name.

    Returns:
        list[str]: Identifier and high-cardinality hints.
    """

    candidates: list[tuple[int, str]] = []
    for table in snapshot.schema_metadata.tables:
        qualified_table = _qualify_name(table.schema_name, table.name)
        profile = profiles.get(qualified_table)
        profile_columns = {
            column.name: column
            for column in ([] if profile is None else profile.columns)
        }
        if table.primary_key:
            candidates.append(
                (
                    10,
                    (
                        f"- {qualified_table}: primary key="
                        f"{', '.join(table.primary_key)}"
                    ),
                )
            )
        for constraint in table.unique_constraints:
            if not constraint.columns:
                continue
            candidates.append(
                (
                    8,
                    (
                        f"- {qualified_table}: unique constraint on "
                        f"{', '.join(constraint.columns)}"
                    ),
                )
            )
        row_count = (
            0 if profile is None or profile.row_count is None else profile.row_count
        )
        for column in profile_columns.values():
            score = _score_identifier_candidate(column, row_count=row_count)
            if score <= 0:
                continue
            unique_bits: list[str] = []
            if column.unique_value_count is not None:
                unique_bits.append(f"unique={column.unique_value_count}")
            if column.unique_ratio is not None:
                unique_bits.append(f"unique_ratio={column.unique_ratio:.2f}")
            label = f"- {qualified_table}.{column.name} looks identifier-like"
            if unique_bits:
                label += f" ({', '.join(unique_bits)})"
            candidates.append((score, label))
        single_unique_indexes = [
            index.columns[0]
            for index in tables[qualified_table].indexes
            if index.unique and len(index.columns) == 1
        ]
        for column_name in single_unique_indexes:
            if column_name in table.primary_key:
                continue
            candidates.append(
                (
                    7,
                    f"- {qualified_table}.{column_name} is backed by a unique index.",
                )
            )
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    deduped: list[str] = []
    seen: set[str] = set()
    for _, label in candidates:
        if label in seen:
            continue
        seen.add(label)
        deduped.append(label)
        if len(deduped) == _MAX_IDENTIFIER_HINTS:
            break
    return deduped


def _build_relationship_lines(
    snapshot: SnapshotBundleModel,
    tables: dict[str, TableModel],
) -> list[str]:
    """Build high-signal relationship guidance lines.

    Args:
        snapshot: Snapshot bundle backing the enhancement.
        tables: Table metadata keyed by qualified table name.

    Returns:
        list[str]: Relationship lines for prompt guidance.
    """

    lines: list[str] = []
    for edge in snapshot.relationship_edges[:_MAX_RELATIONSHIP_HINTS]:
        source = _qualify_name(edge.source_schema, edge.source_table)
        target = _qualify_name(edge.target_schema, edge.target_table)
        source_columns = ", ".join(edge.source_columns) or "unknown"
        target_columns = ", ".join(edge.target_columns) or "unknown"
        source_table = tables.get(source)
        cardinality = _describe_relationship_cardinality(
            table=source_table,
            source_columns=edge.source_columns,
        )
        relation_name = edge.constraint_name or f"{source_columns}_to_{target_columns}"
        lines.append(
            (
                f"- {target}.{target_columns} -> {source}.{source_columns} "
                f"({cardinality}; constraint={relation_name})"
            )
        )
    return lines


def _build_index_hint_lines(snapshot: SnapshotBundleModel) -> list[str]:
    """Build high-signal index and access-path hints from table metadata."""

    candidates: list[tuple[int, str]] = []
    for table in snapshot.schema_metadata.tables:
        qualified_name = _qualify_name(table.schema_name, table.name)
        foreign_key_columns = {
            column_name
            for foreign_key in table.foreign_keys
            for column_name in foreign_key.columns
        }
        for index in table.indexes:
            if not index.columns:
                continue
            purpose_bits: list[str] = []
            if index.unique:
                purpose_bits.append("unique lookup")
            if any(column in foreign_key_columns for column in index.columns):
                purpose_bits.append("join support")
            if not purpose_bits:
                purpose_bits.append("scan/filter support")
            score = 3 if index.unique else 1
            if "join support" in purpose_bits:
                score += 2
            candidates.append(
                (
                    score,
                    (
                        f"- {qualified_name}: index "
                        f"{index.name or '(unnamed)'} on {', '.join(index.columns)} "
                        f"supports {', '.join(purpose_bits)}."
                    ),
                )
            )
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [label for _, label in candidates[:_MAX_INDEX_HINTS]]


def _build_schema_shape_lines(
    snapshot: SnapshotBundleModel,
    profiles: dict[str, TableProfileModel],
) -> list[str]:
    """Build a concise schema-shape summary for one snapshot."""

    lines = [
        (
            f"- Captured {len(snapshot.schema_metadata.tables)} tables, "
            f"{len(snapshot.schema_metadata.views)} views, and "
            f"{len(snapshot.relationship_edges)} foreign-key relationships."
        )
    ]
    connected = sorted(
        (
            (
                qualified_name,
                profile.relationship_count,
            )
            for qualified_name, profile in profiles.items()
            if profile.relationship_count > 0
        ),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )[:3]
    if connected:
        lines.append(
            "- Most connected tables: "
            + ", ".join(
                f"{qualified_name} ({relationship_count} relationships)"
                for qualified_name, relationship_count in connected
            )
        )
    largest = sorted(
        (
            (
                qualified_name,
                profile.storage_bytes or 0,
                profile.row_count or 0,
            )
            for qualified_name, profile in profiles.items()
        ),
        key=lambda item: (item[1], item[2], item[0]),
        reverse=True,
    )[:3]
    if largest:
        lines.append(
            "- Largest profiled tables: "
            + ", ".join(
                f"{qualified_name} (storage_bytes={storage_bytes}, rows={row_count})"
                for qualified_name, storage_bytes, row_count in largest
            )
        )
    return lines


def _build_category_hint_lines(
    profiles: list[TableProfileModel],
) -> list[str]:
    """Build low-cardinality filter and grouping hints from profiles."""

    candidates: list[tuple[int, str]] = []
    for profile in profiles:
        qualified_table = _qualify_name(profile.schema_name, profile.table_name)
        for column in profile.columns:
            if (
                _score_identifier_candidate(column, row_count=profile.row_count or 0)
                > 0
            ):
                continue
            if column.unique_value_count is None or column.unique_value_count < 2:
                continue
            if column.unique_value_count > 12:
                continue
            preview = _build_value_preview(column)
            parts = [
                f"- {qualified_table}.{column.name} is likely useful for filters/grouping",
                f"unique={column.unique_value_count}",
            ]
            if column.unique_ratio is not None:
                parts.append(f"unique_ratio={column.unique_ratio:.2f}")
            if preview:
                parts.append(f"values={preview}")
            candidates.append(
                (
                    max(1, 12 - column.unique_value_count),
                    "; ".join(parts),
                )
            )
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [label for _, label in candidates[:_MAX_CATEGORY_HINTS]]


def _build_nullability_hint_lines(
    profiles: list[TableProfileModel],
) -> list[str]:
    """Build nullability and sparsity hints from column profile statistics."""

    candidates: list[tuple[float, str]] = []
    for profile in profiles:
        qualified_table = _qualify_name(profile.schema_name, profile.table_name)
        for column in profile.columns:
            if column.null_ratio is None or column.null_ratio < 0.4:
                continue
            preview = _build_value_preview(column)
            label = (
                f"- {qualified_table}.{column.name} is sparse "
                f"(null_ratio={column.null_ratio:.2f})"
            )
            if preview:
                label += f"; non-null examples={preview}"
            candidates.append((column.null_ratio, label))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [label for _, label in candidates[:_MAX_NULLABILITY_HINTS]]


def _build_view_lines(snapshot: SnapshotBundleModel) -> list[str]:
    """Build view coverage lines for prompt guidance.

    Args:
        snapshot: Snapshot bundle backing the enhancement.

    Returns:
        list[str]: View hint lines.
    """

    lines: list[str] = []
    for view in snapshot.schema_metadata.views[:_MAX_VIEW_HINTS]:
        qualified_name = _qualify_name(view.schema_name, view.name)
        summary = view.summary or f"{len(view.columns)} columns"
        lines.append(
            f"- {qualified_name}: {summary}; definition_available={view.definition is not None}"
        )
    return lines


def _build_business_key_summary(
    *,
    table: TableModel,
    profile: TableProfileModel | None,
) -> str | None:
    """Build a short business-key summary for one table.

    Args:
        table: Table metadata to summarize.
        profile: Optional table profile for identifier scoring.

    Returns:
        str | None: Comma-separated business-key summary.
    """

    constraint_columns = [
        ", ".join(constraint.columns)
        for constraint in table.unique_constraints
        if constraint.columns
    ]
    if constraint_columns:
        return ", ".join(constraint_columns[:3])
    if profile is None:
        return None
    foreign_key_columns = {
        column_name
        for foreign_key in table.foreign_keys
        for column_name in foreign_key.columns
    }
    column_names: list[str] = []
    for column in profile.columns:
        if column.name in table.primary_key or column.name in foreign_key_columns:
            continue
        if _score_identifier_candidate(column, row_count=profile.row_count or 0) <= 1:
            continue
        column_names.append(column.name)
        if len(column_names) == 3:
            break
    if not column_names:
        return None
    return ", ".join(column_names)


def _build_related_table_summary(profile: TableProfileModel | None) -> str | None:
    """Build a short related-table summary from one table profile."""

    if profile is None or not profile.related_tables:
        return None
    return ", ".join(profile.related_tables[:3])


def _build_filter_column_summary(profile: TableProfileModel | None) -> str | None:
    """Build a short filter-column summary from one table profile."""

    if profile is None:
        return None
    candidates: list[str] = []
    for column in profile.columns:
        if _score_identifier_candidate(column, row_count=profile.row_count or 0) > 0:
            continue
        if (
            column.unique_value_count is None
            or not 2 <= column.unique_value_count <= 12
        ):
            continue
        candidates.append(column.name)
        if len(candidates) == 3:
            break
    if not candidates:
        return None
    return ", ".join(candidates)


def _build_value_preview(column: ColumnProfileModel) -> str | None:
    """Build a concise preview of representative values for one column."""

    top_values = column.top_values[:3]
    if top_values:
        preview = []
        for item in top_values:
            value = _format_value(item.get("value"))
            count = item.get("count")
            if count is None:
                preview.append(value)
            else:
                preview.append(f"{value} ({count})")
        return ", ".join(preview)
    sample_values = column.sample_values[:3]
    if sample_values:
        return ", ".join(_format_value(value) for value in sample_values)
    return None


def _describe_relationship_cardinality(
    *,
    table: TableModel | None,
    source_columns: list[str],
) -> str:
    """Describe one FK relationship using source-table uniqueness heuristics."""

    if table is None:
        return "relationship cardinality unknown"
    if _is_unique_column_set(table=table, columns=source_columns):
        return "likely one-to-one"
    return "likely one-to-many"


def _is_unique_column_set(*, table: TableModel, columns: list[str]) -> bool:
    """Return whether a column set is unique on one table."""

    column_set = set(columns)
    if not column_set:
        return False
    if column_set == set(table.primary_key):
        return True
    if any(
        column_set == set(constraint.columns) for constraint in table.unique_constraints
    ):
        return True
    return any(
        index.unique and column_set == set(index.columns) for index in table.indexes
    )


def _build_operational_guidance_lines(
    snapshot: SnapshotBundleModel,
) -> list[str]:
    """Build deterministic workflow guidance grounded in the stored snapshot."""

    guidance = [
        "- Start with stored snapshot/profile context before issuing guarded live SQL.",
        "- Treat snapshot-derived facts as capture-time metadata; use guarded SQL for current counts, sums, filters, or recency-sensitive answers.",
        "- Follow the listed foreign-key paths for joins instead of inventing unsupported relationships.",
        "- Distinguish clearly between snapshot artifacts, retrieval results, and live SQL findings in final answers.",
    ]
    if snapshot.schema_metadata.views:
        guidance.append(
            "- Inspect existing views before rebuilding the same rollups manually; they often encode the intended business grain."
        )
    return guidance


def _qualify_name(schema_name: str | None, object_name: str) -> str:
    """Return a schema-qualified object name when a schema is present."""

    if schema_name is None:
        return object_name
    return f"{schema_name}.{object_name}"


def _format_value(value: object) -> str:
    """Render one profile value for prompt-friendly previews."""

    if value is None:
        return "NULL"
    text = str(value)
    if len(text) > 40:
        return f"{text[:37]}..."
    return text


def _score_identifier_candidate(column: ColumnProfileModel, *, row_count: int) -> int:
    """Score whether a column looks like an identifier or business key.

    Args:
        column: Column profile to score.
        row_count: Parent table row count when available.

    Returns:
        int: Candidate score where higher is stronger.
    """

    normalized_name = column.name.lower()
    score = 0
    if any(
        token in normalized_name
        for token in ("id", "code", "email", "uuid", "key", "number", "sku")
    ):
        score += 2
    if (
        row_count >= 10
        and column.unique_ratio is not None
        and column.unique_ratio >= 0.9
    ):
        score += 3
    elif (
        row_count >= 10
        and column.unique_ratio is not None
        and column.unique_ratio >= 0.6
    ):
        score += 2
    if column.unique_value_count is not None and row_count >= 10:
        if column.unique_value_count >= row_count:
            score += 2
        elif column.unique_value_count >= max(2, int(row_count * 0.7)):
            score += 1
    if (
        any(
            token in normalized_name
            for token in ("code", "email", "uuid", "number", "sku")
        )
        and column.unique_value_count is not None
        and row_count > 0
        and column.unique_value_count >= row_count
    ):
        score += 2
    return score


def _normalize_optional_text(value: str | None) -> str | None:
    """Normalize optional user-provided text.

    Args:
        value: Raw optional text.

    Returns:
        str | None: Trimmed string or `None` when blank.
    """

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_enhancement_summary(enhancement: PromptEnhancementModel) -> str:
    """Build a concise summary for one prompt enhancement.

    Args:
        enhancement: Enhancement artifact to summarize.

    Returns:
        str: Human-readable enhancement summary.
    """

    status = "active" if enhancement.active else "inactive"
    user_layers = sum(
        1
        for value in (
            (
                None
                if enhancement.exploration is None
                else enhancement.exploration.context
            ),
            enhancement.user_context,
            enhancement.business_rules,
            enhancement.additional_effective_context,
            enhancement.answer_style,
        )
        if value
    )
    return (
        f"Prompt enhancement for '{enhancement.datasource_name}.{enhancement.schema_name}' "
        f"using snapshot '{enhancement.snapshot_id or 'none'}' "
        f"({status}, user_layers={user_layers}, "
        f"live_exploration={'yes' if enhancement.exploration else 'no'})."
    )
