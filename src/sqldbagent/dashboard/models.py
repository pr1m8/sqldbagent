"""Dashboard chat models."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
