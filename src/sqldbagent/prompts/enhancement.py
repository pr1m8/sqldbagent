"""Prompt-enhancement helpers built on top of stored snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import orjson

from sqldbagent.core.config import ArtifactSettings
from sqldbagent.core.models.profile import ColumnProfileModel, TableProfileModel
from sqldbagent.prompts.models import PromptEnhancementModel
from sqldbagent.snapshot.models import SnapshotBundleModel

_MAX_FOCUS_TABLES = 6
_MAX_IDENTIFIER_HINTS = 8
_MAX_RELATIONSHIP_HINTS = 8
_MAX_VIEW_HINTS = 5


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
            active=active,
            generated_context=self._build_generated_context(snapshot),
            user_context=_normalize_optional_text(user_context),
            business_rules=_normalize_optional_text(business_rules),
            additional_effective_context=_normalize_optional_text(
                additional_effective_context
            ),
            answer_style=_normalize_optional_text(answer_style),
        )
        return enhancement.model_copy(
            update={
                "summary": _build_enhancement_summary(enhancement),
                "content_hash": self._hash_enhancement(enhancement),
            }
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
        focus_tables = _build_focus_table_lines(snapshot, profiles)
        identifier_hints = _build_identifier_hint_lines(profiles.values())
        relationship_hints = _build_relationship_lines(snapshot)
        view_hints = _build_view_lines(snapshot)
        lines = [
            f"Snapshot summary: {snapshot.summary or 'No snapshot summary available.'}",
            "Entity priorities:",
            *(focus_tables or ["- No high-signal tables were profiled."]),
            "Identifier hints:",
            *(identifier_hints or ["- No identifier-like columns were detected."]),
            "Relationship paths:",
            *(relationship_hints or ["- No foreign-key relationships were detected."]),
            "View coverage:",
            *(view_hints or ["- No views were present in the stored snapshot."]),
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
            f"{table.schema_name}.{table.name}",
            profiles.get(f"{table.schema_name}.{table.name}"),
        )
        for table in snapshot.schema_metadata.tables
    ]

    def sort_key(item: tuple[str, TableProfileModel | None]) -> tuple[int, int, int]:
        _, profile = item
        if profile is None:
            return (0, 0, 0)
        return (
            profile.storage_bytes or 0,
            profile.row_count or 0,
            profile.relationship_count,
        )

    lines: list[str] = []
    for qualified_name, profile in sorted(
        qualified_tables,
        key=sort_key,
        reverse=True,
    )[:_MAX_FOCUS_TABLES]:
        if profile is None:
            lines.append(f"- {qualified_name}")
            continue
        parts = [qualified_name]
        if profile.entity_kind:
            parts.append(f"entity={profile.entity_kind}")
        if profile.row_count is not None:
            parts.append(f"rows={profile.row_count}")
        if profile.storage_bytes is not None:
            parts.append(f"storage_bytes={profile.storage_bytes}")
        if profile.relationship_count:
            parts.append(f"relationships={profile.relationship_count}")
        key_columns = _build_key_column_summary(profile)
        if key_columns:
            parts.append(f"key_columns={key_columns}")
        lines.append(f"- {'; '.join(parts)}")
    return lines


def _build_identifier_hint_lines(
    profiles: list[TableProfileModel],
) -> list[str]:
    """Build identifier-style hints from column profile statistics.

    Args:
        profiles: Table profiles captured with the snapshot.

    Returns:
        list[str]: Identifier and high-cardinality hints.
    """

    candidates: list[tuple[int, str]] = []
    for profile in profiles:
        qualified_table = f"{profile.schema_name}.{profile.table_name}"
        row_count = profile.row_count or 0
        for column in profile.columns:
            score = _score_identifier_candidate(column, row_count=row_count)
            if score <= 0:
                continue
            unique_bits: list[str] = []
            if column.unique_value_count is not None:
                unique_bits.append(f"unique={column.unique_value_count}")
            if column.unique_ratio is not None:
                unique_bits.append(f"unique_ratio={column.unique_ratio:.2f}")
            label = f"- {qualified_table}.{column.name}"
            if unique_bits:
                label += f" ({', '.join(unique_bits)})"
            candidates.append((score, label))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [label for _, label in candidates[:_MAX_IDENTIFIER_HINTS]]


def _build_relationship_lines(snapshot: SnapshotBundleModel) -> list[str]:
    """Build high-signal relationship guidance lines.

    Args:
        snapshot: Snapshot bundle backing the enhancement.

    Returns:
        list[str]: Relationship lines for prompt guidance.
    """

    lines: list[str] = []
    for edge in snapshot.relationship_edges[:_MAX_RELATIONSHIP_HINTS]:
        source = ".".join(
            part for part in [edge.source_schema, edge.source_table] if part
        )
        target = ".".join(
            part for part in [edge.target_schema, edge.target_table] if part
        )
        source_columns = ", ".join(edge.source_columns) or "unknown"
        target_columns = ", ".join(edge.target_columns) or "unknown"
        lines.append(f"- {source} ({source_columns}) -> {target} ({target_columns})")
    return lines


def _build_view_lines(snapshot: SnapshotBundleModel) -> list[str]:
    """Build view coverage lines for prompt guidance.

    Args:
        snapshot: Snapshot bundle backing the enhancement.

    Returns:
        list[str]: View hint lines.
    """

    lines: list[str] = []
    for view in snapshot.schema_metadata.views[:_MAX_VIEW_HINTS]:
        qualified_name = ".".join(
            part for part in [view.schema_name, view.name] if part
        )
        summary = view.summary or f"{len(view.columns)} columns"
        lines.append(f"- {qualified_name}: {summary}")
    return lines


def _build_key_column_summary(profile: TableProfileModel) -> str | None:
    """Build a short list of key columns for one table profile.

    Args:
        profile: Table profile to summarize.

    Returns:
        str | None: Comma-separated key-column summary.
    """

    columns = []
    for column in profile.columns:
        if _score_identifier_candidate(column, row_count=profile.row_count or 0) <= 0:
            continue
        columns.append(column.name)
        if len(columns) == 3:
            break
    if not columns:
        return None
    return ", ".join(columns)


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
        token in normalized_name for token in ("id", "code", "email", "uuid", "key")
    ):
        score += 2
    if column.unique_ratio is not None and column.unique_ratio >= 0.9:
        score += 3
    elif column.unique_ratio is not None and column.unique_ratio >= 0.6:
        score += 2
    if column.unique_value_count is not None and row_count > 0:
        if column.unique_value_count >= row_count:
            score += 2
        elif column.unique_value_count >= max(2, int(row_count * 0.7)):
            score += 1
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
        f"({status}, user_layers={user_layers})."
    )
