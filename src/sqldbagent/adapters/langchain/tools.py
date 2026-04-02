"""LangChain tool factories over shared services."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.bootstrap import ServiceContainer


class ListSchemasInput(BaseModel):
    """Input for schema listing.

    Attributes:
        database: Optional database scope for schema listing.
    """

    database: str | None = Field(default=None)


class ListTablesInput(BaseModel):
    """Input for table listing.

    Attributes:
        schema_name: Optional schema scope for table listing.
    """

    schema_name: str | None = Field(default=None)


class DescribeTableInput(BaseModel):
    """Input for table description.

    Attributes:
        table_name: Table name to describe.
        schema_name: Optional schema containing the table.
    """

    table_name: str
    schema_name: str | None = Field(default=None)


class DescribeViewInput(BaseModel):
    """Input for view description.

    Attributes:
        view_name: View name to describe.
        schema_name: Optional schema containing the view.
    """

    view_name: str
    schema_name: str | None = Field(default=None)


class ProfileTableInput(BaseModel):
    """Input for table profiling.

    Attributes:
        table_name: Table name to profile.
        schema_name: Optional schema containing the table.
        sample_size: Number of sample rows to include.
    """

    table_name: str
    schema_name: str | None = Field(default=None)
    sample_size: int = Field(default=5, ge=1)


class SampleTableInput(BaseModel):
    """Input for table sampling.

    Attributes:
        table_name: Table name to sample.
        schema_name: Optional schema containing the table.
        limit: Maximum rows to return.
    """

    table_name: str
    schema_name: str | None = Field(default=None)
    limit: int = Field(default=5, ge=1)


class GetUniqueValuesInput(BaseModel):
    """Input for distinct-value lookup.

    Attributes:
        table_name: Table name containing the target column.
        column_name: Column name whose unique values should be returned.
        schema_name: Optional schema containing the table.
        limit: Maximum number of distinct values to return.
    """

    table_name: str
    column_name: str
    schema_name: str | None = Field(default=None)
    limit: int = Field(default=20, ge=1)


class SafeQuerySqlInput(BaseModel):
    """Input for guarded SQL execution.

    Attributes:
        sql: SQL text to guard and execute.
        max_rows: Optional row-limit override.
    """

    sql: str
    max_rows: int | None = Field(default=None, ge=1)


class CreateSnapshotInput(BaseModel):
    """Input for snapshot creation.

    Attributes:
        schema_name: Schema to snapshot.
        sample_size: Number of sample rows per profiled table.
    """

    schema_name: str
    sample_size: int = Field(default=5, ge=1)


class DiffSnapshotsInput(BaseModel):
    """Input for snapshot diffing.

    Attributes:
        left_path: Baseline snapshot path.
        right_path: Comparison snapshot path.
    """

    left_path: str
    right_path: str


class ExportSchemaDocumentsInput(BaseModel):
    """Input for snapshot document export.

    Attributes:
        schema_name: Schema to export from the latest saved snapshot.
    """

    schema_name: str


class GenerateMermaidErdInput(BaseModel):
    """Input for schema diagram generation.

    Attributes:
        schema_name: Schema whose latest saved snapshot should be visualized.
    """

    schema_name: str


class ExportPromptContextInput(BaseModel):
    """Input for prompt export.

    Attributes:
        schema_name: Schema whose latest saved snapshot should become a prompt bundle.
    """

    schema_name: str


class IndexSchemaDocumentsInput(BaseModel):
    """Input for retrieval indexing.

    Attributes:
        schema_name: Schema whose latest saved snapshot should be indexed.
        recreate_collection: Whether the vector collection should be recreated first.
    """

    schema_name: str
    recreate_collection: bool = False


class RetrieveSchemaContextInput(BaseModel):
    """Input for retrieval-backed schema context search.

    Attributes:
        query: Natural-language retrieval query.
        schema_name: Optional schema filter.
        table_name: Optional table filter.
        snapshot_id: Optional snapshot filter.
        artifact_types: Optional artifact-type filters.
        limit: Number of results to return.
    """

    query: str
    schema_name: str | None = Field(default=None)
    table_name: str | None = Field(default=None)
    snapshot_id: str | None = Field(default=None)
    artifact_types: list[str] | None = Field(default=None)
    limit: int = Field(default=6, ge=1)


def create_langchain_tools(services: ServiceContainer) -> list[Any]:
    """Build LangChain tools over the shared service layer.

    Args:
        services: Shared service container for adapter wiring.

    Returns:
        list[Any]: Structured LangChain tools backed by shared services.
    """

    tools_module = require_dependency("langchain_core.tools", "langchain")
    structured_tool = tools_module.StructuredTool
    tools: list[Any] = []

    def list_databases() -> list[str]:
        return services.inspector.list_databases()

    def list_schemas(database: str | None = None) -> list[str]:
        return services.inspector.list_schemas(database=database)

    def list_tables(schema_name: str | None = None) -> list[str]:
        return services.inspector.list_tables(schema=schema_name)

    def list_views(schema_name: str | None = None) -> list[str]:
        return services.inspector.list_views(schema=schema_name)

    def describe_table(
        table_name: str, schema_name: str | None = None
    ) -> dict[str, Any]:
        return services.inspector.describe_table(
            table_name=table_name,
            schema=schema_name,
        ).model_dump(mode="json")

    def describe_view(view_name: str, schema_name: str | None = None) -> dict[str, Any]:
        return services.inspector.describe_view(
            view_name=view_name,
            schema=schema_name,
        ).model_dump(mode="json")

    tools.extend(
        [
            structured_tool.from_function(
                func=list_databases,
                name="list_databases",
                description="List databases visible to the configured datasource.",
            ),
            structured_tool.from_function(
                func=list_schemas,
                name="list_schemas",
                description="List schemas for an optional database.",
                args_schema=ListSchemasInput,
            ),
            structured_tool.from_function(
                func=list_tables,
                name="list_tables",
                description="List tables for an optional schema.",
                args_schema=ListTablesInput,
            ),
            structured_tool.from_function(
                func=list_views,
                name="list_views",
                description="List views for an optional schema.",
                args_schema=ListTablesInput,
            ),
            structured_tool.from_function(
                func=describe_table,
                name="describe_table",
                description="Return normalized metadata for a table.",
                args_schema=DescribeTableInput,
            ),
            structured_tool.from_function(
                func=describe_view,
                name="describe_view",
                description="Return normalized metadata for a view.",
                args_schema=DescribeViewInput,
            ),
        ]
    )

    if services.profiler is not None:

        def profile_table(
            table_name: str,
            schema_name: str | None = None,
            sample_size: int = 5,
        ) -> dict[str, Any]:
            return services.profiler.profile_table(
                table_name=table_name,
                schema=schema_name,
                sample_size=sample_size,
            ).model_dump(mode="json")

        def sample_table(
            table_name: str,
            schema_name: str | None = None,
            limit: int = 5,
        ) -> list[dict[str, object | None]]:
            return services.profiler.sample_table(
                table_name=table_name,
                schema=schema_name,
                limit=limit,
            )

        def get_unique_values(
            table_name: str,
            column_name: str,
            schema_name: str | None = None,
            limit: int = 20,
        ) -> dict[str, Any]:
            return services.profiler.get_unique_values(
                table_name=table_name,
                column_name=column_name,
                schema=schema_name,
                limit=limit,
            ).model_dump(mode="json")

        tools.extend(
            [
                structured_tool.from_function(
                    func=profile_table,
                    name="profile_table",
                    description="Build a normalized profile for a table.",
                    args_schema=ProfileTableInput,
                ),
                structured_tool.from_function(
                    func=sample_table,
                    name="sample_table",
                    description="Return sample rows for a table.",
                    args_schema=SampleTableInput,
                ),
                structured_tool.from_function(
                    func=get_unique_values,
                    name="get_unique_values",
                    description="Return distinct values and counts for one column.",
                    args_schema=GetUniqueValuesInput,
                ),
            ]
        )

    if services.snapshotter is not None:

        def create_snapshot(
            schema_name: str,
            sample_size: int = 5,
        ) -> dict[str, Any]:
            bundle = services.snapshotter.create_schema_snapshot(
                schema_name=schema_name,
                sample_size=sample_size,
            )
            path = services.snapshotter.save_snapshot(bundle)
            payload = bundle.model_dump(mode="json")
            payload["path"] = path.as_posix()
            return payload

        def diff_snapshots(left_path: str, right_path: str) -> dict[str, Any]:
            left_bundle = services.snapshotter.load_snapshot(left_path)
            right_bundle = services.snapshotter.load_snapshot(right_path)
            return services.snapshotter.diff_snapshots(
                left_bundle,
                right_bundle,
            ).model_dump(mode="json")

        tools.extend(
            [
                structured_tool.from_function(
                    func=create_snapshot,
                    name="create_snapshot",
                    description="Create and persist a normalized schema snapshot.",
                    args_schema=CreateSnapshotInput,
                ),
                structured_tool.from_function(
                    func=diff_snapshots,
                    name="diff_snapshots",
                    description="Diff two saved snapshot bundle paths.",
                    args_schema=DiffSnapshotsInput,
                ),
            ]
        )

    if services.query_service is not None:

        def safe_query_sql(
            sql: str,
            max_rows: int | None = None,
        ) -> dict[str, Any]:
            lint = services.query_guard.lint(sql)
            result = services.query_service.run(
                sql=sql,
                max_rows=max_rows,
            ).model_dump(mode="json")
            result["lint"] = lint.model_dump(mode="json")
            return result

        async def safe_query_sql_async(
            sql: str,
            max_rows: int | None = None,
        ) -> dict[str, Any]:
            lint = services.query_guard.lint(sql)
            result = (
                await services.query_service.run_async(
                    sql=sql,
                    max_rows=max_rows,
                )
            ).model_dump(mode="json")
            result["lint"] = lint.model_dump(mode="json")
            return result

        tool_kwargs: dict[str, Any] = {
            "func": safe_query_sql,
            "name": "safe_query_sql",
            "description": "Lint, guard, and execute read-only SQL with policy enforcement.",
            "args_schema": SafeQuerySqlInput,
        }
        if services.async_engine is not None:
            tool_kwargs["coroutine"] = safe_query_sql_async
        tools.append(structured_tool.from_function(**tool_kwargs))

    if services.document_service is not None and services.snapshotter is not None:

        def export_schema_documents(schema_name: str) -> dict[str, Any]:
            bundle = services.snapshotter.load_latest_saved_snapshot(schema_name)
            document_bundle = services.document_service.create_document_bundle(bundle)
            path = services.document_service.save_document_bundle(document_bundle)
            payload = document_bundle.model_dump(mode="json")
            payload["path"] = path.as_posix()
            return payload

        tools.append(
            structured_tool.from_function(
                func=export_schema_documents,
                name="export_schema_documents",
                description="Export retrieval-ready documents from the latest saved schema snapshot.",
                args_schema=ExportSchemaDocumentsInput,
            )
        )

    if services.prompt_service is not None and services.snapshotter is not None:

        def export_prompt_context(schema_name: str) -> dict[str, Any]:
            bundle = services.snapshotter.load_latest_saved_snapshot(schema_name)
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

        tools.append(
            structured_tool.from_function(
                func=export_prompt_context,
                name="export_prompt_context",
                description="Export a durable prompt bundle from the latest saved schema snapshot.",
                args_schema=ExportPromptContextInput,
            )
        )

    if services.diagram_service is not None and services.snapshotter is not None:

        def generate_mermaid_erd(schema_name: str) -> dict[str, Any]:
            bundle = services.snapshotter.load_latest_saved_snapshot(schema_name)
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

        tools.append(
            structured_tool.from_function(
                func=generate_mermaid_erd,
                name="generate_mermaid_erd",
                description="Generate Mermaid ER and graph artifacts from the latest saved schema snapshot.",
                args_schema=GenerateMermaidErdInput,
            )
        )

    if services.retrieval_service is not None:

        def index_schema_documents(
            schema_name: str,
            recreate_collection: bool = False,
        ) -> dict[str, Any]:
            return services.retrieval_service.index_latest_schema_snapshot(
                schema_name=schema_name,
                recreate_collection=recreate_collection,
            ).model_dump(mode="json")

        def retrieve_schema_context(
            query: str,
            schema_name: str | None = None,
            table_name: str | None = None,
            snapshot_id: str | None = None,
            artifact_types: list[str] | None = None,
            limit: int = 6,
        ) -> dict[str, Any]:
            return services.retrieval_service.retrieve(
                query,
                schema_name=schema_name,
                table_name=table_name,
                snapshot_id=snapshot_id,
                artifact_types=artifact_types,
                limit=limit,
            ).model_dump(mode="json")

        tools.extend(
            [
                structured_tool.from_function(
                    func=index_schema_documents,
                    name="index_schema_documents",
                    description="Index the latest saved schema snapshot into the retrieval vector store.",
                    args_schema=IndexSchemaDocumentsInput,
                ),
                structured_tool.from_function(
                    func=retrieve_schema_context,
                    name="retrieve_schema_context",
                    description="Retrieve schema context from indexed snapshot documents in the vector store.",
                    args_schema=RetrieveSchemaContextInput,
                ),
            ]
        )

    return tools
