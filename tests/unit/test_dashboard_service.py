"""Dashboard chat service tests."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage
from sqlalchemy import create_engine, text

from sqldbagent.adapters.langgraph import create_memory_checkpointer
from sqldbagent.core.config import (
    AgentCheckpointSettings,
    AgentSettings,
    AppSettings,
    ArtifactSettings,
    DatasourceSettings,
)
from sqldbagent.core.enums import Dialect
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
