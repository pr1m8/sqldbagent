"""Prompt helpers for LangChain v1 and LangGraph agents."""

from __future__ import annotations

from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.snapshot.service import SnapshotService


def create_sqldbagent_system_prompt(
    *,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
) -> str:
    """Build the default sqldbagent system prompt.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.

    Returns:
        str: System prompt text for LangChain and LangGraph agents.
    """

    resolved_settings = settings or load_settings()
    snapshot_context = _load_snapshot_context(
        datasource_name=datasource_name,
        settings=resolved_settings,
        schema_name=schema_name,
    )
    schema_text = (
        f"Focus on schema '{schema_name}'."
        if schema_name
        else "Work across the visible schemas when necessary."
    )
    prompt_parts = [
        f"ROLE: You are the '{resolved_settings.agent.name}' database intelligence agent.",
        f"ACTIVE CONTEXT: Use datasource '{datasource_name}'. {schema_text}",
        "MISSION: Build a precise understanding of the database using normalized metadata, stored snapshots, retrieval over indexed snapshot documents, profiling, and guarded SQL only when necessary.",
        "WORKFLOW ORDER:",
        "1. Start with inspection, schema discovery, table/view description, and profiling tools.",
        "2. Reuse stored snapshot context before doing redundant live work.",
        "3. Prefer `retrieve_schema_context` over live SQL when indexed snapshot documents can answer the question.",
        "4. Use `safe_query_sql` only when metadata, retrieval, and profiles are insufficient.",
        "5. Prefer narrow, descriptive read-only queries with clear intent.",
        "6. When you infer something, say it is an inference and explain why.",
        "QUERY RULES:",
        "- Never assume write access or administrative permissions.",
        "- Never request destructive SQL.",
        "- Treat query limits, guards, and schema constraints as part of the contract, not optional suggestions.",
        "OUTPUT RULES:",
        "- Be descriptive and concrete about entities, relationships, row-count hints, storage hints, and data quality signals.",
        "- When useful, summarize findings in a way that can later feed docs, prompts, or dashboard views.",
        "- Prefer explaining what is known from snapshots versus what was learned from live reads.",
    ]
    if snapshot_context:
        prompt_parts.append(f"STORED SNAPSHOT CONTEXT:\n{snapshot_context}")
    return "\n".join(prompt_parts)


def _load_snapshot_context(
    *,
    datasource_name: str,
    settings: AppSettings,
    schema_name: str | None,
) -> str | None:
    """Load stored snapshot summary context for an agent prompt.

    Args:
        datasource_name: Datasource identifier.
        settings: Application settings.
        schema_name: Optional schema focus.

    Returns:
        str | None: Snapshot summary context when available.
    """

    if not settings.agent.include_latest_snapshot_context:
        return None

    try:
        if schema_name:
            latest = SnapshotService.load_latest_snapshot(
                settings.artifacts,
                datasource_name=datasource_name,
                schema_name=schema_name,
            )
            return latest.summary
    except FileNotFoundError:
        return None

    entries = SnapshotService.list_saved_snapshots(
        settings.artifacts,
        datasource_name=datasource_name,
    )[:3]
    summaries = [entry.summary for entry in entries if entry.summary]
    if not summaries:
        return None
    return "\n".join(f"- {summary}" for summary in summaries)
