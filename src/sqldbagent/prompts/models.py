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


class PromptBundleModel(BaseModel):
    """Persisted prompt bundle derived from a stored schema snapshot.

    Attributes:
        snapshot_id: Source snapshot identifier.
        datasource_name: Datasource identifier.
        schema_name: Schema represented by the bundle.
        created_at: Prompt-bundle creation timestamp.
        content_hash: Deterministic content hash for the bundle.
        summary: Human-readable summary for downstream tools and docs.
        system_prompt: Final rendered prompt used by agent surfaces.
        sections: Structured prompt sections for human review and reuse.
        state_seed: Initial agent state payload derived from stored artifacts.
    """

    snapshot_id: str
    datasource_name: str
    schema_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str | None = None
    summary: str | None = None
    system_prompt: str
    sections: list[PromptSectionModel] = Field(default_factory=list)
    state_seed: dict[str, Any] = Field(default_factory=dict)
