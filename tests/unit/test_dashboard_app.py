"""Dashboard app helper tests."""

from __future__ import annotations

from datetime import UTC, datetime

from sqldbagent.core.config import AgentCheckpointSettings, AgentSettings, AppSettings
from sqldbagent.dashboard.app import (
    _build_checkpoint_status,
    _build_graphviz_dot,
    _build_mermaid_embed,
    _format_thread_label,
    _resolve_dashboard_checkpointer,
)
from sqldbagent.dashboard.models import DashboardThreadEntryModel
from sqldbagent.diagrams.models import (
    SchemaGraphEdgeModel,
    SchemaGraphModel,
    SchemaGraphNodeModel,
)


def test_resolve_dashboard_checkpointer_reuses_session_memory_saver() -> None:
    """Reuse one in-memory saver for the whole Streamlit session."""

    session_state: dict[str, object] = {}
    settings = AppSettings(
        datasources=[],
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(backend="memory"),
        ),
    )

    first = _resolve_dashboard_checkpointer(session_state, settings)
    second = _resolve_dashboard_checkpointer(session_state, settings)

    if first is None or second is None:
        raise AssertionError(session_state)
    if first is not second:
        raise AssertionError("Expected the same memory checkpointer instance")


def test_resolve_dashboard_checkpointer_defers_to_postgres_backend() -> None:
    """Avoid injecting a memory saver when Postgres checkpointing is enabled."""

    session_state: dict[str, object] = {}
    settings = AppSettings(
        datasources=[],
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(
                backend="postgres",
                postgres_url="postgresql+psycopg://demo:demo@127.0.0.1:5432/demo",
            ),
        ),
    )

    resolved = _resolve_dashboard_checkpointer(session_state, settings)

    if resolved is not None:
        raise AssertionError(resolved)
    if "dashboard_checkpointer" in session_state:
        raise AssertionError(session_state)


def test_build_checkpoint_status_reflects_backend() -> None:
    """Describe the dashboard persistence mode in plain language."""

    memory_status = _build_checkpoint_status({"checkpoint_backend": "memory"})
    postgres_status = _build_checkpoint_status({"checkpoint_backend": "postgres"})

    if "Streamlit session" not in memory_status:
        raise AssertionError(memory_status)
    if "Postgres" not in postgres_status:
        raise AssertionError(postgres_status)


def test_build_mermaid_embed_contains_runtime_markup() -> None:
    """Embed Mermaid markup into the Streamlit component HTML payload."""

    payload = _build_mermaid_embed("flowchart LR\nA --> B")

    if "cdn.jsdelivr.net/npm/mermaid@11" not in payload:
        raise AssertionError(payload)
    if "flowchart LR" not in payload:
        raise AssertionError(payload)


def test_format_thread_label_uses_preview_and_timestamp() -> None:
    """Build a readable selector label for saved dashboard threads."""

    entry = DashboardThreadEntryModel(
        thread_id="thread-12345678",
        datasource_name="postgres_demo",
        schema_name="public",
        updated_at=datetime(2026, 4, 2, 10, 0, tzinfo=UTC),
        last_user_message="List the public tables and highlight key relationships.",
    )

    label = _format_thread_label(
        entry,
        current_thread_id="other-thread",
        thread_id=entry.thread_id,
    )

    if "List the public tables" not in label:
        raise AssertionError(label)
    if "[public]" not in label:
        raise AssertionError(label)


def test_build_graphviz_dot_contains_nodes_and_edges() -> None:
    """Build DOT output for Streamlit graph rendering."""

    graph = SchemaGraphModel(
        nodes=[
            SchemaGraphNodeModel(
                node_id="public.customers",
                label="public.customers",
                kind="table",
                object_name="customers",
            ),
            SchemaGraphNodeModel(
                node_id="public.orders",
                label="public.orders",
                kind="table",
                object_name="orders",
            ),
        ],
        edges=[
            SchemaGraphEdgeModel(
                source_node_id="public.orders",
                target_node_id="public.customers",
                label="customer_id",
            )
        ],
    )

    dot = _build_graphviz_dot(graph)

    if "digraph schema {" not in dot:
        raise AssertionError(dot)
    if '"public.orders" -> "public.customers"' not in dot:
        raise AssertionError(dot)
    if 'label="customer_id"' not in dot:
        raise AssertionError(dot)
