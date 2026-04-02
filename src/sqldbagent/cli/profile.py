"""Profiling CLI commands."""

from __future__ import annotations

import orjson

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.core.config import load_settings

typer = load_typer()
app = typer.Typer(help="Profiling commands.")


@app.command("table")
def table(
    datasource: str,
    table_name: str,
    schema: str | None = None,
    sample_size: int | None = None,
) -> None:
    """Profile a table.

    Args:
        datasource: Datasource identifier.
        table_name: Table name.
        schema: Optional schema name.
        sample_size: Number of sample rows to include.
    """

    settings = load_settings()
    resolved_sample_size = sample_size or settings.profiling.default_sample_size
    container = build_service_container(datasource, settings=settings)
    try:
        result = container.profiler.profile_table(
            table_name=table_name,
            schema=schema,
            sample_size=resolved_sample_size,
        )
    finally:
        container.close()

    typer.echo(result.model_dump_json(indent=2))


@app.command("sample")
def sample(
    datasource: str,
    table_name: str,
    schema: str | None = None,
    limit: int | None = None,
) -> None:
    """Sample rows from a table.

    Args:
        datasource: Datasource identifier.
        table_name: Table name.
        schema: Optional schema name.
        limit: Maximum rows to return.
    """

    settings = load_settings()
    resolved_limit = limit or settings.profiling.default_sample_size
    container = build_service_container(datasource, settings=settings)
    try:
        result = container.profiler.sample_table(
            table_name=table_name,
            schema=schema,
            limit=resolved_limit,
        )
    finally:
        container.close()

    typer.echo(orjson.dumps(result, option=orjson.OPT_INDENT_2).decode())
