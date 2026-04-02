"""Reusable agent context helpers for prompts, state, and dashboard payloads."""

from __future__ import annotations

from typing import Any

from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.core.models.profile import TableProfileModel
from sqldbagent.prompts.enhancement import PromptEnhancementService
from sqldbagent.prompts.models import PromptEnhancementModel
from sqldbagent.snapshot.models import SnapshotBundleModel
from sqldbagent.snapshot.service import SnapshotService

_MAX_TABLE_HIGHLIGHTS = 8
_MAX_RELATIONSHIP_HIGHLIGHTS = 8


def build_sqldbagent_state_seed(
    *,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
) -> dict[str, Any]:
    """Build the initial state payload used by sqldbagent agent surfaces.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.

    Returns:
        dict[str, Any]: Seed state with snapshot and dashboard-friendly context.
    """

    resolved_settings = settings or load_settings()
    snapshot = load_latest_snapshot_bundle(
        datasource_name=datasource_name,
        settings=resolved_settings,
        schema_name=schema_name,
    )
    prompt_enhancement = _load_prompt_enhancement(
        datasource_name=datasource_name,
        settings=resolved_settings,
        schema_name=schema_name,
        snapshot=snapshot,
    )
    snapshot_id = snapshot.snapshot_id if snapshot is not None else None
    snapshot_summary = snapshot.summary if snapshot is not None else None
    dashboard_payload = build_sqldbagent_dashboard_payload(
        datasource_name=datasource_name,
        schema_name=schema_name,
        snapshot=snapshot,
        prompt_enhancement=prompt_enhancement,
    )
    return {
        "datasource_name": datasource_name,
        "schema_name": schema_name,
        "latest_snapshot_id": snapshot_id,
        "latest_snapshot_summary": snapshot_summary,
        "prompt_enhancement_active": (
            prompt_enhancement.active if prompt_enhancement is not None else False
        ),
        "prompt_enhancement_summary": (
            prompt_enhancement.summary if prompt_enhancement is not None else None
        ),
        "remembered_context_active": False,
        "remembered_context_summary": None,
        "dashboard_payload": dashboard_payload,
        "tool_call_digest": [],
    }


def build_sqldbagent_dashboard_payload(
    *,
    datasource_name: str,
    schema_name: str | None,
    snapshot: SnapshotBundleModel | None,
    prompt_enhancement: PromptEnhancementModel | None = None,
) -> dict[str, Any]:
    """Build dashboard-oriented agent state from the latest known snapshot.

    Args:
        datasource_name: Datasource identifier.
        schema_name: Optional schema focus.
        snapshot: Optional latest stored snapshot.
        prompt_enhancement: Optional prompt enhancement for the same scope.

    Returns:
        dict[str, Any]: Dashboard-friendly payload for UI surfaces.
    """

    cards = [
        {
            "title": "Datasource",
            "value": datasource_name,
            "kind": "identity",
        },
        {
            "title": "Schema",
            "value": schema_name or "all-visible",
            "kind": "scope",
        },
        {
            "title": "Snapshot",
            "value": snapshot.snapshot_id if snapshot is not None else "none",
            "kind": "artifact",
        },
    ]
    if snapshot is not None:
        cards.extend(
            [
                {
                    "title": "Tables",
                    "value": str(len(snapshot.schema_metadata.tables)),
                    "kind": "catalog",
                },
                {
                    "title": "Views",
                    "value": str(len(snapshot.schema_metadata.views)),
                    "kind": "catalog",
                },
                {
                    "title": "Relationships",
                    "value": str(len(snapshot.relationship_edges)),
                    "kind": "graph",
                },
            ]
        )
    if prompt_enhancement is not None:
        cards.append(
            {
                "title": "Prompt",
                "value": "enhanced" if prompt_enhancement.active else "stored-only",
                "kind": "prompt",
            }
        )
    return {
        "headline": f"{datasource_name}:{schema_name or 'default'}",
        "cards": cards,
        "notes": [
            "Use inspection and profiling before SQL.",
            "Treat safe_query_sql as guarded read-only access.",
            "Prefer reusable summaries that can feed docs, prompts, diagrams, and dashboard views.",
            *(
                [prompt_enhancement.summary]
                if prompt_enhancement is not None and prompt_enhancement.summary
                else []
            ),
        ],
    }


def load_latest_snapshot_bundle(
    *,
    datasource_name: str,
    settings: AppSettings,
    schema_name: str | None,
) -> SnapshotBundleModel | None:
    """Load the latest relevant snapshot bundle when available.

    Args:
        datasource_name: Datasource identifier.
        settings: Application settings.
        schema_name: Optional schema focus.

    Returns:
        SnapshotBundleModel | None: Latest matching snapshot or `None`.
    """

    try:
        if schema_name:
            return SnapshotService.load_latest_snapshot(
                settings.artifacts,
                datasource_name=datasource_name,
                schema_name=schema_name,
            )
    except FileNotFoundError:
        return None

    entries = SnapshotService.list_saved_snapshots(
        settings.artifacts,
        datasource_name=datasource_name,
    )
    if not entries:
        return None
    try:
        return SnapshotService.load_snapshot(
            SnapshotService._snapshot_dir_from_artifacts(settings.artifacts)
            / entries[0].path
        )
    except FileNotFoundError:
        return None


