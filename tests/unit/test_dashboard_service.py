"""Dashboard chat service tests."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage
from sqlalchemy import create_engine, text

from sqldbagent.adapters.langgraph import create_memory_checkpointer
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


def test_dashboard_chat_service_surfaces_observability_settings() -> None:
    """Expose checkpoint and LangSmith status for dashboard rendering."""

    settings = AppSettings(
        datasources=[],
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(backend="postgres"),
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
    if observability.get("langsmith_project") != "sqldbagent-dev":
        raise AssertionError(observability)
    if observability.get("langsmith_tracing") is not True:
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
    if entry.latest_snapshot_id != "snapshot-1":
        raise AssertionError(entry)


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
    if "Mission: safe database intelligence" not in service.render_prompt_markdown(
        prompt_bundle
    ):
        raise AssertionError(prompt_bundle)


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
        answer_style="Use short bullets and evidence.",
        refresh_generated=True,
    )

    if bundle is None:
        raise AssertionError(bundle)
    if bundle.enhancement is None:
        raise AssertionError(bundle.model_dump())
    if bundle.enhancement.user_context != "Customers are subscription tenants.":
        raise AssertionError(bundle.enhancement.model_dump())
    if "subscription tenants" not in bundle.system_prompt:
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
