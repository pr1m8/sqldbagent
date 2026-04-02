"""Dashboard chat service tests."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, text

from sqldbagent.adapters.langgraph import create_memory_checkpointer
from sqldbagent.adapters.langgraph.memory import load_database_memory
from sqldbagent.adapters.langgraph.store import create_memory_store
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.core.config import (
    AgentCheckpointSettings,
    AgentSettings,
    AppSettings,
    ArtifactSettings,
    DatasourceSettings,
)
from sqldbagent.core.enums import Dialect
from sqldbagent.dashboard.models import ChatMessageModel
from sqldbagent.dashboard.service import DashboardChatService
from sqldbagent.prompts.models import PromptBundleModel
from tests.helpers import ToolReadyFakeMessagesListChatModel


def test_dashboard_chat_service_persists_thread_with_reused_checkpointer(
    tmp_path: Path,
) -> None:
    """Persist a thread across multiple dashboard turns with the same saver."""

    database_path = tmp_path / "dashboard-chat.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(backend="memory"),
        ),
        default_schema_name="main",
    )
    service = DashboardChatService(
        settings=settings,
        model=ToolReadyFakeMessagesListChatModel(
            responses=[
                AIMessage(content="first reply"),
                AIMessage(content="second reply"),
            ]
        ),
        checkpointer=create_memory_checkpointer(),
    )

    first = service.run_turn(
        thread_id="thread-1",
        user_message="hello",
        datasource_name="sqlite",
        schema_name="main",
    )
    loaded = service.load_thread(
        thread_id="thread-1",
        datasource_name="sqlite",
        schema_name="main",
    )
    second = service.run_turn(
        thread_id="thread-1",
        user_message="again",
        datasource_name="sqlite",
        schema_name="main",
    )

    if first.messages[-1].content != "first reply":
        raise AssertionError(first.messages)
    if loaded.messages[-1].content != "first reply":
        raise AssertionError(loaded.messages)
    if second.messages[-1].content != "second reply":
        raise AssertionError(second.messages)
    user_messages = [message for message in second.messages if message.role == "user"]
    if len(user_messages) != 2:
        raise AssertionError(second.messages)


def test_dashboard_chat_service_renders_tool_call_placeholder() -> None:
    """Render AI tool-call planning messages into readable assistant text."""

    service = DashboardChatService(settings=AppSettings(datasources=[]))
    session = service._session_from_values(  # noqa: SLF001
        thread_id="thread-2",
        datasource_name="demo",
        schema_name="public",
        values={
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "list_tables", "args": {}, "id": "call-1"}],
                )
            ]
        },
    )

    if session.messages[0].content != "Calling tools: list_tables":
        raise AssertionError(session.messages)


def test_dashboard_chat_service_emits_progress_events(tmp_path: Path) -> None:
    """Emit readable progress events while a turn is running."""

    database_path = tmp_path / "dashboard-progress.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(backend="memory"),
        ),
        default_schema_name="main",
    )
    service = DashboardChatService(
        settings=settings,
        model=ToolReadyFakeMessagesListChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "list_tables",
                            "args": {"schema_name": "main"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="done"),
            ]
        ),
        checkpointer=create_memory_checkpointer(),
    )

    events: list[str] = []
    session = service.run_turn(
        thread_id="thread-progress",
        user_message="what tables exist?",
        datasource_name="sqlite",
        schema_name="main",
        progress_callback=lambda event: events.append(event.label),
    )

    if not any("Planning tool calls" in event for event in events):
        raise AssertionError(events)
    if not any("Completed tool: list_tables" in event for event in events):
        raise AssertionError(events)
    if events[-1] != "Agent turn complete.":
        raise AssertionError(events)
    if session.messages[-1].content != "done":
        raise AssertionError(session.messages)


def test_dashboard_chat_service_surfaces_observability_settings() -> None:
    """Expose checkpoint and LangSmith status for dashboard rendering."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="postgres_demo",
                dialect=Dialect.POSTGRES,
                url="postgresql+psycopg://demo:demo@127.0.0.1:5432/demo",
            )
        ],
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(
                backend="postgres",
                postgres_url="postgresql+psycopg://demo:demo@127.0.0.1:5432/checkpoints",
            ),
        ),
        langsmith={
            "tracing": True,
            "project": "sqldbagent-dev",
            "api_key": "langsmith-test-key",
            "tags": ["sqldbagent", "dashboard"],
        },
    )
    service = DashboardChatService(settings=settings)
    session = service._session_from_values(  # noqa: SLF001
        thread_id="thread-3",
        datasource_name="postgres_demo",
        schema_name="public",
        values={"messages": []},
    )

    observability = session.observability
    if observability.get("checkpoint_backend") != "postgres":
        raise AssertionError(observability)
    if observability.get("checkpoint_is_durable") is not True:
        raise AssertionError(observability)
    if observability.get("langsmith_project") != "sqldbagent-dev":
        raise AssertionError(observability)
    if observability.get("langsmith_tracing") is not True:
        raise AssertionError(observability)
    if "Postgres read-only transactions" not in str(
        observability.get("database_access_summary")
    ):
        raise AssertionError(observability)


