"""Typed state and context schemas for sqldbagent agents."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from sqldbagent.adapters.shared import require_dependency

_middleware_types = require_dependency("langchain.agents.middleware", "langchain")
AgentState = _middleware_types.AgentState


class DashboardCard(TypedDict):
    """Single dashboard-oriented card derived from agent state."""

    title: str
    value: str
    kind: str


class DashboardPayload(TypedDict):
    """Dashboard-friendly payload describing the active database context."""

    headline: str
    cards: list[DashboardCard]
    notes: list[str]


class SQLDBAgentContext(TypedDict):
    """Runtime context schema for sqldbagent agents."""

    datasource_name: str
    schema_name: NotRequired[str | None]
    latest_snapshot_id: NotRequired[str | None]
    latest_snapshot_summary: NotRequired[str | None]
    prompt_enhancement_active: NotRequired[bool]
    prompt_enhancement_summary: NotRequired[str | None]


class SQLDBAgentState(AgentState[Any]):
    """Extended LangChain agent state used by sqldbagent surfaces."""

    datasource_name: NotRequired[str]
    schema_name: NotRequired[str | None]
    latest_snapshot_id: NotRequired[str | None]
    latest_snapshot_summary: NotRequired[str | None]
    prompt_enhancement_active: NotRequired[bool]
    prompt_enhancement_summary: NotRequired[str | None]
    dashboard_payload: NotRequired[DashboardPayload]
    tool_call_digest: NotRequired[list[str]]
