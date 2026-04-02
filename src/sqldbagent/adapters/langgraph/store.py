"""LangGraph long-term memory store factory helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from sqlalchemy.engine import make_url

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.core.errors import ConfigurationError


def create_memory_store() -> Any:
    """Create an in-memory LangGraph store.

    Returns:
        Any: LangGraph in-memory store.
    """

    memory_module = require_dependency("langgraph.store.memory", "langgraph")
    return memory_module.InMemoryStore()


@contextmanager
def create_sync_postgres_store(
    *,
    connection_string: str | None = None,
    settings: AppSettings | None = None,
    auto_setup: bool | None = None,
    pipeline: bool | None = None,
) -> Iterator[Any]:
    """Create a sync Postgres-backed LangGraph long-term memory store.

    Args:
        connection_string: Explicit Postgres connection string override.
        settings: Optional application settings.
        auto_setup: Whether to initialize store tables.
        pipeline: Whether to enable pipelining when supported.

    Yields:
        Any: Sync Postgres store.
    """

    resolved_settings = settings or load_settings()
    resolved_url = connection_string or resolved_settings.agent.memory.postgres_url
    if not resolved_url:
        raise ConfigurationError("agent memory Postgres URL is not configured")
    resolved_url = _normalize_postgres_store_url(resolved_url)

    resolved_auto_setup = (
        resolved_settings.agent.memory.auto_setup if auto_setup is None else auto_setup
    )
    resolved_pipeline = (
        resolved_settings.agent.memory.pipeline if pipeline is None else pipeline
    )
    postgres_module = require_dependency(
        "langgraph.store.postgres",
        "langgraph-checkpoint-postgres",
    )
    with postgres_module.PostgresStore.from_conn_string(
        resolved_url,
        pipeline=resolved_pipeline,
    ) as store:
        if resolved_auto_setup:
            store.setup()
        yield store


@asynccontextmanager
async def create_async_postgres_store(
    *,
    connection_string: str | None = None,
    settings: AppSettings | None = None,
    auto_setup: bool | None = None,
    pipeline: bool | None = None,
) -> AsyncIterator[Any]:
    """Create an async Postgres-backed LangGraph long-term memory store.

    Args:
        connection_string: Explicit Postgres connection string override.
        settings: Optional application settings.
        auto_setup: Whether to initialize store tables.
        pipeline: Whether to enable pipelining when supported.

    Yields:
        Any: Async Postgres store.
    """

    resolved_settings = settings or load_settings()
    resolved_url = connection_string or resolved_settings.agent.memory.postgres_url
    if not resolved_url:
        raise ConfigurationError("agent memory Postgres URL is not configured")
    resolved_url = _normalize_postgres_store_url(resolved_url)

    resolved_auto_setup = (
        resolved_settings.agent.memory.auto_setup if auto_setup is None else auto_setup
    )
    resolved_pipeline = (
        resolved_settings.agent.memory.pipeline if pipeline is None else pipeline
    )
    postgres_module = require_dependency(
        "langgraph.store.postgres",
        "langgraph-checkpoint-postgres",
    )
    async with postgres_module.AsyncPostgresStore.from_conn_string(
        resolved_url,
        pipeline=resolved_pipeline,
    ) as store:
        if resolved_auto_setup:
            await store.setup()
        yield store


@asynccontextmanager
async def generate_store() -> AsyncIterator[Any]:
    """Yield the configured store for LangGraph CLI and LangSmith runtimes.

    Returns:
        AsyncIterator[Any]: Async context manager yielding a configured store.
    """

    settings = load_settings()
    if settings.agent.memory.backend == "postgres":
        async with create_async_postgres_store(settings=settings) as store:
            yield store
        return
    yield create_memory_store()


def _normalize_postgres_store_url(connection_string: str) -> str:
    """Convert a SQLAlchemy Postgres URL into a psycopg-compatible DSN.

    Args:
        connection_string: Raw configured store URL.

    Returns:
        str: Connection string usable by psycopg.
    """

    parsed = make_url(connection_string)
    if parsed.drivername == "postgresql+psycopg":
        parsed = parsed.set(drivername="postgresql")
        return parsed.render_as_string(hide_password=False)
    return connection_string
