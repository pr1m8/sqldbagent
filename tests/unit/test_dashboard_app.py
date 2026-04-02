"""Dashboard app helper tests."""

from __future__ import annotations

from datetime import UTC, datetime

from sqldbagent.core.config import AgentCheckpointSettings, AgentSettings, AppSettings
from sqldbagent.dashboard.app import (
    _build_checkpoint_status,
    _build_database_access_status,
    _build_graphviz_dot,
    _build_mermaid_embed,
    _format_thread_label,
    _resolve_dashboard_checkpointer,
    _should_render_chat_message,
    _should_show_example_questions,
    _summarize_tool_message,
)
from sqldbagent.dashboard.models import ChatMessageModel, DashboardThreadEntryModel
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


def test_resolve_dashboard_checkpointer_uses_session_memory_when_postgres_missing_url() -> (
    None
):
    """Keep one session saver when Postgres checkpointing is requested but unavailable."""

    session_state: dict[str, object] = {}
    settings = AppSettings(
        datasources=[],
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(backend="postgres"),
        ),
        postgres_host=None,
        postgres_db=None,
        postgres_user=None,
        postgres_password=None,
    )

    first = _resolve_dashboard_checkpointer(session_state, settings)
    second = _resolve_dashboard_checkpointer(session_state, settings)

    if first is None or second is None:
        raise AssertionError(session_state)
    if first is not second:
        raise AssertionError("Expected the same fallback memory checkpointer instance")


def test_build_checkpoint_status_reflects_backend() -> None:
    """Describe the dashboard persistence mode in plain language."""

    memory_status = _build_checkpoint_status(
        {
            "checkpoint_backend": "memory",
            "checkpoint_summary": "Thread persistence is scoped to the current dashboard session.",
        }
    )
    postgres_status = _build_checkpoint_status(
        {
            "checkpoint_backend": "postgres",
            "checkpoint_summary": "Durable thread persistence is active through the configured Postgres checkpoint database.",
        }
    )

    if "dashboard session" not in memory_status:
        raise AssertionError(memory_status)
    if "Postgres checkpoint database" not in postgres_status:
        raise AssertionError(postgres_status)


def test_build_database_access_status_prefers_summary_field() -> None:
    """Surface the dialect-aware read-only status copy when it is present."""

    status = _build_database_access_status(
        {
            "database_access_summary": (
                "Guarded SQL uses Postgres read-only transactions with the configured statement timeout."
            )
        }
    )

    if "Postgres read-only transactions" not in status:
        raise AssertionError(status)


def test_build_mermaid_embed_contains_runtime_markup() -> None:
    """Embed Mermaid markup into the Streamlit component HTML payload."""

    payload = _build_mermaid_embed("flowchart LR\nA --> B")

    if "cdn.jsdelivr.net/npm/mermaid@11" not in payload:
        raise AssertionError(payload)
    if "svg-pan-zoom@3.6.2" not in payload:
        raise AssertionError(payload)
    if "mermaid.render(" not in payload:
        raise AssertionError(payload)
    if "Interactive Mermaid SVG" not in payload:
        raise AssertionError(payload)
    if "download-svg" not in payload:
        raise AssertionError(payload)
    if "open-viewer" not in payload:
        raise AssertionError(payload)
    if "Open Focus View" not in payload:
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


def test_format_thread_label_prefers_display_name() -> None:
    """Prefer a saved thread display name over message previews."""

    entry = DashboardThreadEntryModel(
        thread_id="thread-87654321",
        datasource_name="postgres_demo",
        schema_name="public",
        display_name="Revenue analysis",
        updated_at=datetime(2026, 4, 2, 10, 30, tzinfo=UTC),
        last_user_message="List important tables.",
    )

    label = _format_thread_label(
        entry,
        current_thread_id="other-thread",
        thread_id=entry.thread_id,
    )

    if "Revenue analysis" not in label:
        raise AssertionError(label)


def test_summarize_tool_message_prefers_summary_field() -> None:
    """Prefer structured summary text when tool payloads provide it."""

    message = ChatMessageModel(
        role="tool",
        kind="tool",
        name="retrieve_schema_context",
        content='{"summary":"Retrieved 3 documents.","documents":[]}',
    )

    if _summarize_tool_message(message) != "Retrieved 3 documents.":
        raise AssertionError(_summarize_tool_message(message))


def test_should_show_example_questions_only_before_first_user_message() -> None:
    """Hide starter questions once a thread has a real user turn."""

    if _should_show_example_questions([]) is not True:
        raise AssertionError("Expected starter questions for an empty thread")

    if (
        _should_show_example_questions(
            [
                ChatMessageModel(
                    role="assistant",
                    kind="ai",
                    content="Welcome.",
                )
            ]
        )
        is not True
    ):
        raise AssertionError("Assistant-only state should still show examples")

    if (
        _should_show_example_questions(
            [
                ChatMessageModel(
                    role="user",
                    kind="human",
                    content="Summarize the schema.",
                )
            ]
        )
        is not False
    ):
        raise AssertionError("Starter questions should hide after the first user turn")


def test_should_render_chat_message_hides_tool_rows_when_toggle_is_off() -> None:
    """Hide tool transcript rows from the main chat when traces are disabled."""

    tool_message = ChatMessageModel(
        role="tool",
        kind="tool",
        name="describe_table",
        content='{"summary":"Loaded table details."}',
    )

    if _should_render_chat_message(tool_message, show_tool_traces=False) is not False:
        raise AssertionError("Expected the tool row to be hidden")
    if _should_render_chat_message(tool_message, show_tool_traces=True) is not True:
        raise AssertionError("Expected the tool row to be visible")

    assistant_message = ChatMessageModel(
        role="assistant",
        kind="ai",
        content="Here is the answer.",
    )
    if (
        _should_render_chat_message(assistant_message, show_tool_traces=False)
        is not True
    ):
        raise AssertionError("Expected non-tool rows to stay visible")


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
