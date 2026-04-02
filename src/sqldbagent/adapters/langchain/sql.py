"""LangChain community SQL adapter helpers.

This module exposes LangChain's SQLDatabase integration for orchestration use
cases. It is useful for experimentation and retrieval-oriented metadata access,
but it should not become the primary query execution path for agent-facing SQL.
The package safety layer remains the long-term execution boundary.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.engines.factory import DatasourceRegistry, EngineManager


def _build_engine(datasource_name: str, settings: AppSettings | None = None) -> Engine:
    """Build an engine for a datasource.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.

    Returns:
        Engine: SQLAlchemy engine for the requested datasource.
    """

    resolved_settings = settings or load_settings()
    registry = DatasourceRegistry.from_settings(resolved_settings)
    return EngineManager(registry).create_sync_engine(datasource_name)


def create_sql_database(
    datasource_name: str,
    *,
    settings: AppSettings | None = None,
    include_tables: list[str] | None = None,
    ignore_tables: list[str] | None = None,
    view_support: bool = True,
    sample_rows_in_table_info: int = 0,
) -> Any:
    """Create a LangChain community SQLDatabase for a datasource.

    Args:
        datasource_name: Datasource identifier.
        settings: Optional application settings.
        include_tables: Optional allowlist of tables exposed through SQLDatabase.
        ignore_tables: Optional denylist of tables excluded from SQLDatabase.
        view_support: Whether reflected views should be included.
        sample_rows_in_table_info: Sample rows included in LangChain table info.

    Returns:
        Any: LangChain `SQLDatabase` instance.
    """

    sql_database_module = require_dependency(
        "langchain_community.utilities.sql_database",
        "langchain-community",
    )
    engine = _build_engine(datasource_name, settings=settings)
    return sql_database_module.SQLDatabase(
        engine=engine,
        include_tables=include_tables,
        ignore_tables=ignore_tables,
        view_support=view_support,
        sample_rows_in_table_info=sample_rows_in_table_info,
    )


def create_sql_database_from_engine(
    engine: Engine,
    *,
    include_tables: list[str] | None = None,
    ignore_tables: list[str] | None = None,
    view_support: bool = True,
    sample_rows_in_table_info: int = 0,
) -> Any:
    """Create a LangChain `SQLDatabase` directly from an engine.

    Args:
        engine: SQLAlchemy engine.
        include_tables: Optional allowlist of tables exposed through SQLDatabase.
        ignore_tables: Optional denylist of tables excluded from SQLDatabase.
        view_support: Whether reflected views should be included.
        sample_rows_in_table_info: Sample rows included in LangChain table info.

    Returns:
        Any: LangChain `SQLDatabase` instance.
    """

    sql_database_module = require_dependency(
        "langchain_community.utilities.sql_database",
        "langchain-community",
    )
    return sql_database_module.SQLDatabase(
        engine=engine,
        include_tables=include_tables,
        ignore_tables=ignore_tables,
        view_support=view_support,
        sample_rows_in_table_info=sample_rows_in_table_info,
    )


def create_sql_database_toolkit(
    datasource_name: str,
    *,
    llm: Any,
    settings: AppSettings | None = None,
    include_tables: list[str] | None = None,
    ignore_tables: list[str] | None = None,
    view_support: bool = True,
    sample_rows_in_table_info: int = 0,
) -> Any:
    """Create a LangChain community SQLDatabaseToolkit.

    This is useful for orchestration experiments, but it should not be exposed
    as the default safe query surface before the package safety layer is in
    place.

    Args:
        datasource_name: Datasource identifier.
        llm: LangChain-compatible language model used by the toolkit.
        settings: Optional application settings.
        include_tables: Optional allowlist of tables exposed through SQLDatabase.
        ignore_tables: Optional denylist of tables excluded from SQLDatabase.
        view_support: Whether reflected views should be included.
        sample_rows_in_table_info: Sample rows included in LangChain table info.

    Returns:
        Any: LangChain `SQLDatabaseToolkit` instance.
    """

    toolkit_module = require_dependency(
        "langchain_community.agent_toolkits.sql.toolkit",
        "langchain-community",
    )
    database = create_sql_database(
        datasource_name,
        settings=settings,
        include_tables=include_tables,
        ignore_tables=ignore_tables,
        view_support=view_support,
        sample_rows_in_table_info=sample_rows_in_table_info,
    )
    return toolkit_module.SQLDatabaseToolkit(db=database, llm=llm)


def create_sql_database_loader(
    datasource_name: str,
    *,
    query: str,
    settings: AppSettings | None = None,
    parameters: dict[str, Any] | None = None,
    include_query_into_metadata: bool = False,
) -> Any:
    """Create a LangChain community SQLDatabaseLoader.

    This is useful for targeted row-to-document workflows, but it is not the
    primary metadata retrieval path. The default RAG path in sqldbagent should
    prefer stored snapshot documents and the vector store.

    Args:
        datasource_name: Datasource identifier.
        query: SQL query used to create documents.
        settings: Optional application settings.
        parameters: Optional query parameters.
        include_query_into_metadata: Whether to include the query in metadata.

    Returns:
        Any: LangChain `SQLDatabaseLoader` instance.
    """

    loader_module = require_dependency(
        "langchain_community.document_loaders.sql_database",
        "langchain-community",
    )
    database = create_sql_database(
        datasource_name,
        settings=settings,
    )
    return loader_module.SQLDatabaseLoader(
        query=query,
        db=database,
        parameters=parameters,
        include_query_into_metadata=include_query_into_metadata,
    )
