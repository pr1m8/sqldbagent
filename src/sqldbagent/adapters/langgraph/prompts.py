"""Prompt helpers for LangChain v1 and LangGraph agents."""

from __future__ import annotations

from sqldbagent.core.agent_context import (
    build_snapshot_prompt_context,
    load_latest_snapshot_bundle,
)
from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.prompts.enhancement import (
    PromptEnhancementService,
    merge_prompt_with_enhancement,
)
from sqldbagent.prompts.models import PromptEnhancementModel


def create_sqldbagent_base_system_prompt(
    *,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
    remembered_context: str | None = None,
) -> str:
    """Build the base sqldbagent system prompt before enhancement layers.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.
        remembered_context: Optional remembered database context loaded from the
            long-term memory store.

    Returns:
        str: Base system prompt text for LangChain and LangGraph agents.
    """

    resolved_settings = settings or load_settings()
    datasource = resolved_settings.get_datasource(datasource_name)
    snapshot_context = build_snapshot_prompt_context(
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
        (
            f"ACTIVE CONTEXT: Use datasource '{datasource_name}' with "
            f"dialect '{datasource.dialect.value}'. {schema_text}"
        ),
        "MISSION: Build a precise understanding of the database using normalized metadata, stored snapshots, retrieval over indexed snapshot documents, profiling, and guarded SQL only when necessary.",
        "WORKFLOW ORDER:",
        "1. Start with inspection, schema discovery, table/view description, and profiling tools.",
        "2. Reuse stored snapshot context before doing redundant live work.",
        "3. Prefer `retrieve_schema_context` over live SQL when indexed snapshot documents can answer the question.",
        "4. Use `safe_query_sql` only when metadata, retrieval, and profiles are insufficient.",
        "5. Prefer narrow, descriptive read-only queries with clear intent.",
        "6. When you infer something, say it is an inference and explain why.",
        "DIALECT AND ACCESS RULES:",
        (
            f"- Generate SQL that is valid for the active dialect: "
            f"{datasource.dialect.value}."
        ),
        (
            "- The default execution mode is read-only. Writable execution is "
            "exceptional, must be requested explicitly, and is only available "
            "when the datasource policy enables it."
        ),
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
    if remembered_context:
        prompt_parts.append(f"REMEMBERED DATABASE CONTEXT:\n{remembered_context}")
    return "\n".join(prompt_parts)


def create_sqldbagent_system_prompt(
    *,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
    enhancement: PromptEnhancementModel | None = None,
    remembered_context: str | None = None,
) -> str:
    """Build the default sqldbagent system prompt.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.
        enhancement: Optional preloaded prompt enhancement.
        remembered_context: Optional remembered database context loaded from the
            long-term memory store.

    Returns:
        str: System prompt text for LangChain and LangGraph agents.
    """

    resolved_settings = settings or load_settings()
    base_prompt = create_sqldbagent_base_system_prompt(
        datasource_name=datasource_name,
        settings=resolved_settings,
        schema_name=schema_name,
        remembered_context=remembered_context,
    )
    if not resolved_settings.agent.enable_prompt_enhancements:
        return base_prompt

    resolved_enhancement = enhancement
    if resolved_enhancement is None:
        snapshot = load_latest_snapshot_bundle(
            datasource_name=datasource_name,
            settings=resolved_settings,
            schema_name=schema_name,
        )
        if snapshot is not None:
            resolved_enhancement = PromptEnhancementService(
                artifacts=resolved_settings.artifacts
            ).load_or_create_enhancement(snapshot)
    return merge_prompt_with_enhancement(base_prompt, resolved_enhancement)
