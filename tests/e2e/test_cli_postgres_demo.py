"""Demo Postgres CLI end-to-end tests."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from sqldbagent.cli.app import app
from sqldbagent.core.config import load_settings


@pytest.mark.e2e
@pytest.mark.enable_socket
def test_cli_postgres_demo_end_to_end(
    live_postgres_demo_settings,
    live_qdrant_settings,
    monkeypatch,
) -> None:
    """Exercise the demo datasource through the CLI and retrieval path."""

    del live_postgres_demo_settings
    del live_qdrant_settings
    monkeypatch.setenv("SQLDBAGENT_EMBEDDINGS_PROVIDER", "hash")
    monkeypatch.setenv("SQLDBAGENT_EMBEDDINGS_DIMENSIONS", "64")
    load_settings.cache_clear()
    runner = CliRunner()

    tables_result = runner.invoke(
        app,
        ["inspect", "tables", "postgres_demo", "--schema", "public"],
    )
    if tables_result.exit_code != 0:
        raise AssertionError(tables_result.output)
    if "customers" not in tables_result.output or "orders" not in tables_result.output:
        raise AssertionError(tables_result.output)

    profile_result = runner.invoke(
        app,
        ["profile", "table", "postgres_demo", "customers", "--schema", "public"],
    )
    if profile_result.exit_code != 0:
        raise AssertionError(profile_result.output)
    compact_profile_output = profile_result.output.replace(" ", "").replace("\n", "")
    if '"row_count":3' not in compact_profile_output:
        raise AssertionError(profile_result.output)
    if '"storage_source":"pg_total_relation_size"' not in compact_profile_output:
        raise AssertionError(profile_result.output)
    if '"unique_value_count":2' not in compact_profile_output:
        raise AssertionError(profile_result.output)

    query_result = runner.invoke(
        app,
        [
            "query",
            "run",
            "postgres_demo",
            "SELECT customer_code, name FROM public.customers ORDER BY id",
        ],
    )
    if query_result.exit_code != 0:
        raise AssertionError(query_result.output)
    if '"row_count":3' not in query_result.output.replace(" ", "").replace("\n", ""):
        raise AssertionError(query_result.output)

    snapshot_result = runner.invoke(
        app,
        ["snapshot", "create", "postgres_demo", "public"],
    )
    if snapshot_result.exit_code != 0:
        raise AssertionError(snapshot_result.output)

    docs_result = runner.invoke(
        app,
        ["docs", "export", "postgres_demo", "public"],
    )
    if docs_result.exit_code != 0:
        raise AssertionError(docs_result.output)

    rag_index_result = runner.invoke(
        app,
        ["rag", "index", "postgres_demo", "public", "--recreate-collection"],
    )
    if rag_index_result.exit_code != 0:
        raise AssertionError(rag_index_result.output)

    rag_query_result = runner.invoke(
        app,
        [
            "rag",
            "query",
            "postgres_demo",
            "Which table stores support tickets?",
            "--schema",
            "public",
        ],
    )
    if rag_query_result.exit_code != 0:
        raise AssertionError(rag_query_result.output)
    output = rag_query_result.output.replace(" ", "").replace("\n", "")
    if '"table_name":"support_tickets"' not in output:
        raise AssertionError(rag_query_result.output)
