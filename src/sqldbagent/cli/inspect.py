"""Inspection CLI commands."""

from __future__ import annotations

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.core.errors import ConfigurationError

typer = load_typer()
app = typer.Typer(help="Inspection commands.")


@app.command("server")
def server(datasource: str) -> None:
    """Describe the connected server for a datasource.

    Args:
        datasource: Datasource identifier.
    """

    container = build_service_container(datasource)
    try:
        typer.echo(container.inspector.inspect_server().model_dump_json(indent=2))
    finally:
        container.close()


@app.command("databases")
def databases(datasource: str) -> None:
    """List databases for a datasource.

    Args:
        datasource: Datasource identifier.
    """

    container = build_service_container(datasource)
    try:
        for database_name in container.inspector.list_databases():
            typer.echo(database_name)
    finally:
        container.close()


@app.command("database")
def database(datasource: str, database_name: str | None = None) -> None:
    """Describe a database for a datasource.

    Args:
        datasource: Datasource identifier.
        database_name: Optional database name override.
    """

    container = build_service_container(datasource)
    try:
        typer.echo(
            container.inspector.inspect_database(database_name).model_dump_json(
                indent=2
            )
        )
    finally:
        container.close()


@app.command("schemas")
def schemas(datasource: str, database: str | None = None) -> None:
    """List schemas for a datasource.

    Args:
        datasource: Datasource identifier.
        database: Optional database scope.
    """

    container = build_service_container(datasource)
    try:
        for schema_name in container.inspector.list_schemas(database=database):
            typer.echo(schema_name)
    finally:
        container.close()


@app.command("schema")
def schema(datasource: str, schema_name: str) -> None:
    """Describe a schema for a datasource.

    Args:
        datasource: Datasource identifier.
        schema_name: Schema name.
    """

    container = build_service_container(datasource)
    try:
        typer.echo(
            container.inspector.inspect_schema(schema_name).model_dump_json(indent=2)
        )
    finally:
        container.close()


@app.command("tables")
def tables(datasource: str, schema: str | None = None) -> None:
    """List tables for a datasource.

    Args:
        datasource: Datasource identifier.
        schema: Optional schema scope.
    """

    container = build_service_container(datasource)
    try:
        for table_name in container.inspector.list_tables(schema=schema):
            typer.echo(table_name)
    finally:
        container.close()


@app.command("views")
def views(datasource: str, schema: str | None = None) -> None:
    """List views for a datasource.

    Args:
        datasource: Datasource identifier.
        schema: Optional schema scope.
    """

    container = build_service_container(datasource)
    try:
        for view_name in container.inspector.list_views(schema=schema):
            typer.echo(view_name)
    finally:
        container.close()


@app.command("table")
def table(datasource: str, table_name: str, schema: str | None = None) -> None:
    """Describe a table for a datasource.

    Args:
        datasource: Datasource identifier.
        table_name: Table name.
        schema: Optional schema scope.
    """

    try:
        container = build_service_container(datasource)
        description = container.inspector.describe_table(
            table_name=table_name,
            schema=schema,
        )
    except ConfigurationError as exc:
        raise typer.Exit(code=2) from exc
    finally:
        if "container" in locals():
            container.close()

    typer.echo(description.model_dump_json(indent=2))


@app.command("view")
def view(datasource: str, view_name: str, schema: str | None = None) -> None:
    """Describe a view for a datasource.

    Args:
        datasource: Datasource identifier.
        view_name: View name.
        schema: Optional schema scope.
    """

    container = build_service_container(datasource)
    try:
        description = container.inspector.describe_view(view_name, schema=schema)
    finally:
        container.close()

    typer.echo(description.model_dump_json(indent=2))
