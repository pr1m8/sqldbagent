"""Dashboard chat models."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from sqldbagent.diagrams.models import DiagramBundleModel
from sqldbagent.prompts.models import PromptBundleModel


class ChatMessageModel(BaseModel):
    """Rendered chat transcript entry for dashboard surfaces.

    Attributes:
        role: Message role shown in the dashboard.
        content: Human-readable message body.
        kind: Original LangChain/LangGraph message type.
        name: Optional tool or actor name.
        status: Optional tool status marker.
    """

    role: str
    content: str
    kind: str
    name: str | None = None
    status: str | None = None


class DashboardThreadEntryModel(BaseModel):
    """Persisted dashboard thread summary used for thread selection.

    Attributes:
        thread_id: Stable thread identifier used by the LangGraph checkpointer.
        datasource_name: Datasource identifier associated with the thread.
        schema_name: Optional schema focus for the thread.
        created_at: First time the thread was observed by the dashboard.
        updated_at: Most recent time the dashboard refreshed the thread entry.
        message_count: Number of rendered transcript messages currently known.
        latest_snapshot_id: Latest snapshot bound into the thread state, if any.
        last_user_message: Most recent user message preview.
        last_assistant_message: Most recent assistant message preview.
    """

    thread_id: str
    datasource_name: str
    schema_name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message_count: int = 0
    latest_snapshot_id: str | None = None
    last_user_message: str | None = None
    last_assistant_message: str | None = None


class ChatSessionModel(BaseModel):
    """Dashboard-ready snapshot of one agent conversation thread.

    Attributes:
        thread_id: Stable thread identifier used by the LangGraph checkpointer.
        datasource_name: Datasource identifier backing the session.
        schema_name: Optional schema focus.
        messages: Rendered chat transcript entries.
        dashboard_payload: Dashboard-friendly state payload from the agent state.
        observability: Dashboard-friendly runtime and tracing status payload.
        latest_snapshot_id: Latest known stored snapshot id.
        latest_snapshot_summary: Latest known stored snapshot summary.
        tool_call_digest: Compressed tool-call history from the agent state.
        diagram_bundle: Stored schema-diagram bundle associated with the session.
        prompt_bundle: Stored prompt bundle associated with the session.
        example_questions: Snapshot-aware starter questions for the dashboard chat.
        available_threads: Persisted dashboard thread summaries for selection.
    """

    thread_id: str
    datasource_name: str
    schema_name: str | None = None
    messages: list[ChatMessageModel] = Field(default_factory=list)
    dashboard_payload: dict[str, object] = Field(default_factory=dict)
    observability: dict[str, object] = Field(default_factory=dict)
    latest_snapshot_id: str | None = None
    latest_snapshot_summary: str | None = None
    tool_call_digest: list[str] = Field(default_factory=list)
    diagram_bundle: DiagramBundleModel | None = None
    prompt_bundle: PromptBundleModel | None = None
    example_questions: list[str] = Field(default_factory=list)
    available_threads: list[DashboardThreadEntryModel] = Field(default_factory=list)
