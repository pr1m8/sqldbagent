"""Adapter bootstrap tests."""

import asyncio
from importlib.util import find_spec
from pathlib import Path

import orjson
from sqlalchemy import create_engine, text

from sqldbagent.adapters.langchain import (
    create_langchain_tools,
    create_sql_database_from_engine,
)
from sqldbagent.adapters.mcp import create_mcp_server
from sqldbagent.core.bootstrap import ServiceContainer
from sqldbagent.core.config import (
    AppSettings,
    ArtifactSettings,
    DatasourceSettings,
    ProfilingSettings,
    SafetySettings,
)
from sqldbagent.core.enums import Dialect
from sqldbagent.core.errors import AdapterDependencyError
from sqldbagent.core.models.catalog import (
    ColumnModel,
    SchemaModel,
    TableModel,
    ViewModel,
)
from sqldbagent.core.models.profile import TableProfileModel
from sqldbagent.core.models.query import QueryExecutionResult
from sqldbagent.prompts.models import PromptBundleModel, PromptExplorationModel
from sqldbagent.safety.models import QueryGuardResult
from sqldbagent.snapshot.models import SnapshotBundleModel


class StubInspectionService:
    """Small test double for adapter factories."""

    def list_databases(self) -> list[str]:
        """Return a fixed database list."""

        return ["main"]

    def list_schemas(self, database: str | None = None) -> list[str]:
        """Return a fixed schema list."""

        if database not in {None, "main"}:
            raise ValueError(f"unexpected database: {database}")
        return ["public"]

    def list_tables(self, schema: str | None = None) -> list[str]:
        """Return a fixed table list."""

        if schema not in {None, "public"}:
            raise ValueError(f"unexpected schema: {schema}")
        return ["users"]

    def list_views(self, schema: str | None = None) -> list[str]:
        """Return a fixed view list."""

        if schema not in {None, "public"}:
            raise ValueError(f"unexpected schema: {schema}")
        return ["active_users"]

    def describe_table(self, table_name: str, schema: str | None = None) -> TableModel:
        """Return a fixed normalized table description."""

        if table_name != "users":
            raise ValueError(f"unexpected table: {table_name}")
        if schema not in {None, "public"}:
            raise ValueError(f"unexpected schema: {schema}")
        return TableModel(
            schema_name="public",
            name="users",
            columns=[ColumnModel(name="id", data_type="integer", nullable=False)],
            primary_key=["id"],
        )

    def describe_view(self, view_name: str, schema: str | None = None) -> ViewModel:
        """Return a fixed normalized view description."""

        return ViewModel(
            schema_name="public",
            name=view_name,
            columns=[ColumnModel(name="id", data_type="integer", nullable=False)],
        )


class StubProfilingService:
    """Small test double for profiling-capable adapters."""

    def profile_table(
        self,
        table_name: str,
        schema: str | None = None,
        sample_size: int = 5,
    ) -> TableProfileModel:
        """Return a fixed normalized table profile."""

        del schema, sample_size
        return TableProfileModel(table_name=table_name, row_count=1)

    def sample_table(
        self,
        table_name: str,
        schema: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, object | None]]:
        """Return fixed sample rows."""

        del table_name, schema, limit
        return [{"id": 1}]


class StubQueryService:
    """Small test double for guarded query adapters."""

    def run(self, sql: str, *, max_rows: int | None = None) -> QueryExecutionResult:
        """Return a fixed query execution result."""

        del sql, max_rows
        return QueryExecutionResult(
            mode="sync",
            guard=QueryGuardResult(
                allowed=True,
                dialect="sqlite",
                original_sql="SELECT 1",
            ),
            columns=["id"],
            rows=[{"id": 1}],
            row_count=1,
        )


class StubSnapshotService:
    """Small test double for snapshot-backed adapter tooling."""

    def load_latest_saved_snapshot(self, schema_name: str) -> SnapshotBundleModel:
        """Return a fixed snapshot bundle."""

        return SnapshotBundleModel(
            snapshot_id="snapshot-1",
            datasource_name="stub",
            schema_metadata=SchemaModel(
                database="main",
                name=schema_name,
                tables=[
                    TableModel(
                        database="main",
                        schema_name=schema_name,
                        name="users",
                        columns=[
                            ColumnModel(
                                name="id",
                                data_type="integer",
                                nullable=False,
                            )
                        ],
                        primary_key=["id"],
                    )
                ],
                views=[],
                summary="Stub schema",
            ),
            summary="Stub snapshot",
            regenerate={
                "datasource_name": "stub",
                "schema_name": schema_name,
                "sample_size": 5,
            },
        )

    def create_schema_snapshot(
        self,
        schema_name: str,
        sample_size: int = 5,
    ) -> SnapshotBundleModel:
        """Return a fixed generated snapshot bundle."""

        del sample_size
        return self.load_latest_saved_snapshot(schema_name)

    def save_snapshot(self, bundle: SnapshotBundleModel) -> Path:
        """Return a fixed saved snapshot path."""

        del bundle
        return Path("var/sqldbagent/snapshots/stub/public/snapshot-1.json")


