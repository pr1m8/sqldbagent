"""Guarded sync and async SQL execution services."""

from __future__ import annotations

from time import perf_counter

from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncEngine

from sqldbagent.core.errors import ConfigurationError
from sqldbagent.core.models.query import QueryExecutionResult
from sqldbagent.core.serialization import to_jsonable
from sqldbagent.safety.guard import QueryGuardService


class SafeQueryService:
    """Execute read-only SQL only after it passes the guard layer."""

    def __init__(
        self,
        *,
        engine: Engine,
        guard: QueryGuardService,
        async_engine: AsyncEngine | None = None,
    ) -> None:
        """Initialize the safe query service.

        Args:
            engine: Sync SQLAlchemy engine.
            guard: Shared SQL guard service.
            async_engine: Optional async SQLAlchemy engine.
        """

        self._engine = engine
        self._guard = guard
        self._async_engine = async_engine

    def run(self, sql: str, *, max_rows: int | None = None) -> QueryExecutionResult:
        """Guard and execute SQL synchronously.

        Args:
            sql: SQL text to execute.
            max_rows: Optional row-limit override.

        Returns:
            QueryExecutionResult: Guard and execution result.
        """

        guard_result = self._guard.guard(sql, max_rows=max_rows)
        if not guard_result.allowed or guard_result.normalized_sql is None:
            return QueryExecutionResult(
                mode="sync",
                guard=guard_result,
                summary=guard_result.summary,
            )

        started_at = perf_counter()
        with self._engine.connect() as connection:
            result = connection.execute(text(guard_result.normalized_sql))
            columns = list(result.keys())
            rows = [
                {str(key): to_jsonable(value) for key, value in row.items()}
                for row in result.mappings().all()
            ]
        duration_ms = round((perf_counter() - started_at) * 1000, 3)

        return QueryExecutionResult(
            mode="sync",
            guard=guard_result,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=bool(
                guard_result.max_rows is not None and len(rows) >= guard_result.max_rows
            ),
            duration_ms=duration_ms,
            summary=self._summarize_result(
                mode="sync",
                row_count=len(rows),
                duration_ms=duration_ms,
                guard_summary=guard_result.summary,
            ),
        )

    async def run_async(
        self,
        sql: str,
        *,
        max_rows: int | None = None,
    ) -> QueryExecutionResult:
        """Guard and execute SQL asynchronously.

        Args:
            sql: SQL text to execute.
            max_rows: Optional row-limit override.

        Returns:
            QueryExecutionResult: Guard and execution result.

        Raises:
            ConfigurationError: If no async engine is configured.
        """

        if self._async_engine is None:
            raise ConfigurationError("async query execution is not configured")

        guard_result = self._guard.guard(sql, max_rows=max_rows)
        if not guard_result.allowed or guard_result.normalized_sql is None:
            return QueryExecutionResult(
                mode="async",
                guard=guard_result,
                summary=guard_result.summary,
            )

        started_at = perf_counter()
        async with self._async_engine.connect() as connection:
            result = await connection.execute(text(guard_result.normalized_sql))
            columns = list(result.keys())
            rows = [
                {str(key): to_jsonable(value) for key, value in row.items()}
                for row in result.mappings().all()
            ]
        duration_ms = round((perf_counter() - started_at) * 1000, 3)

        return QueryExecutionResult(
            mode="async",
            guard=guard_result,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=bool(
                guard_result.max_rows is not None and len(rows) >= guard_result.max_rows
            ),
            duration_ms=duration_ms,
            summary=self._summarize_result(
                mode="async",
                row_count=len(rows),
                duration_ms=duration_ms,
                guard_summary=guard_result.summary,
            ),
        )

    def _summarize_result(
        self,
        *,
        mode: str,
        row_count: int,
        duration_ms: float,
        guard_summary: str | None,
    ) -> str:
        """Build a short human-readable summary for one execution."""

        prefix = guard_summary or "Query executed."
        return (
            f"{prefix} Execution mode: {mode}. Returned {row_count} rows in "
            f"{duration_ms} ms."
        )
