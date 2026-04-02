"""LangGraph Postgres checkpoint integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage

from sqldbagent.adapters.langgraph import (
    create_async_postgres_checkpointed_agent,
    create_sync_postgres_checkpointed_agent,
)
from sqldbagent.core.bootstrap import build_service_container
from tests.helpers import ToolReadyFakeMessagesListChatModel


@pytest.mark.integration
def test_sync_langgraph_agent_uses_actual_postgres_checkpointer(
    live_postgres_settings,
    live_postgres_schema: str,
) -> None:
    """Use the real sync PostgresSaver in an integration flow."""

    container = build_service_container("postgres", settings=live_postgres_settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot(
            live_postgres_schema,
            sample_size=1,
        )
        container.snapshotter.save_snapshot(bundle)
        with create_sync_postgres_checkpointed_agent(
            services=container,
            model=ToolReadyFakeMessagesListChatModel(
                responses=[AIMessage(content="sync agent ok")]
            ),
            datasource_name="postgres",
            settings=live_postgres_settings,
            schema_name=live_postgres_schema,
        ) as agent:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": "Say sync agent ok"}]},
                config={"configurable": {"thread_id": f"sync-{uuid4()}"}},
            )
    finally:
        container.close()

    if "messages" not in result:
        raise AssertionError(result)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_langgraph_agent_uses_actual_postgres_checkpointer(
    live_postgres_settings,
    live_postgres_schema: str,
) -> None:
    """Use the real AsyncPostgresSaver in an integration flow."""

    container = build_service_container(
        "postgres",
        settings=live_postgres_settings,
        include_async_engine=True,
    )
    try:
        bundle = container.snapshotter.create_schema_snapshot(
            live_postgres_schema,
            sample_size=1,
        )
        container.snapshotter.save_snapshot(bundle)
        async with create_async_postgres_checkpointed_agent(
            services=container,
            model=ToolReadyFakeMessagesListChatModel(
                responses=[AIMessage(content="async agent ok")]
            ),
            datasource_name="postgres",
            settings=live_postgres_settings,
            schema_name=live_postgres_schema,
        ) as agent:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": "Say async agent ok"}]},
                config={"configurable": {"thread_id": f"async-{uuid4()}"}},
            )
    finally:
        await container.aclose()

    if "messages" not in result:
        raise AssertionError(result)