class StubPromptService:
    """Small test double for prompt-backed adapter tooling."""

    def save_prompt_exploration(
        self,
        snapshot: SnapshotBundleModel,
        exploration: PromptExplorationModel,
    ) -> dict[str, object]:
        """Return a small enhancement-like payload."""

        del snapshot
        return {
            "schema_name": exploration.schema_name,
            "summary": exploration.summary,
        }

    def create_prompt_bundle(
        self,
        snapshot: SnapshotBundleModel,
        enhancement: dict[str, object] | None = None,
    ) -> PromptBundleModel:
        """Return a fixed prompt bundle."""

        del enhancement
        return PromptBundleModel(
            snapshot_id=snapshot.snapshot_id,
            datasource_name=snapshot.datasource_name,
            schema_name=snapshot.schema_name,
            base_system_prompt="Base prompt",
            system_prompt="Base prompt\n\nEnhanced prompt",
            summary="Stub prompt bundle",
            token_estimates={"system_prompt_tokens": 4},
        )

    def save_prompt_bundle(self, prompt_bundle: PromptBundleModel) -> Path:
        """Return a fixed saved prompt path."""

        del prompt_bundle
        return Path("var/sqldbagent/prompts/stub/public/prompt-1.json")


def test_langchain_adapter_raises_clear_dependency_error() -> None:
    """Build tools or raise a clear dependency error."""

    services = ServiceContainer(inspector=StubInspectionService())

    if find_spec("langchain_core.tools") is None:
        try:
            create_langchain_tools(services)
        except AdapterDependencyError as exc:
            if "langchain_core.tools" not in str(exc):
                raise AssertionError(str(exc)) from exc
        else:
            raise AssertionError(
                "expected AdapterDependencyError for missing langchain"
            )
    else:
        tools = create_langchain_tools(services)
        if len(tools) < 6:
            raise AssertionError(f"unexpected tool count: {len(tools)}")


def test_mcp_adapter_raises_clear_dependency_error() -> None:
    """Build a server or raise a clear dependency error."""

    services = ServiceContainer(
        inspector=StubInspectionService(),
        profiler=StubProfilingService(),
        query_service=StubQueryService(),
    )

    if find_spec("fastmcp") is None:
        try:
            create_mcp_server(services)
        except AdapterDependencyError as exc:
            if "fastmcp" not in str(exc):
                raise AssertionError(str(exc)) from exc
        else:
            raise AssertionError("expected AdapterDependencyError for missing fastmcp")
    else:
        server = create_mcp_server(services)
        if server is None:
            raise AssertionError("expected FastMCP server instance")


def test_mcp_server_registers_tools_prompts_and_resources() -> None:
    """Register MCP tools, prompts, and resources on the server."""

    if find_spec("fastmcp") is None:
        return

    services = ServiceContainer(
        inspector=StubInspectionService(),
        profiler=StubProfilingService(),
        query_service=StubQueryService(),
    )
    server = create_mcp_server(services)

    tools = asyncio.run(server.list_tools())
    prompts = asyncio.run(server.list_prompts())
    resources = asyncio.run(server.list_resources())

    if len(tools) < 8:
        raise AssertionError(tools)
    if len(prompts) < 2:
        raise AssertionError(prompts)
    if len(resources) < 2:
        raise AssertionError(resources)

    capabilities = asyncio.run(server.read_resource("sqldbagent://capabilities"))
    capabilities_payload = orjson.loads(capabilities.contents[0].content)
    if "list_tables" not in capabilities_payload.get("tools", []):
        raise AssertionError(capabilities_payload)


def test_langchain_sql_database_can_reflect_sqlite_engine() -> None:
    """Create a LangChain SQLDatabase from a SQLite engine."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))

    database = create_sql_database_from_engine(engine)
    table_info = database.get_table_info(["users"])
    engine.dispose()

    if "users" not in table_info:
        raise AssertionError(table_info)


def test_langchain_runtime_tools_hide_runtime_from_json_schema() -> None:
    """Exclude injected runtime arguments from generated tool schemas."""

    if (
        find_spec("langchain_core.tools") is None
        or find_spec("langchain.tools") is None
    ):
        return

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="stub",
                dialect=Dialect.SQLITE,
                url="sqlite+pysqlite:///:memory:",
                safety=SafetySettings(),
            )
        ],
        profiling=ProfilingSettings(),
        artifacts=ArtifactSettings(root_dir="var/sqldbagent-test"),
    )
    services = ServiceContainer(
        inspector=StubInspectionService(),
        profiler=StubProfilingService(),
        snapshotter=StubSnapshotService(),
        prompt_service=StubPromptService(),
        datasource_name="stub",
        settings=settings,
    )

    tool_map = {tool.name: tool for tool in create_langchain_tools(services)}
    runtime_tool_names = [
        "explore_and_save_prompt_context",
        "get_runtime_context",
        "load_database_memory",
        "remember_database_context",
        "sync_database_memory",
    ]

    for tool_name in runtime_tool_names:
        tool_args = tool_map[tool_name].args
        if "runtime" in tool_args:
            raise AssertionError(f"{tool_name} leaked runtime into tool schema")
