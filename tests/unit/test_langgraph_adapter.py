"""LangGraph adapter tests."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage
from sqlalchemy import create_engine, text

from sqldbagent.adapters.langgraph import (
    build_sqldbagent_state_seed,
    create_memory_checkpointer,
    create_sqldbagent_agent,
    create_sqldbagent_middleware,
    create_sqldbagent_system_prompt,
)
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.core.config import (
    AgentCheckpointSettings,
    AgentSettings,
    AppSettings,
    ArtifactSettings,
    DatasourceSettings,
)
from sqldbagent.core.enums import Dialect
from tests.helpers import ToolReadyFakeMessagesListChatModel


def test_langgraph_system_prompt_uses_latest_snapshot_summary(tmp_path: Path) -> None:
    """Include stored snapshot context in the agent prompt when available."""

    database_path = tmp_path / "prompt.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
        )

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path), snapshots_dir="snapshots"),
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(bundle)
    finally:
        container.close()
        engine.dispose()

    prompt = create_sqldbagent_system_prompt(
        datasource_name="sqlite",
        settings=settings,
        schema_name="main",
    )

    if "STORED SNAPSHOT CONTEXT:" not in prompt:
        raise AssertionError(prompt)
    if "Snapshot for datasource 'sqlite' schema 'main'" not in prompt:
        raise AssertionError(prompt)
    if "Table Highlights:" not in prompt:
        raise AssertionError(prompt)


def test_langgraph_system_prompt_merges_saved_prompt_enhancement(
    tmp_path: Path,
) -> None:
    """Merge saved prompt-enhancement context into the dynamic system prompt."""

    database_path = tmp_path / "prompt-enhancement-runtime.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT UNIQUE, tier TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE invoices (id INTEGER PRIMARY KEY, customer_id INTEGER, amount_cents INTEGER)"
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
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        snapshot = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(snapshot)
        enhancement = container.prompt_service.update_prompt_enhancement(
            snapshot,
            active=True,
            user_context="Customers are tenants and invoices reflect subscription billing.",
            business_rules="Treat amount_cents as the authoritative revenue field.",
            answer_style="Prefer concise bullets with explicit evidence.",
            refresh_generated=True,
        )
        container.prompt_service.save_prompt_enhancement(enhancement)
    finally:
        container.close()

    prompt = create_sqldbagent_system_prompt(
        datasource_name="sqlite",
        settings=settings,
        schema_name="main",
    )

    if "DATABASE-SPECIFIC PROMPT ENHANCEMENT:" not in prompt:
        raise AssertionError(prompt)
    if "subscription billing" not in prompt:
        raise AssertionError(prompt)
    if "authoritative revenue field" not in prompt:
        raise AssertionError(prompt)


def test_langgraph_agent_builder_returns_compiled_agent(tmp_path: Path) -> None:
    """Build and run a LangChain v1 agent over sqldbagent tools."""

    database_path = tmp_path / "agent.db"
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
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(backend="memory"),
        ),
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        agent = create_sqldbagent_agent(
            services=container,
            model=ToolReadyFakeMessagesListChatModel(
                responses=[AIMessage(content="done")]
            ),
            datasource_name="sqlite",
            settings=settings,
            checkpointer=create_memory_checkpointer(),
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "Say done"}]},
            config={"configurable": {"thread_id": "unit-langgraph-agent"}},
        )
    finally:
        container.close()

    if agent is None:
        raise AssertionError(agent)
    if result["messages"][-1].content != "done":
        raise AssertionError(result)


def test_langgraph_default_middleware_is_built_from_settings(tmp_path: Path) -> None:
    """Create the repo default LangChain middleware stack."""

    database_path = tmp_path / "agent-middleware.db"
    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(backend="memory"),
            max_model_calls_per_run=3,
            max_tool_calls_per_run=5,
        ),
    )

    middlewares = create_sqldbagent_middleware(
        datasource_name="sqlite",
        settings=settings,
        schema_name="main",
    )

    middleware_names = [middleware.__class__.__name__ for middleware in middlewares]
    if len(middlewares) < 4:
        raise AssertionError(middleware_names)
    if "TodoListMiddleware" not in middleware_names:
        raise AssertionError(middleware_names)
    if "ModelCallLimitMiddleware" not in middleware_names:
        raise AssertionError(middleware_names)
    if "ToolCallLimitMiddleware" not in middleware_names:
        raise AssertionError(middleware_names)


def test_langgraph_state_seed_includes_dashboard_counts(tmp_path: Path) -> None:
    """Seed agent state with dashboard-friendly snapshot counts."""

    database_path = tmp_path / "agent-state.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        )
        connection.execute(
            text("CREATE VIEW active_users AS SELECT id, email FROM users")
        )

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        snapshot = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(snapshot)
    finally:
        container.close()
        engine.dispose()

    state_seed = build_sqldbagent_state_seed(
        datasource_name="sqlite",
        settings=settings,
        schema_name="main",
    )

    cards = state_seed.get("dashboard_payload", {}).get("cards", [])
    card_titles = {card["title"]: card["value"] for card in cards}
    if card_titles.get("Tables") != "1":
        raise AssertionError(cards)
    if card_titles.get("Views") != "1":
        raise AssertionError(cards)
