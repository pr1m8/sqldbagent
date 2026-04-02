"""Live Postgres CLI end-to-end tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sqldbagent.cli.app import app
from sqldbagent.core.config import load_settings


@pytest.mark.e2e
@pytest.mark.enable_socket
def test_cli_postgres_end_to_end(
    live_postgres_settings,
    live_postgres_schema: str,
    live_qdrant_settings,
    monkeypatch,
) -> None:
    """Exercise CLI inspection, profiling, querying, and snapshots on Postgres."""

    del live_postgres_settings
    del live_qdrant_settings
    monkeypatch.setenv("SQLDBAGENT_EMBEDDINGS_PROVIDER", "hash")
    monkeypatch.setenv("SQLDBAGENT_EMBEDDINGS_DIMENSIONS", "64")
    load_settings.cache_clear()
    runner = CliRunner()

    tables_result = runner.invoke(
        app,
        ["inspect", "tables", "postgres", "--schema", live_postgres_schema],
    )
    if tables_result.exit_code != 0:
        raise AssertionError(tables_result.output)
    if "users" not in tables_result.output:
        raise AssertionError(tables_result.output)

    table_result = runner.invoke(
        app,
        ["inspect", "table", "postgres", "users", "--schema", live_postgres_schema],
    )
    if table_result.exit_code != 0:
        raise AssertionError(table_result.output)
    table_output = table_result.output.replace(" ", "").replace("\n", "")
    if f'"schema_name":"{live_postgres_schema}"' not in table_output:
        raise AssertionError(table_result.output)
    if '"name":"users"' not in table_output:
        raise AssertionError(table_result.output)

    profile_result = runner.invoke(
        app,
        ["profile", "table", "postgres", "users", "--schema", live_postgres_schema],
    )
    if profile_result.exit_code != 0:
        raise AssertionError(profile_result.output)
    profile_output = profile_result.output.replace(" ", "").replace("\n", "")
    if '"row_count":3' not in profile_output:
        raise AssertionError(profile_result.output)
    if '"unique_value_count":2' not in profile_output:
        raise AssertionError(profile_result.output)

    query_sql = f'SELECT id, email FROM "{live_postgres_schema}"."users" ORDER BY id'  # nosec B608
    query_result = runner.invoke(app, ["query", "run", "postgres", query_sql])
    if query_result.exit_code != 0:
        raise AssertionError(query_result.output)
    if '"row_count":3' not in query_result.output.replace(" ", "").replace("\n", ""):
        raise AssertionError(query_result.output)

    query_async_result = runner.invoke(
        app,
        ["query", "run-async", "postgres", query_sql],
    )
    if query_async_result.exit_code != 0:
        raise AssertionError(query_async_result.output)
    if '"mode":"async"' not in query_async_result.output.replace(" ", "").replace(
        "\n", ""
    ):
        raise AssertionError(query_async_result.output)

    snapshot_create_result = runner.invoke(
        app,
        ["snapshot", "create", "postgres", live_postgres_schema],
    )
    if snapshot_create_result.exit_code != 0:
        raise AssertionError(snapshot_create_result.output)
    snapshot_path = Path(snapshot_create_result.output.strip())
    if not snapshot_path.exists():
        raise AssertionError(snapshot_path)

    snapshot_latest_result = runner.invoke(
        app,
        ["snapshot", "latest", "postgres", live_postgres_schema],
    )
    if snapshot_latest_result.exit_code != 0:
        raise AssertionError(snapshot_latest_result.output)
    if (
        f'"schema_name":"{live_postgres_schema}"'
        not in snapshot_latest_result.output.replace(" ", "").replace("\n", "")
    ):
        raise AssertionError(snapshot_latest_result.output)

    docs_export_result = runner.invoke(
        app,
        ["docs", "export", "postgres", live_postgres_schema],
    )
    if docs_export_result.exit_code != 0:
        raise AssertionError(docs_export_result.output)

    diagram_result = runner.invoke(
        app,
        ["diagram", "schema", "postgres", live_postgres_schema],
    )
    if diagram_result.exit_code != 0:
        raise AssertionError(diagram_result.output)
    diagram_output = diagram_result.output.replace(" ", "").replace("\n", "")
    if '"mermaid_erd":"erDiagram' not in diagram_output:
        raise AssertionError(diagram_result.output)

    rag_index_result = runner.invoke(
        app,
        ["rag", "index", "postgres", live_postgres_schema, "--recreate-collection"],
    )
    if rag_index_result.exit_code != 0:
        raise AssertionError(rag_index_result.output)
    rag_index_output = rag_index_result.output.replace(" ", "").replace("\n", "")
    if '"document_count":' not in rag_index_output:
        raise AssertionError(rag_index_result.output)

    rag_query_result = runner.invoke(
        app,
        [
            "rag",
            "query",
            "postgres",
            "Which table stores user email addresses?",
            "--schema",
            live_postgres_schema,
        ],
    )
    if rag_query_result.exit_code != 0:
        raise AssertionError(rag_query_result.output)
    if '"table_name":"users"' not in rag_query_result.output.replace(" ", "").replace(
        "\n", ""
    ):
        raise AssertionError(rag_query_result.output)
