"""Guarded query execution tests."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from sqldbagent.core.config import SafetySettings
from sqldbagent.core.enums import Dialect
from sqldbagent.safety.execution import SafeQueryService
from sqldbagent.safety.guard import QueryGuardService


def test_safe_query_service_executes_guarded_sync_sql() -> None:
    """Execute guarded read-only SQL through the sync path."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        )
        connection.execute(text("""
                INSERT INTO users (id, email) VALUES
                (1, 'a@example.com'),
                (2, 'b@example.com')
                """))

    service = SafeQueryService(
        engine=engine,
        guard=QueryGuardService(
            policy=SafetySettings(max_rows=10),
            dialect=Dialect.SQLITE,
        ),
    )
    result = service.run("SELECT id, email FROM users ORDER BY id")
    engine.dispose()

    if not result.guard.allowed:
        raise AssertionError(result.guard)
    if result.row_count != 2:
        raise AssertionError(result)
    if result.rows[0]["email"] != "a@example.com":
        raise AssertionError(result.rows)


@pytest.mark.asyncio
async def test_safe_query_service_executes_guarded_async_sql(tmp_path) -> None:
    """Execute guarded read-only SQL through the async path."""

    database_path = tmp_path / "async-query.db"
    sync_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with sync_engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        )
        connection.execute(
            text("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
        )
    sync_engine.dispose()

    sync_engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    service = SafeQueryService(
        engine=sync_engine,
        async_engine=async_engine,
        guard=QueryGuardService(
            policy=SafetySettings(max_rows=10),
            dialect=Dialect.SQLITE,
        ),
    )
    result = await service.run_async("SELECT id, email FROM users")
    await async_engine.dispose()
    sync_engine.dispose()

    if not result.guard.allowed:
        raise AssertionError(result.guard)
    if result.mode != "async":
        raise AssertionError(result.mode)
    if result.row_count != 1:
        raise AssertionError(result)
