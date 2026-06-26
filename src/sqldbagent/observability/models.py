"""Pydantic models for local usage and audit observability."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    """Return a timezone-aware timestamp for artifact models."""

    return datetime.now(UTC)


def _event_id() -> str:
    """Return a compact stable event identifier."""

    return uuid4().hex


class CostEstimateModel(BaseModel):
    """Estimated cost for a model or tool event.

    Attributes:
        currency: ISO-like currency code for the estimate.
        input_cost: Estimated prompt/input cost.
        output_cost: Estimated completion/output cost.
        total_cost: Estimated total cost.
        pricing_source: Source used for the estimate.
    """

    currency: str = "USD"
    input_cost: float | None = None
    output_cost: float | None = None
    total_cost: float | None = None
    pricing_source: str | None = None


class ModelUsageEventModel(BaseModel):
    """One local model-usage event extracted from a runtime turn.

    Attributes:
        event_id: Unique local event identifier.
        run_id: Local run identifier grouping events from one operation.
        thread_id: Optional LangGraph thread identifier.
        datasource_name: Datasource associated with the operation.
        schema_name: Optional schema focus.
        surface: Runtime surface that emitted the event.
        provider: Model provider when known.
        model: Model name when known.
        input_tokens: Prompt/input tokens.
        output_tokens: Completion/output tokens.
        total_tokens: Total tokens reported by the provider.
        cache_read_tokens: Cached input tokens read, when reported.
        cache_write_tokens: Cached input tokens written, when reported.
        reasoning_tokens: Reasoning tokens, when reported.
        cost: Optional cost estimate.
        langsmith_run_id: LangSmith run id when known.
        created_at: Event creation timestamp.
        metadata: Extra JSON-friendly metadata.
    """

    event_id: str = Field(default_factory=_event_id)
    run_id: str
    thread_id: str | None = None
    datasource_name: str | None = None
    schema_name: str | None = None
    surface: str
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost: CostEstimateModel | None = None
    langsmith_run_id: str | None = None
    created_at: datetime = Field(default_factory=_now)
    metadata: dict[str, object] = Field(default_factory=dict)


class ToolUsageEventModel(BaseModel):
    """One local tool-call usage event.

    Attributes:
        event_id: Unique local event identifier.
        run_id: Local run identifier grouping events from one operation.
        thread_id: Optional LangGraph thread identifier.
        datasource_name: Datasource associated with the operation.
        schema_name: Optional schema focus.
        surface: Runtime surface that emitted the event.
        tool_name: Tool name.
        status: Tool result status.
        duration_ms: Tool duration when known.
        output_characters: Size of the rendered tool output.
        compressed_output_characters: Size after digest/compression, when known.
        created_at: Event creation timestamp.
        metadata: Extra JSON-friendly metadata.
    """

    event_id: str = Field(default_factory=_event_id)
    run_id: str
    thread_id: str | None = None
    datasource_name: str | None = None
    schema_name: str | None = None
    surface: str
    tool_name: str
    status: str | None = None
    duration_ms: float | None = None
    output_characters: int | None = None
    compressed_output_characters: int | None = None
    created_at: datetime = Field(default_factory=_now)
    metadata: dict[str, object] = Field(default_factory=dict)


class AuditEventModel(BaseModel):
    """Append-only audit event describing what a runtime surface did.

    Attributes:
        event_id: Unique local event identifier.
        event_type: Stable event type such as `query.execute` or
            `agent.run_turn`.
        run_id: Optional local run identifier grouping related events.
        thread_id: Optional LangGraph thread identifier.
        surface: Runtime surface that emitted the event.
        datasource_name: Datasource associated with the event.
        schema_name: Optional schema focus.
        dialect: SQL dialect when known.
        access_mode: Requested database access mode.
        read_only: Whether the relevant path was read-only.
        status: Event status.
        started_at: Operation start timestamp.
        completed_at: Operation completion timestamp.
        duration_ms: Operation duration in milliseconds.
        input_limits: Limits applied to the operation.
        touched: Tables, columns, tools, or other objects touched.
        artifact_paths: Artifact paths written or read.
        warning: Optional warning text.
        error: Optional error text.
        metadata: Extra JSON-friendly metadata.
    """

    event_id: str = Field(default_factory=_event_id)
    event_type: str
    run_id: str | None = None
    thread_id: str | None = None
    surface: str
    datasource_name: str | None = None
    schema_name: str | None = None
    dialect: str | None = None
    access_mode: str | None = None
    read_only: bool | None = None
    status: Literal["started", "success", "warning", "error", "skipped"] = "success"
    started_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None
    duration_ms: float | None = None
    input_limits: dict[str, object] = Field(default_factory=dict)
    touched: dict[str, object] = Field(default_factory=dict)
    artifact_paths: list[str] = Field(default_factory=list)
    warning: str | None = None
    error: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class UsageBudgetPolicyModel(BaseModel):
    """Optional per-run token and cost budget policy."""

    warn_total_tokens: int | None = None
    hard_total_tokens: int | None = None
    warn_cost_usd: float | None = None
    hard_cost_usd: float | None = None


class RunUsageSummaryModel(BaseModel):
    """Aggregated local usage summary for a group of events."""

    event_count: int = 0
    model_event_count: int = 0
    tool_event_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)