def test_dashboard_chat_service_surfaces_checkpoint_fallback_status() -> None:
    """Report when Postgres checkpointing is requested but unavailable."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url="sqlite+pysqlite:////tmp/demo.db",
            )
        ],
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(backend="postgres"),
        ),
        postgres_host=None,
        postgres_db=None,
        postgres_user=None,
        postgres_password=None,
    )
    service = DashboardChatService(settings=settings)
    session = service._session_from_values(  # noqa: SLF001
        thread_id="thread-fallback",
        datasource_name="sqlite",
        schema_name="main",
        values={"messages": []},
    )

    observability = session.observability
    if observability.get("checkpoint_backend") != "memory":
        raise AssertionError(observability)
    if observability.get("checkpoint_status") != "fallback":
        raise AssertionError(observability)
    if "fell back" not in str(observability.get("checkpoint_summary")):
        raise AssertionError(observability)
    if "PRAGMA query_only" not in str(observability.get("database_access_summary")):
        raise AssertionError(observability)


def test_dashboard_chat_service_persists_thread_registry_entries(
    tmp_path: Path,
) -> None:
    """Persist thread summaries for later thread selection in the dashboard."""

    settings = AppSettings(
        datasources=[],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
    )
    service = DashboardChatService(settings=settings)
    session = service._session_from_values(  # noqa: SLF001
        thread_id="thread-registry-1",
        datasource_name="postgres_demo",
        schema_name="public",
        values={
            "messages": [
                AIMessage(content="dashboard reply"),
            ],
            "latest_snapshot_id": "snapshot-1",
        },
    ).model_copy(
        update={
            "messages": [
                *service._session_from_values(  # noqa: SLF001
                    thread_id="thread-registry-1",
                    datasource_name="postgres_demo",
                    schema_name="public",
                    values={
                        "messages": [
                            AIMessage(content="dashboard reply"),
                        ],
                    },
                ).messages,
            ]
        }
    )
    session.messages.insert(
        0,
        ChatMessageModel(
            role="user",
            content="Inspect the schema and summarize it.",
            kind="human",
        ),
    )

    service._upsert_thread_entry(session)  # noqa: SLF001
    entries = service.list_threads(
        datasource_name="postgres_demo",
        schema_name="public",
    )

    if len(entries) != 1:
        raise AssertionError(entries)
    entry = entries[0]
    if entry.thread_id != "thread-registry-1":
        raise AssertionError(entry)


def test_dashboard_chat_service_explores_prompt_context_and_syncs_memory(
    tmp_path: Path,
) -> None:
    """Save live prompt exploration and mirror a concise summary into memory."""

    database_path = tmp_path / "dashboard-explore.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, segment TEXT, status TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO customers (id, segment, status) VALUES "
                "(1, 'enterprise', 'active'), (2, 'smb', 'active'), (3, 'smb', 'paused')"
            )
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        default_schema_name="main",
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        snapshot = container.snapshotter.create_schema_snapshot("main", sample_size=2)
        container.snapshotter.save_snapshot(snapshot)
    finally:
        container.close()

    store = create_memory_store()
    service = DashboardChatService(
        settings=settings,
        store=store,
    )
    bundle = service.explore_prompt_bundle_context(
        datasource_name="sqlite",
        schema_name="main",
        table_names=["customers"],
        max_tables=1,
        unique_value_limit=4,
        sync_memory=True,
    )

    if not isinstance(bundle, PromptBundleModel):
        raise AssertionError(bundle)
    if bundle.enhancement is None or bundle.enhancement.exploration is None:
        raise AssertionError(bundle.model_dump())
    if "LIVE EXPLORED CONTEXT:" not in bundle.system_prompt:
        raise AssertionError(bundle.system_prompt)
    if "filters.segment" not in bundle.system_prompt:
        raise AssertionError(bundle.system_prompt)
    memory_record = load_database_memory(
        store,
        settings=settings,
        datasource_name="sqlite",
        schema_name="main",
    )
    if memory_record is None or "Explored 1 table" not in str(memory_record.summary):
        raise AssertionError(memory_record)


def test_dashboard_chat_service_updates_thread_display_name(
    tmp_path: Path,
) -> None:
    """Persist an optional display name for saved dashboard threads."""

    settings = AppSettings(
        datasources=[],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
    )
    service = DashboardChatService(settings=settings)
    session = service._session_from_values(  # noqa: SLF001
        thread_id="thread-registry-2",
        datasource_name="postgres_demo",
        schema_name="public",
        values={
            "messages": [
                AIMessage(content="dashboard reply"),
            ],
        },
    )

    service._upsert_thread_entry(session)  # noqa: SLF001
    updated = service.update_thread_display_name(
        thread_id="thread-registry-2",
        datasource_name="postgres_demo",
        schema_name="public",
        display_name="Demo Lifecycle Thread",
    )

    if updated is None or updated.display_name != "Demo Lifecycle Thread":
        raise AssertionError(updated)
    entries = service.list_threads(
        datasource_name="postgres_demo",
        schema_name="public",
    )
    if entries[0].display_name != "Demo Lifecycle Thread":
        raise AssertionError(entries)


def test_dashboard_chat_service_loads_artifact_bundles_from_snapshot(
    tmp_path: Path,
) -> None:
    """Load or create prompt and diagram bundles from the latest saved snapshot."""

    database_path = tmp_path / "dashboard-artifacts.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT, tier TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO customers (email, tier) VALUES "
                "('a@example.com', 'gold'), ('b@example.com', 'silver')"
            )
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        default_schema_name="main",
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(bundle)
    finally:
        container.close()

    service = DashboardChatService(settings=settings)
    diagram_bundle = service._load_or_create_diagram_bundle(  # noqa: SLF001
        datasource_name="sqlite",
        schema_name="main",
        values={"latest_snapshot_id": bundle.snapshot_id},
    )
    prompt_bundle = service._load_or_create_prompt_bundle(  # noqa: SLF001
        datasource_name="sqlite",
        schema_name="main",
        values={"latest_snapshot_id": bundle.snapshot_id},
    )

    if diagram_bundle is None or "erDiagram" not in diagram_bundle.mermaid_erd:
        raise AssertionError(diagram_bundle)
    if prompt_bundle is None or prompt_bundle.snapshot_id != bundle.snapshot_id:
        raise AssertionError(prompt_bundle)


def test_dashboard_chat_service_regenerates_stale_diagram_bundle(
    tmp_path: Path,
) -> None:
    """Regenerate stale stored diagram bundles from the latest snapshot."""

    database_path = tmp_path / "dashboard-diagram-regenerate.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)"
            )
        )
        connection.execute(text("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    team_id INTEGER NOT NULL REFERENCES teams(id),
                    email TEXT
                )
                """))
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        default_schema_name="main",
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(bundle)
        diagram_bundle = container.diagram_service.create_diagram_bundle(bundle)
        stale_bundle = diagram_bundle.model_copy(
            update={
                "mermaid_erd": "erDiagram\n  %% stale comment-based bundle",
                "content_hash": "stale",
            }
        )
        container.diagram_service.save_diagram_bundle(stale_bundle)
    finally:
        container.close()

    service = DashboardChatService(settings=settings)
    refreshed_bundle = service._load_or_create_diagram_bundle(  # noqa: SLF001
        datasource_name="sqlite",
        schema_name="main",
        values={"latest_snapshot_id": bundle.snapshot_id},
    )

    if refreshed_bundle is None:
        raise AssertionError("Expected a refreshed diagram bundle.")
    if "%% stale comment-based bundle" in refreshed_bundle.mermaid_erd:
        raise AssertionError(refreshed_bundle.mermaid_erd)
    if "direction LR" not in refreshed_bundle.mermaid_erd:
        raise AssertionError(refreshed_bundle.mermaid_erd)


