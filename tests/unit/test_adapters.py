"""Adapter bootstrap tests."""

import asyncio
from importlib.util import find_spec

from sqlalchemy import create_engine, text

from sqldbagent.adapters.langchain import (
    create_langchain_tools,
    create_sql_database_from_engine,
)
from sqldbagent.adapters.mcp import create_mcp_server
from sqldbagent.core.bootstrap import ServiceContainer
from sqldbagent.core.errors import AdapterDependencyError
from sqldbagent.core.models.catalog import ColumnModel, TableModel, ViewModel
from sqldbagent.core.models.profile import TableProfileModel
from sqldbagent.core.models.query import QueryExecutionResult
from sqldbagent.safety.models import QueryGuardResult


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
