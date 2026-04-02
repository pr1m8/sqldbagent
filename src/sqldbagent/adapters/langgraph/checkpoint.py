"""LangGraph checkpoint factory helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from sqlalchemy.engine import make_url

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.core.errors import ConfigurationError


def create_memory_checkpointer() -> Any:
    """Create an in-memory LangGraph checkpointer.

    Returns:
        Any: LangGraph in-memory saver.
    """

    memory_module = require_dependency("langgraph.checkpoint.memory", "langgraph")
    return memory_module.InMemorySaver()


@contextmanager
def create_sync_postgres_checkpointer(
    *,
    connection_string: str | None = None,
    settings: AppSettings | None = None,
    auto_setup: bool | None = None,
    pipeline: bool | None = None,
) -> Iterator[Any]:
    """Create a sync Postgres-backed LangGraph checkpointer.

    Args:
        connection_string: Explicit Postgres connection string override.
        settings: Optional application settings.
        auto_setup: Whether to initialize checkpoint tables.
        pipeline: Whether to enable pipelining when supported.

    Yields:
        Any: Sync Postgres saver.
    """

    resolved_settings = settings or load_settings()
    resolved_url = connection_string or resolved_settings.agent.checkpoint.postgres_url
    if not resolved_url:
        raise ConfigurationError("agent checkpoint Postgres URL is not configured")
    resolved_url = _normalize_postgres_checkpoint_url(resolved_url)

    resolved_auto_setup = (
        resolved_settings.agent.checkpoint.auto_setup
        if auto_setup is None
        else auto_setup
    )
    resolved_pipeline = (
        resolved_settings.agent.checkpoint.pipeline if pipeline is None else pipeline
    )
    postgres_module = require_dependency(
        "langgraph.checkpoint.postgres",
        "langgraph-checkpoint-postgres",
    )
    with postgres_module.PostgresSaver.from_conn_string(
        resolved_url,
        pipeline=resolved_pipeline,
    ) as checkpointer:
        if resolved_auto_setup:
            checkpointer.setup()
        yield checkpointer


@asynccontextmanager
async def create_async_postgres_checkpointer(
    *,
    connection_string: str | None = None,
    settings: AppSettings | None = None,
    auto_setup: bool | None = None,
    pipeline: bool | None = None,
) -> AsyncIterator[Any]:
    """Create an async Postgres-backed LangGraph checkpointer.

    Args:
        connection_string: Explicit Postgres connection string override.
        settings: Optional application settings.
        auto_setup: Whether to initialize checkpoint tables.
        pipeline: Whether to enable pipelining when supported.

    Yields:
        Any: Async Postgres saver.
    """

    resolved_settings = settings or load_settings()
    resolved_url = connection_string or resolved_settings.agent.checkpoint.postgres_url
    if not resolved_url:
        raise ConfigurationError("agent checkpoint Postgres URL is not configured")
    resolved_url = _normalize_postgres_checkpoint_url(resolved_url)

    resolved_auto_setup = (
        resolved_settings.agent.checkpoint.auto_setup
        if auto_setup is None
        else auto_setup
    )
    resolved_pipeline = (
        resolved_settings.agent.checkpoint.pipeline if pipeline is None else pipeline
    )
    postgres_module = require_dependency(
        "langgraph.checkpoint.postgres.aio",
        "langgraph-checkpoint-postgres",
    )
    async with postgres_module.AsyncPostgresSaver.from_conn_string(
        resolved_url,
        pipeline=resolved_pipeline,
    ) as checkpointer:
        if resolved_auto_setup:
            await checkpointer.setup()
        yield checkpointer


def _normalize_postgres_checkpoint_url(connection_string: str) -> str:
    """Convert a SQLAlchemy Postgres URL into a psycopg-compatible DSN.

    Args:
        connection_string: Raw configured checkpoint URL.

    Returns:
        str: Connection string usable by psycopg.
    """

    parsed = make_url(connection_string)
    if parsed.drivername == "postgresql+psycopg":
        parsed = parsed.set(drivername="postgresql")
        return parsed.render_as_string(hide_password=False)
    return connection_string
