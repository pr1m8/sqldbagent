"""Retrieval and vector-index CLI commands."""

from __future__ import annotations

import orjson

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container

typer = load_typer()
app = typer.Typer(help="Retrieval and vector-index commands.")


@app.command("index")
def index(datasource: str, schema: str, recreate_collection: bool = False) -> None:
    """Index the latest saved schema snapshot into the vector store.

    Args:
        datasource: Datasource identifier.
        schema: Schema name whose latest saved snapshot should be indexed.
        recreate_collection: Whether to recreate the target collection first.
    """

    container = build_service_container(datasource)
    try:
        result = container.retrieval_service.index_latest_schema_snapshot(
            schema_name=schema,
            recreate_collection=recreate_collection,
        )
    finally:
        container.close()

    typer.echo(
        orjson.dumps(
            result.model_dump(mode="json"),
            option=orjson.OPT_INDENT_2,
        ).decode()
    )


@app.command("query")
def query(
    datasource: str,
    query_text: str,
    schema: str | None = None,
    table_name: str | None = None,
    snapshot_id: str | None = None,
    limit: int | None = None,
) -> None:
    """Retrieve schema context from indexed documents.

    Args:
        datasource: Datasource identifier.
        query_text: Natural-language retrieval query.
        schema: Optional schema filter.
        table_name: Optional table filter.
        snapshot_id: Optional snapshot filter.
        limit: Optional result limit override.
    """

    container = build_service_container(datasource)
    try:
        result = container.retrieval_service.retrieve(
            query_text,
            schema_name=schema,
            table_name=table_name,
            snapshot_id=snapshot_id,
            limit=limit,
        )
    finally:
        container.close()

    typer.echo(
        orjson.dumps(
            result.model_dump(mode="json"),
            option=orjson.OPT_INDENT_2,
        ).decode()
    )