def build_snapshot_prompt_context(
    *,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
) -> str | None:
    """Build rich prompt context from the latest stored snapshot.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.

    Returns:
        str | None: Formatted prompt context block when a snapshot exists.
    """

    resolved_settings = settings or load_settings()
    if not resolved_settings.agent.include_latest_snapshot_context:
        return None

    snapshot = load_latest_snapshot_bundle(
        datasource_name=datasource_name,
        settings=resolved_settings,
        schema_name=schema_name,
    )
    if snapshot is None:
        return None

    profiles_by_table = {
        f"{profile.schema_name}.{profile.table_name}": profile
        for profile in snapshot.profiles
    }
    table_lines = _build_table_highlights(snapshot=snapshot, profiles=profiles_by_table)
    relationship_lines = _build_relationship_highlights(snapshot=snapshot)
    lines = [
        f"Snapshot ID: {snapshot.snapshot_id}",
        f"Snapshot Summary: {snapshot.summary or 'No snapshot summary available.'}",
        (
            "Captured Objects: "
            f"{len(snapshot.schema_metadata.tables)} tables, "
            f"{len(snapshot.schema_metadata.views)} views, "
            f"{len(snapshot.relationship_edges)} relationships"
        ),
        "Table Highlights:",
        *(table_lines or ["- No table highlights were captured."]),
        "Relationship Highlights:",
        *(relationship_lines or ["- No relationship highlights were captured."]),
    ]
    return "\n".join(lines)


def _load_prompt_enhancement(
    *,
    datasource_name: str,
    settings: AppSettings,
    schema_name: str | None,
    snapshot: SnapshotBundleModel | None,
) -> PromptEnhancementModel | None:
    """Load prompt-enhancement context for the active datasource/schema.

    Args:
        datasource_name: Datasource identifier.
        settings: Application settings.
        schema_name: Optional schema focus.
        snapshot: Optional latest snapshot for the same scope.

    Returns:
        PromptEnhancementModel | None: Saved or generated enhancement context.
    """

    if not settings.agent.enable_prompt_enhancements:
        return None
    if schema_name is None or snapshot is None:
        return None
    enhancements = PromptEnhancementService(artifacts=settings.artifacts)
    saved = enhancements.load_saved_enhancement(
        datasource_name=datasource_name,
        schema_name=schema_name,
    )
    if saved is not None:
        return saved
    return enhancements.load_or_create_enhancement(snapshot)


def _build_table_highlights(
    *,
    snapshot: SnapshotBundleModel,
    profiles: dict[str, TableProfileModel],
) -> list[str]:
    """Build high-signal table/profile lines for prompt context."""

    def sort_key(
        table_profile: tuple[str, TableProfileModel | None],
    ) -> tuple[int, int]:
        _, profile = table_profile
        storage_bytes = (
            0
            if profile is None or profile.storage_bytes is None
            else profile.storage_bytes
        )
        row_count = (
            0 if profile is None or profile.row_count is None else profile.row_count
        )
        return (storage_bytes, row_count)

    qualified_tables = [
        (
            f"{table.schema_name}.{table.name}",
            profiles.get(f"{table.schema_name}.{table.name}"),
        )
        for table in snapshot.schema_metadata.tables
    ]
    highlights: list[str] = []
    for qualified_name, profile in sorted(qualified_tables, key=sort_key, reverse=True)[
        :_MAX_TABLE_HIGHLIGHTS
    ]:
        summary_parts = [qualified_name]
        if profile is not None:
            if profile.entity_kind:
                summary_parts.append(f"entity={profile.entity_kind}")
            if profile.row_count is not None:
                summary_parts.append(f"rows={profile.row_count}")
            if profile.storage_bytes is not None:
                summary_parts.append(f"storage_bytes={profile.storage_bytes}")
            if profile.summary:
                summary_parts.append(profile.summary)
        highlights.append(f"- {'; '.join(summary_parts)}")
    return highlights


def _build_relationship_highlights(*, snapshot: SnapshotBundleModel) -> list[str]:
    """Build relationship highlight lines for prompt context."""

    highlights: list[str] = []
    for edge in snapshot.relationship_edges[:_MAX_RELATIONSHIP_HIGHLIGHTS]:
        summary = edge.summary or (
            f"{edge.source_schema}.{edge.source_table} -> "
            f"{edge.target_schema}.{edge.target_table}"
        )
        highlights.append(f"- {summary}")
    return highlights
