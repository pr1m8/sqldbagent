"""LangGraph runtime integration tests."""

from __future__ import annotations

from importlib import import_module
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from sqldbagent.core.bootstrap import build_service_container
from tests.helpers import ToolReadyFakeMessagesListChatModel


@pytest.mark.integration
def test_langgraph_runtime_agent_uses_default_runtime_wiring(
    live_postgres_settings,
    live_postgres_demo_settings,
    monkeypatch,
) -> None:
    """Build the runtime agent with default wiring and execute a real tool call."""

    settings = live_postgres_demo_settings.model_copy(
        update={
            "default_datasource_name": "postgres_demo",
            "default_schema_name": "public",
            "agent": live_postgres_demo_settings.agent.model_copy(
                update={
                    "checkpoint": live_postgres_settings.agent.checkpoint.model_copy(
                        update={"backend": "postgres"}
                    )
                }
            ),
        }
    )
    container = build_service_container("postgres_demo", settings=settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot("public", sample_size=1)
        container.snapshotter.save_snapshot(bundle)
    finally:
        container.close()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    runtime_module = import_module("sqldbagent.adapters.langgraph.runtime")
    runtime_module._cleanup_runtime_resources()
    monkeypatch.setattr(
        runtime_module,
        "_build_runtime_model",
        lambda _settings: ToolReadyFakeMessagesListChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "list_tables",
                            "args": {"schema_name": "public"},
                            "id": "call_runtime_list_tables",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="runtime ok"),
            ]
        ),
    )
    try:
        agent = runtime_module.create_runtime_agent(settings=settings)
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "List the public tables and say runtime ok",
                    }
                ]
            },
            config={"configurable": {"thread_id": f"runtime-{uuid4()}"}},
        )
    finally:
        runtime_module._cleanup_runtime_resources()

    tool_messages = [
        message
        for message in result["messages"]
        if getattr(message, "type", None) == "tool"
    ]
    if not tool_messages:
        raise AssertionError(result)
    if "customers" not in str(tool_messages[0].content):
        raise AssertionError(tool_messages[0])
    if result["messages"][-1].content != "runtime ok":
        raise AssertionError(result)
