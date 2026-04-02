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
    """Execute guarded SQL after it passes the safety layer."""

    def __init__(
        self,
        *,
        engine: Engine,
        guard: QueryGuardService,
        async_engine: AsyncEngine | None = None,
        write_engine: Engine | None = None,
        write_async_engine: AsyncEngine | None = None,
    ) -> None:
        """Initialize the safe query service.

        Args:
            engine: Sync SQLAlchemy engine.
            guard: Shared SQL guard service.
            async_engine: Optional async SQLAlchemy engine.
            write_engine: Optional writable sync engine used only when writable
                access is requested explicitly and allowed by policy.
            write_async_engine: Optional writable async engine used only when
                writable access is requested explicitly and allowed by policy.
        """

        self._engine = engine
        self._guard = guard
        self._async_engine = async_engine
        self._write_engine = write_engine
        self._write_async_engine = write_async_engine

    def run(
        self,
        sql: str,
        *,
        max_rows: int | None = None,
        access_mode: str = "read_only",
    ) -> QueryExecutionResult:
        """Guard and execute SQL synchronously.

        Args:
            sql: SQL text to execute.
            max_rows: Optional row-limit override.
            access_mode: Requested execution mode, either `read_only` or
                `writable`.

        Returns:
            QueryExecutionResult: Guard and execution result.
        """

        guard_result = self._guard.guard(
            sql,
            max_rows=max_rows,
            access_mode=access_mode,
        )
        if not guard_result.allowed or guard_result.normalized_sql is None:
            return QueryExecutionResult(
                mode="sync",
                guard=guard_result,
                summary=guard_result.summary,
            )

        started_at = perf_counter()
        engine = self._resolve_sync_engine(access_mode=guard_result.access_mode)
        with engine.begin() as connection:
            result = connection.execute(text(guard_result.normalized_sql))
            rows_affected = self._rows_affected(result)
            if result.returns_rows:
                columns = list(result.keys())
                rows = [
                    {str(key): to_jsonable(value) for key, value in row.items()}
                    for row in result.mappings().all()
                ]
            else:
                columns = []
                rows = []
        duration_ms = round((perf_counter() - started_at) * 1000, 3)

        return QueryExecutionResult(
            mode="sync",
            guard=guard_result,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            rows_affected=rows_affected,
            truncated=bool(
                guard_result.max_rows is not None and len(rows) >= guard_result.max_rows
            ),
            duration_ms=duration_ms,
            summary=self._summarize_result(
                mode="sync",
                row_count=len(rows),
                rows_affected=rows_affected,
                duration_ms=duration_ms,
                guard_summary=guard_result.summary,
            ),
        )

    async def run_async(
        self,
        sql: str,
        *,
        max_rows: int | None = None,
        access_mode: str = "read_only",
    ) -> QueryExecutionResult:
        """Guard and execute SQL asynchronously.

        Args:
            sql: SQL text to execute.
            max_rows: Optional row-limit override.
            access_mode: Requested execution mode, either `read_only` or
                `writable`.

        Returns:
            QueryExecutionResult: Guard and execution result.

        Raises:
            ConfigurationError: If no async engine is configured.
        """

        if self._async_engine is None and access_mode != "writable":
            raise ConfigurationError("async query execution is not configured")
        if self._write_async_engine is None and access_mode == "writable":
            raise ConfigurationError("async writable query execution is not configured")

        guard_result = self._guard.guard(
            sql,
            max_rows=max_rows,
            access_mode=access_mode,
        )
        if not guard_result.allowed or guard_result.normalized_sql is None:
            return QueryExecutionResult(
                mode="async",
                guard=guard_result,
                summary=guard_result.summary,
            )

        started_at = perf_counter()
        engine = self._resolve_async_engine(access_mode=guard_result.access_mode)
        async with engine.begin() as connection:
            result = await connection.execute(text(guard_result.normalized_sql))
            rows_affected = self._rows_affected(result)
            if result.returns_rows:
                columns = list(result.keys())
                rows = [
                    {str(key): to_jsonable(value) for key, value in row.items()}
                    for row in result.mappings().all()
                ]
            else:
                columns = []
                rows = []
        duration_ms = round((perf_counter() - started_at) * 1000, 3)

        return QueryExecutionResult(
            mode="async",
            guard=guard_result,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            rows_affected=rows_affected,
            truncated=bool(
                guard_result.max_rows is not None and len(rows) >= guard_result.max_rows
            ),
            duration_ms=duration_ms,
            summary=self._summarize_result(
                mode="async",
                row_count=len(rows),
                rows_affected=rows_affected,
                duration_ms=duration_ms,
                guard_summary=guard_result.summary,
            ),
        )

    def _summarize_result(
        self,
        *,
        mode: str,
        row_count: int,
        rows_affected: int | None,
        duration_ms: float,
        guard_summary: str | None,
    ) -> str:
        """Build a short human-readable summary for one execution."""

        prefix = guard_summary or "Query executed."
        if rows_affected is not None and row_count == 0:
            return (
                f"{prefix} Execution mode: {mode}. Affected {rows_affected} rows in "
                f"{duration_ms} ms."
            )
        return (
            f"{prefix} Execution mode: {mode}. Returned {row_count} rows in "
            f"{duration_ms} ms."
        )

    def _resolve_sync_engine(self, *, access_mode: str) -> Engine:
        """Resolve the sync engine for the requested access mode."""

        if access_mode == "writable":
            if self._write_engine is None:
                raise ConfigurationError("writable query execution is not configured")
            return self._write_engine
        return self._engine

    def _resolve_async_engine(self, *, access_mode: str) -> AsyncEngine:
        """Resolve the async engine for the requested access mode."""

        if access_mode == "writable":
            if self._write_async_engine is None:
                raise ConfigurationError(
                    "async writable query execution is not configured"
                )
            return self._write_async_engine
        if self._async_engine is None:
            raise ConfigurationError("async query execution is not configured")
        return self._async_engine

    @staticmethod
    def _rows_affected(result: object) -> int | None:
        """Return rows-affected metadata when provided by SQLAlchemy."""

        rowcount = getattr(result, "rowcount", None)
        if isinstance(rowcount, int) and rowcount >= 0:
            return rowcount
        return None
