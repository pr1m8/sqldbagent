"""Query CLI commands."""

from __future__ import annotations

import asyncio

import orjson

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container

typer = load_typer()
app = typer.Typer(help="Query analysis commands.")


@app.command("lint")
def lint(datasource: str, sql: str) -> None:
    """Lint SQL against the datasource dialect.

    Args:
        datasource: Datasource identifier.
        sql: SQL text to lint.
    """

    container = build_service_container(datasource)
    try:
        result = container.query_guard.lint(sql)
    finally:
        container.close()

    typer.echo(result.model_dump_json(indent=2))
    if not result.allowed:
        raise typer.Exit(code=2)


@app.command("guard")
def guard(
    datasource: str,
    sql: str,
    access_mode: str = "read_only",
) -> None:
    """Guard SQL under the datasource safety policy.

    Args:
        datasource: Datasource identifier.
        sql: SQL text to guard.
        access_mode: Requested execution mode, either `read_only` or `writable`.
    """

    container = build_service_container(datasource)
    try:
        result = container.query_guard.guard(sql, access_mode=access_mode)
    finally:
        container.close()

    typer.echo(result.model_dump_json(indent=2))
    if not result.allowed:
        raise typer.Exit(code=2)


@app.command("run")
def run(
    datasource: str,
    sql: str,
    max_rows: int | None = None,
    access_mode: str = "read_only",
) -> None:
    """Guard and execute SQL synchronously.

    Args:
        datasource: Datasource identifier.
        sql: SQL text to execute.
        max_rows: Optional row-limit override.
        access_mode: Requested execution mode, either `read_only` or `writable`.
    """

    container = build_service_container(datasource)
    try:
        result = container.query_service.run(
            sql,
            max_rows=max_rows,
            access_mode=access_mode,
        )
    finally:
        container.close()

    typer.echo(result.model_dump_json(indent=2))
    if not result.guard.allowed:
        raise typer.Exit(code=2)


@app.command("run-async")
def run_async(
    datasource: str,
    sql: str,
    max_rows: int | None = None,
    access_mode: str = "read_only",
) -> None:
    """Guard and execute SQL asynchronously.

    Args:
        datasource: Datasource identifier.
        sql: SQL text to execute.
        max_rows: Optional row-limit override.
        access_mode: Requested execution mode, either `read_only` or `writable`.
    """

    result = asyncio.run(
        _run_async(
            datasource=datasource,
            sql=sql,
            max_rows=max_rows,
            access_mode=access_mode,
        )
    )
    typer.echo(
        orjson.dumps(
            result.model_dump(mode="json"), option=orjson.OPT_INDENT_2
        ).decode()
    )
    if not result.guard.allowed:
        raise typer.Exit(code=2)


async def _run_async(
    *,
    datasource: str,
    sql: str,
    max_rows: int | None,
    access_mode: str,
):
    """Execute the async query path inside an event loop.

    Args:
        datasource: Datasource identifier.
        sql: SQL text to execute.
        max_rows: Optional row-limit override.
        access_mode: Requested execution mode, either `read_only` or `writable`.

    Returns:
        object: Query execution result model.
    """

    container = build_service_container(datasource, include_async_engine=True)
    try:
        return await container.query_service.run_async(
            sql,
            max_rows=max_rows,
            access_mode=access_mode,
        )
    finally:
        await container.aclose()
