"""Demo Postgres MCP end-to-end tests."""

from __future__ import annotations

import orjson
import pytest

from sqldbagent.adapters.mcp import create_mcp_server
from sqldbagent.core.bootstrap import build_service_container


@pytest.mark.e2e
@pytest.mark.enable_socket
@pytest.mark.asyncio
async def test_mcp_postgres_demo_end_to_end(
    live_postgres_demo_settings,
    live_qdrant_settings,
) -> None:
    """Exercise the MCP adapter against the demo datasource and retrieval flow."""

    del live_qdrant_settings
    settings = live_postgres_demo_settings.model_copy(
        update={
            "embeddings": live_postgres_demo_settings.embeddings.model_copy(
                update={"provider": "hash", "dimensions": 64}
            )
        }
    )
    container = build_service_container(
        "postgres_demo",
        settings=settings,
        include_async_engine=True,
    )
    try:
        server = create_mcp_server(container)
        tables = await server.call_tool("list_tables", {"schema": "public"})
        snapshot = await server.call_tool(
            "create_snapshot",
            {"schema": "public", "sample_size": 1},
        )
        diagram = await server.call_tool("generate_mermaid_erd", {"schema": "public"})
        documents = await server.call_tool(
            "export_schema_documents",
            {"schema": "public"},
        )
        prompt_bundle = await server.call_tool(
            "export_prompt_context",
            {"schema": "public"},
        )
        index_result = await server.call_tool(
            "index_schema_documents",
            {"schema": "public", "recreate_collection": True},
        )
        retrieval = await server.call_tool(
            "retrieve_schema_context",
            {"query": "Which table stores support tickets?", "schema": "public"},
        )
        query = await server.call_tool(
            "safe_query_sql",
            {"sql": "SELECT customer_code FROM public.customers ORDER BY id"},
        )
        query_async = await server.call_tool(
            "safe_query_sql_async",
            {"sql": "SELECT customer_code FROM public.customers ORDER BY id"},
        )
        prompt = await server.render_prompt(
            "retrieval_workflow",
            {"goal": "Find support tickets", "schema": "public"},
        )
        capabilities = await server.read_resource("sqldbagent://capabilities")
    finally:
        await container.aclose()

    if "customers" not in tables.structured_content.get("result", []):
        raise AssertionError(tables.structured_content)
    snapshot_payload = snapshot.structured_content
    if snapshot_payload.get("schema_metadata", {}).get("name") != "public":
        raise AssertionError(snapshot_payload)
    if "path" not in snapshot_payload:
        raise AssertionError(snapshot_payload)
    diagram_payload = diagram.structured_content
    if "erDiagram" not in diagram_payload.get("mermaid_erd", ""):
        raise AssertionError(diagram_payload)
    if "path" not in diagram_payload or "graph_path" not in diagram_payload:
        raise AssertionError(diagram_payload)
    documents_payload = documents.structured_content
    if not documents_payload.get("documents"):
        raise AssertionError(documents_payload)
    prompt_payload = prompt_bundle.structured_content
    if "system_prompt" not in prompt_payload or "markdown_path" not in prompt_payload:
        raise AssertionError(prompt_payload)
    if index_result.structured_content.get("document_count", 0) <= 0:
        raise AssertionError(index_result.structured_content)
    retrieval_payload = retrieval.structured_content
    if not any(
        document.get("metadata", {}).get("table_name") == "support_tickets"
        for document in retrieval_payload.get("documents", [])
    ):
        raise AssertionError(retrieval_payload)
    if query.structured_content.get("row_count") != 3:
        raise AssertionError(query.structured_content)
    if query_async.structured_content.get("mode") != "async":
        raise AssertionError(query_async.structured_content)
    prompt_text = prompt.messages[0].content.text
    if "stored snapshot documents" not in prompt_text:
        raise AssertionError(prompt)
    capabilities_payload = orjson.loads(capabilities.contents[0].content)
    if "generate_mermaid_erd" not in capabilities_payload.get("tools", []):
        raise AssertionError(capabilities_payload)
    if "export_prompt_context" not in capabilities_payload.get("tools", []):
        raise AssertionError(capabilities_payload)
