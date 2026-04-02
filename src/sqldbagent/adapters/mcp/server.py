"""FastMCP server factory."""

from __future__ import annotations

from typing import Any

import orjson

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.bootstrap import ServiceContainer
from sqldbagent.snapshot.service import SnapshotService


def create_mcp_server(services: ServiceContainer, name: str = "sqldbagent") -> Any:
    """Build a FastMCP server over the shared service layer.

    Args:
        services: Shared service container for adapter wiring.
        name: Server name exposed through FastMCP.

    Returns:
        Any: Configured FastMCP server instance.
    """

    fastmcp_module = require_dependency("fastmcp", "fastmcp")
    server = fastmcp_module.FastMCP(name)
    server.instructions = (
        "Use sqldbagent tools for normalized metadata discovery, profiling, "
        "snapshots, and guarded read-only SQL. Start with inspection, then "
        "profile or query only when metadata is insufficient."
    )

    @server.tool
    def list_databases() -> list[str]:
        return services.inspector.list_databases()

    @server.tool
    def list_schemas(database: str | None = None) -> list[str]:
        return services.inspector.list_schemas(database=database)

    @server.tool
    def list_tables(schema: str | None = None) -> list[str]:
        return services.inspector.list_tables(schema=schema)

    @server.tool
    def list_views(schema: str | None = None) -> list[str]:
        return services.inspector.list_views(schema=schema)

    @server.tool
    def describe_table(table_name: str, schema: str | None = None) -> dict[str, Any]:
        return services.inspector.describe_table(
            table_name=table_name,
            schema=schema,
        ).model_dump(mode="json")

    @server.tool
    def describe_view(view_name: str, schema: str | None = None) -> dict[str, Any]:
        return services.inspector.describe_view(
            view_name=view_name,
            schema=schema,
        ).model_dump(mode="json")

    if services.profiler is not None:

        @server.tool
        def profile_table(
            table_name: str,
            schema: str | None = None,
            sample_size: int = 5,
        ) -> dict[str, Any]:
            return services.profiler.profile_table(
                table_name=table_name,
                schema=schema,
                sample_size=sample_size,
            ).model_dump(mode="json")

        @server.tool
        def sample_table(
            table_name: str,
            schema: str | None = None,
            limit: int = 5,
        ) -> list[dict[str, object | None]]:
            return services.profiler.sample_table(
                table_name=table_name,
                schema=schema,
                limit=limit,
            )

    if services.snapshotter is not None:

        @server.tool
        def create_snapshot(
            schema: str,
            sample_size: int = 5,
        ) -> dict[str, Any]:
            bundle = services.snapshotter.create_schema_snapshot(
                schema_name=schema,
                sample_size=sample_size,
            )
            path = services.snapshotter.save_snapshot(bundle)
            payload = bundle.model_dump(mode="json")
            payload["path"] = path.as_posix()
            return payload

        @server.tool
        def diff_snapshots(left_path: str, right_path: str) -> dict[str, Any]:
            left_bundle = SnapshotService.load_snapshot(left_path)
            right_bundle = SnapshotService.load_snapshot(right_path)
            return SnapshotService.diff_snapshots(
                left=left_bundle,
                right=right_bundle,
            ).model_dump(mode="json")

    if services.document_service is not None and services.snapshotter is not None:

        @server.tool
        def export_schema_documents(schema: str) -> dict[str, Any]:
            bundle = services.snapshotter.load_latest_saved_snapshot(schema)
            document_bundle = services.document_service.create_document_bundle(bundle)
            path = services.document_service.save_document_bundle(document_bundle)
            payload = document_bundle.model_dump(mode="json")
            payload["path"] = path.as_posix()
            return payload

    if services.prompt_service is not None and services.snapshotter is not None:

        @server.tool
        def export_prompt_context(schema: str) -> dict[str, Any]:
            bundle = services.snapshotter.load_latest_saved_snapshot(schema)
            prompt_bundle = services.prompt_service.create_prompt_bundle(bundle)
            path = services.prompt_service.save_prompt_bundle(prompt_bundle)
            payload = prompt_bundle.model_dump(mode="json")
            payload["path"] = path.as_posix()
            payload["markdown_path"] = services.prompt_service.markdown_path(
                datasource_name=prompt_bundle.datasource_name,
                schema_name=prompt_bundle.schema_name,
                snapshot_id=prompt_bundle.snapshot_id,
            ).as_posix()
            return payload

    if services.diagram_service is not None and services.snapshotter is not None:

        @server.tool
        def generate_mermaid_erd(schema: str) -> dict[str, Any]:
            bundle = services.snapshotter.load_latest_saved_snapshot(schema)
            diagram_bundle = services.diagram_service.create_diagram_bundle(bundle)
            path = services.diagram_service.save_diagram_bundle(diagram_bundle)
            payload = diagram_bundle.model_dump(mode="json")
            payload["path"] = path.as_posix()
            payload["mermaid_path"] = services.diagram_service.mermaid_path(
                datasource_name=diagram_bundle.datasource_name,
                schema_name=diagram_bundle.schema_name,
                snapshot_id=diagram_bundle.snapshot_id,
            ).as_posix()
            payload["graph_path"] = services.diagram_service.graph_path(
                datasource_name=diagram_bundle.datasource_name,
                schema_name=diagram_bundle.schema_name,
                snapshot_id=diagram_bundle.snapshot_id,
            ).as_posix()
            return payload

    if services.retrieval_service is not None:

        @server.tool
        def index_schema_documents(
            schema: str,
            recreate_collection: bool = False,
        ) -> dict[str, Any]:
            return services.retrieval_service.index_latest_schema_snapshot(
                schema_name=schema,
                recreate_collection=recreate_collection,
            ).model_dump(mode="json")

        @server.tool
        def retrieve_schema_context(
            query: str,
            schema: str | None = None,
            table_name: str | None = None,
            snapshot_id: str | None = None,
            artifact_types: list[str] | None = None,
            limit: int = 6,
        ) -> dict[str, Any]:
            return services.retrieval_service.retrieve(
                query,
                schema_name=schema,
                table_name=table_name,
                snapshot_id=snapshot_id,
                artifact_types=artifact_types,
                limit=limit,
            ).model_dump(mode="json")

    if services.query_service is not None:

        @server.tool
        def safe_query_sql(sql: str, max_rows: int | None = None) -> dict[str, Any]:
            result = services.query_service.run(
                sql=sql,
                max_rows=max_rows,
            ).model_dump(mode="json")
            result["lint"] = services.query_guard.lint(sql).model_dump(mode="json")
            return result

        if services.async_engine is not None:

            @server.tool
            async def safe_query_sql_async(
                sql: str,
                max_rows: int | None = None,
            ) -> dict[str, Any]:
                result = (
                    await services.query_service.run_async(
                        sql=sql,
                        max_rows=max_rows,
                    )
                ).model_dump(mode="json")
                result["lint"] = services.query_guard.lint(sql).model_dump(mode="json")
                return result

    @server.resource(
        "sqldbagent://instructions",
        name="instructions",
        description="High-level usage guidance for the sqldbagent MCP server.",
        mime_type="text/plain",
    )
    def instructions_resource() -> str:
        return (
            "sqldbagent MCP focuses on normalized metadata first. "
            "List schemas, tables, and views, then describe or profile objects, "
            "then use retrieval or safe_query_sql when the answer requires stored context or live data."
        )

    @server.resource(
        "sqldbagent://capabilities",
        name="capabilities",
        description="Current MCP capabilities exposed by sqldbagent.",
        mime_type="application/json",
    )
    def capabilities_resource() -> dict[str, Any]:
        tools = [
            "list_databases",
            "list_schemas",
            "list_tables",
            "list_views",
            "describe_table",
            "describe_view",
        ]
        if services.profiler is not None:
            tools.extend(["profile_table", "sample_table"])
        if services.snapshotter is not None:
            tools.extend(["create_snapshot", "diff_snapshots"])
        if services.document_service is not None and services.snapshotter is not None:
            tools.append("export_schema_documents")
        if services.prompt_service is not None and services.snapshotter is not None:
            tools.append("export_prompt_context")
        if services.diagram_service is not None and services.snapshotter is not None:
            tools.append("generate_mermaid_erd")
        if services.retrieval_service is not None:
            tools.extend(["index_schema_documents", "retrieve_schema_context"])
        if services.query_service is not None:
            tools.append("safe_query_sql")
        if services.query_service is not None and services.async_engine is not None:
            tools.append("safe_query_sql_async")

        return orjson.dumps(
            {
                "tools": tools,
                "prompts": [
                    "schema_explorer",
                    "table_summary",
                    "safe_query_workflow",
                    "retrieval_workflow",
                ],
                "notes": [
                    "Normalized metadata is the primary contract for downstream adapters.",
                    "Guarded SQL is read-only and row-limited by policy.",
                    "Snapshot bundles are meant to be stored and reloaded as durable artifacts.",
                    "Diagrams are generated from stored snapshot bundles, not ad hoc SQL.",
                    "Retrieval works over stored snapshot documents indexed in Qdrant.",
                ],
            },
            option=orjson.OPT_INDENT_2,
        ).decode()

    @server.prompt(
        name="schema_explorer",
        description="Guide an agent to inspect a datasource schema safely.",
    )
    def schema_explorer_prompt(database: str | None = None) -> str:
        database_scope = (
            f"Focus on database '{database}'."
            if database
            else "Inspect the default database."
        )
        return (
            "You are exploring a relational database through sqldbagent. "
            f"{database_scope} "
            "Start by listing schemas, then list relevant tables and views, then "
            "describe the objects that matter. Prefer metadata inspection over "
            "speculative SQL."
        )

    @server.prompt(
        name="table_summary",
        description="Guide an agent to summarize one table from normalized metadata.",
    )
    def table_summary_prompt(table_name: str, schema: str | None = None) -> str:
        qualified_name = f"{schema}.{table_name}" if schema else table_name
        return (
            "Summarize the table using sqldbagent metadata and profiles. "
            f"Inspect '{qualified_name}', identify keys, constraints, and likely "
            "relationships, then explain what business entity it appears to model."
        )

    @server.prompt(
        name="safe_query_workflow",
        description="Guide an agent through guarded live querying.",
    )
    def safe_query_workflow_prompt(goal: str) -> str:
        return (
            "Use sqldbagent metadata first, then guarded SQL only if needed. "
            f"Goal: {goal}. "
            "Describe the relevant tables, profile the high-signal ones, then run a "
            "single read-only safe_query_sql statement with a tight scope."
        )

    @server.prompt(
        name="retrieval_workflow",
        description="Guide an agent to use indexed snapshot documents before live SQL.",
    )
    def retrieval_workflow_prompt(goal: str, schema: str | None = None) -> str:
        schema_scope = (
            f"Focus on schema '{schema}'." if schema else "Use all indexed schemas."
        )
        return (
            "Use sqldbagent retrieval over stored snapshot documents first. "
            f"{schema_scope} "
            f"Goal: {goal}. "
            "If needed, export and index the latest schema snapshot, retrieve the most "
            "relevant table and relationship context, then decide whether live SQL is required."
        )

    return server
