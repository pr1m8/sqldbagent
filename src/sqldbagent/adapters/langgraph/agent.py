"""LangGraph agent builders over the shared sqldbagent services."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Iterator

from sqldbagent.adapters.langchain.tools import create_langchain_tools
from sqldbagent.adapters.langgraph.checkpoint import (
    create_async_postgres_checkpointer,
    create_sync_postgres_checkpointer,
)
from sqldbagent.adapters.langgraph.middleware import create_sqldbagent_middleware
from sqldbagent.adapters.langgraph.prompts import create_sqldbagent_system_prompt
from sqldbagent.adapters.langgraph.state import SQLDBAgentContext, SQLDBAgentState
from sqldbagent.adapters.langgraph.store import (
    create_async_postgres_store,
    create_memory_store,
    create_sync_postgres_store,
)
from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.bootstrap import ServiceContainer
from sqldbagent.core.config import AppSettings, load_settings


def create_sqldbagent_agent(
    *,
    services: ServiceContainer,
    model: str | Any,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
    checkpointer: Any | None = None,
    store: Any | None = None,
    middleware: Sequence[Any] = (),
    include_default_middleware: bool = True,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    debug: bool = False,
) -> Any:
    """Create a LangChain v1 agent compiled on LangGraph.

    Args:
        services: Shared sqldbagent service container.
        model: LangChain-compatible model instance or model identifier.
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.
        checkpointer: Optional LangGraph checkpointer.
        store: Optional LangGraph long-term memory store.
        middleware: Optional additional LangChain middleware chain.
        include_default_middleware: Whether to prepend sqldbagent's default middleware.
        interrupt_before: Optional LangGraph interrupt hook points.
        interrupt_after: Optional LangGraph interrupt hook points.
        debug: Whether LangGraph debug mode should be enabled.

    Returns:
        Any: Compiled LangGraph agent.
    """

    resolved_settings = settings or load_settings()
    agents_module = require_dependency("langchain.agents", "langchain")
    resolved_middleware = list(middleware)
    if include_default_middleware:
        resolved_middleware = [
            *create_sqldbagent_middleware(
                datasource_name=datasource_name,
                settings=resolved_settings,
                schema_name=schema_name,
                services=services,
            ),
            *resolved_middleware,
        ]

    return agents_module.create_agent(
        model=model,
        tools=create_langchain_tools(services),
        system_prompt=(
            None
            if include_default_middleware
            else create_sqldbagent_system_prompt(
                datasource_name=datasource_name,
                settings=resolved_settings,
                schema_name=schema_name,
            )
        ),
        middleware=resolved_middleware,
        state_schema=SQLDBAgentState,
        context_schema=SQLDBAgentContext,
        checkpointer=checkpointer,
        store=store,
        interrupt_before=interrupt_before,
        interrupt_after=interrupt_after,
        debug=debug,
        name=resolved_settings.agent.name,
    )


@contextmanager
def create_sync_postgres_checkpointed_agent(
    *,
    services: ServiceContainer,
    model: str | Any,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
    middleware: Sequence[Any] = (),
    include_default_middleware: bool = True,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    debug: bool = False,
) -> Iterator[Any]:
    """Create a sync LangGraph agent with Postgres-backed checkpointing.

    Args:
        services: Shared sqldbagent service container.
        model: LangChain-compatible model instance or model identifier.
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.
        middleware: Optional additional LangChain middleware chain.
        include_default_middleware: Whether to prepend sqldbagent's default middleware.
        interrupt_before: Optional LangGraph interrupt hook points.
        interrupt_after: Optional LangGraph interrupt hook points.
        debug: Whether LangGraph debug mode should be enabled.

    Yields:
        Any: Compiled LangGraph agent.
    """

    resolved_settings = settings or load_settings()
    with create_sync_postgres_checkpointer(settings=resolved_settings) as checkpointer:
        with _configured_sync_store(settings=resolved_settings) as store:
            yield create_sqldbagent_agent(
                services=services,
                model=model,
                datasource_name=datasource_name,
                settings=resolved_settings,
                schema_name=schema_name,
                checkpointer=checkpointer,
                store=store,
                middleware=middleware,
                include_default_middleware=include_default_middleware,
                interrupt_before=interrupt_before,
                interrupt_after=interrupt_after,
                debug=debug,
            )


@asynccontextmanager
async def create_async_postgres_checkpointed_agent(
    *,
    services: ServiceContainer,
    model: str | Any,
    datasource_name: str,
    settings: AppSettings | None = None,
    schema_name: str | None = None,
    middleware: Sequence[Any] = (),
    include_default_middleware: bool = True,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    debug: bool = False,
) -> AsyncIterator[Any]:
    """Create an async LangGraph agent with Postgres-backed checkpointing.

    Args:
        services: Shared sqldbagent service container.
        model: LangChain-compatible model instance or model identifier.
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        schema_name: Optional schema focus.
        middleware: Optional additional LangChain middleware chain.
        include_default_middleware: Whether to prepend sqldbagent's default middleware.
        interrupt_before: Optional LangGraph interrupt hook points.
        interrupt_after: Optional LangGraph interrupt hook points.
        debug: Whether LangGraph debug mode should be enabled.

    Yields:
        Any: Compiled LangGraph agent.
    """

    resolved_settings = settings or load_settings()
    async with create_async_postgres_checkpointer(
        settings=resolved_settings
    ) as checkpointer:
        async with _configured_async_store(settings=resolved_settings) as store:
            yield create_sqldbagent_agent(
                services=services,
                model=model,
                datasource_name=datasource_name,
                settings=resolved_settings,
                schema_name=schema_name,
                checkpointer=checkpointer,
                store=store,
                middleware=middleware,
                include_default_middleware=include_default_middleware,
                interrupt_before=interrupt_before,
                interrupt_after=interrupt_after,
                debug=debug,
            )


@contextmanager
def _configured_sync_store(*, settings: AppSettings) -> Iterator[Any | None]:
    """Yield the configured sync LangGraph store for the current settings."""

    backend = settings.agent.memory.backend
    if backend == "disabled":
        yield None
        return
    if backend == "postgres" and settings.agent.memory.postgres_url is not None:
        with create_sync_postgres_store(settings=settings) as store:
            yield store
        return
    yield create_memory_store()


@asynccontextmanager
async def _configured_async_store(
    *, settings: AppSettings
) -> AsyncIterator[Any | None]:
    """Yield the configured async LangGraph store for the current settings."""

    backend = settings.agent.memory.backend
    if backend == "disabled":
        yield None
        return
    if backend == "postgres" and settings.agent.memory.postgres_url is not None:
        async with create_async_postgres_store(settings=settings) as store:
            yield store
        return
    yield create_memory_store()