def test_dashboard_chat_service_refreshes_prompt_bundle_context(
    tmp_path: Path,
) -> None:
    """Refresh generated schema context from the latest stored snapshot."""

    database_path = tmp_path / "dashboard-prompt-refresh.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT, tier TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO customers (email, tier) VALUES "
                "('a@example.com', 'gold'), ('b@example.com', 'silver')"
            )
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        default_schema_name="main",
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(bundle)
    finally:
        container.close()

    service = DashboardChatService(settings=settings)
    prompt_bundle = service.refresh_prompt_bundle_context(
        datasource_name="sqlite",
        schema_name="main",
    )

    if prompt_bundle is None:
        raise AssertionError("Expected a refreshed prompt bundle")
    enhancement = prompt_bundle.enhancement
    if enhancement is None or not enhancement.generated_context.strip():
        raise AssertionError(prompt_bundle)


def test_dashboard_chat_service_ensures_retrieval_index(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Build and return a retrieval manifest for the active snapshot."""

    database_path = tmp_path / "dashboard-retrieval.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT, tier TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO customers (email, tier) VALUES "
                "('a@example.com', 'gold'), ('b@example.com', 'silver')"
            )
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        embeddings={"provider": "hash", "dimensions": 64},
        retrieval={"qdrant_url": "http://127.0.0.1:6333"},
        default_schema_name="main",
    )
    snapshot_container = build_service_container("sqlite", settings=settings)
    try:
        bundle = snapshot_container.snapshotter.create_schema_snapshot(
            "main", sample_size=1
        )
        snapshot_container.snapshotter.save_snapshot(bundle)
    finally:
        snapshot_container.close()

    original_build_service_container = build_service_container

    def build_test_container(
        datasource_name: str,
        settings: AppSettings | None = None,
        **kwargs,
    ):
        container = original_build_service_container(
            datasource_name,
            settings=settings,
            **kwargs,
        )
        if container.retrieval_service is not None:
            container.retrieval_service._client = QdrantClient(
                location=":memory:"
            )  # noqa: SLF001
        return container

    monkeypatch.setattr(
        "sqldbagent.dashboard.service.build_service_container",
        build_test_container,
    )

    service = DashboardChatService(settings=settings)
    manifest = service.ensure_retrieval_index(
        datasource_name="sqlite",
        schema_name="main",
    )
    loaded = service.load_thread(
        thread_id="thread-retrieval",
        datasource_name="sqlite",
        schema_name="main",
    )

    if manifest is None or manifest.document_count <= 0:
        raise AssertionError(manifest)
    if loaded.retrieval_manifest is None:
        raise AssertionError(loaded)


def test_dashboard_chat_service_runs_guarded_sync_query(
    tmp_path: Path,
) -> None:
    """Run a guarded read-only query through the dashboard service."""

    database_path = tmp_path / "dashboard-query-sync.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        )
        connection.execute(
            text(
                "INSERT INTO users (id, email) VALUES "
                "(1, 'a@example.com'),"
                "(2, 'b@example.com')"
            )
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        default_schema_name="main",
    )
    service = DashboardChatService(settings=settings)

    result = service.run_safe_query(
        datasource_name="sqlite",
        sql="SELECT id, email FROM users ORDER BY id",
        max_rows=10,
        mode="sync",
    )

    if not result.guard.allowed:
        raise AssertionError(result.guard)
    if result.row_count != 2:
        raise AssertionError(result)
    if result.rows[0]["email"] != "a@example.com":
        raise AssertionError(result.rows)


def test_dashboard_chat_service_runs_guarded_async_query(
    tmp_path: Path,
) -> None:
    """Run the async guarded query path through the dashboard service."""

    database_path = tmp_path / "dashboard-query-async.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        )
        connection.execute(
            text("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        default_schema_name="main",
    )
    service = DashboardChatService(settings=settings)

    result = service.run_safe_query(
        datasource_name="sqlite",
        sql="SELECT id, email FROM users",
        max_rows=10,
        mode="async",
    )

    if not result.guard.allowed:
        raise AssertionError(result.guard)
    if result.mode != "async":
        raise AssertionError(result.mode)
    if result.row_count != 1:
        raise AssertionError(result)


def test_dashboard_chat_service_builds_example_questions_from_snapshot(
    tmp_path: Path,
) -> None:
    """Build snapshot-aware starter questions for the dashboard chat."""

    database_path = tmp_path / "dashboard-example-questions.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT UNIQUE, tier TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total_cents INTEGER, "
                "FOREIGN KEY(customer_id) REFERENCES customers(id))"
            )
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        default_schema_name="main",
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(bundle)
    finally:
        container.close()

    service = DashboardChatService(settings=settings)
    session = service._session_from_values(  # noqa: SLF001
        thread_id="example-questions-thread",
        datasource_name="sqlite",
        schema_name="main",
        values={"latest_snapshot_id": bundle.snapshot_id, "messages": []},
    )

    if not session.example_questions:
        raise AssertionError(session.model_dump())
    if not any("customers" in question for question in session.example_questions):
        raise AssertionError(session.example_questions)
    if not any("join path" in question for question in session.example_questions):
        raise AssertionError(session.example_questions)


def test_dashboard_chat_service_updates_prompt_enhancement(
    tmp_path: Path,
) -> None:
    """Update prompt enhancement state through the dashboard service layer."""

    database_path = tmp_path / "dashboard-prompt-enhancement.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT UNIQUE, tier TEXT)"
            )
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        default_schema_name="main",
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        snapshot = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(snapshot)
    finally:
        container.close()

    service = DashboardChatService(settings=settings)
    bundle = service.update_prompt_bundle_enhancement(
        datasource_name="sqlite",
        schema_name="main",
        active=True,
        user_context="Customers are subscription tenants.",
        business_rules="Tier drives commercial segmentation.",
        additional_effective_context=(
            "Call out whether each answer section comes from snapshots, retrieval, or live SQL."
        ),
        answer_style="Use short bullets and evidence.",
        refresh_generated=True,
    )

    if bundle is None:
        raise AssertionError(bundle)
    if bundle.enhancement is None:
        raise AssertionError(bundle.model_dump())
    if bundle.enhancement.user_context != "Customers are subscription tenants.":
        raise AssertionError(bundle.enhancement.model_dump())
    if bundle.enhancement.additional_effective_context is None:
        raise AssertionError(bundle.enhancement.model_dump())
    if "subscription tenants" not in bundle.system_prompt:
        raise AssertionError(bundle.system_prompt)
    if "Call out whether each answer section" not in bundle.system_prompt:
        raise AssertionError(bundle.system_prompt)


def test_dashboard_chat_service_builds_demo_specific_example_questions(
    tmp_path: Path,
) -> None:
    """Prefer richer starter questions when the bundled demo schema is present."""

    database_path = tmp_path / "dashboard-demo-example-questions.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, customer_code TEXT, segment TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT, category TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, order_number TEXT, "
                "FOREIGN KEY(customer_id) REFERENCES customers(id))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER, "
                "FOREIGN KEY(order_id) REFERENCES orders(id), "
                "FOREIGN KEY(product_id) REFERENCES products(id))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE support_tickets (id INTEGER PRIMARY KEY, customer_id INTEGER, ticket_number TEXT, "
                "FOREIGN KEY(customer_id) REFERENCES customers(id))"
            )
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
        default_schema_name="main",
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(bundle)
    finally:
        container.close()

    service = DashboardChatService(settings=settings)
    session = service._session_from_values(  # noqa: SLF001
        thread_id="demo-example-questions-thread",
        datasource_name="sqlite",
        schema_name="main",
        values={"latest_snapshot_id": bundle.snapshot_id, "messages": []},
    )

    if not any(
        "customer lifecycle" in question for question in session.example_questions
    ):
        raise AssertionError(session.example_questions)
    if not any(
        "support-ticket patterns" in question for question in session.example_questions
    ):
        raise AssertionError(session.example_questions)
