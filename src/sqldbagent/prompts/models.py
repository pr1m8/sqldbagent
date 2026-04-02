"""Prompt export models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class PromptSectionModel(BaseModel):
    """Structured prompt section for stored prompt bundles.

    Attributes:
        title: Human-readable section title.
        content: Section body text.
    """

    title: str
    content: str


class PromptEnhancementModel(BaseModel):
    """Persisted prompt-enhancement artifact for one datasource/schema pair.

    Attributes:
        datasource_name: Datasource identifier.
        schema_name: Schema represented by the enhancement artifact.
        snapshot_id: Latest snapshot identifier used to generate DB-aware guidance.
        created_at: Enhancement creation timestamp.
        updated_at: Most recent enhancement update timestamp.
        content_hash: Deterministic content hash for persistence and reload checks.
        summary: Human-readable summary for dashboards and prompt exports.
        active: Whether the enhancement should be merged into dynamic prompts.
        generated_context: Deterministic DB-aware guidance derived from the snapshot.
        user_context: Freeform user context or domain notes layered on top.
        business_rules: Business-specific caveats, rules, or interpretation notes.
        answer_style: Preferred answer style for downstream agent responses.
    """

    datasource_name: str
    schema_name: str
    snapshot_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str | None = None
    summary: str | None = None
    active: bool = True
    generated_context: str = ""
    user_context: str | None = None
    business_rules: str | None = None
    answer_style: str | None = None


class PromptBundleModel(BaseModel):
    """Persisted prompt bundle derived from a stored schema snapshot.

    Attributes:
        snapshot_id: Source snapshot identifier.
        datasource_name: Datasource identifier.
        schema_name: Schema represented by the bundle.
        created_at: Prompt-bundle creation timestamp.
        content_hash: Deterministic content hash for the bundle.
        summary: Human-readable summary for downstream tools and docs.
        base_system_prompt: Prompt rendered before enhancement layers are applied.
        system_prompt: Final rendered prompt used by agent surfaces.
        sections: Structured prompt sections for human review and reuse.
        enhancement: Optional prompt-enhancement artifact merged into the bundle.
        state_seed: Initial agent state payload derived from stored artifacts.
    """

    snapshot_id: str
    datasource_name: str
    schema_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str | None = None
    summary: str | None = None
    base_system_prompt: str
    system_prompt: str
    sections: list[PromptSectionModel] = Field(default_factory=list)
    enhancement: PromptEnhancementModel | None = None
    state_seed: dict[str, Any] = Field(default_factory=dict)
