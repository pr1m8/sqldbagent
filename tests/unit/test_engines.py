"""Engine factory tests."""

from sqlalchemy.ext.asyncio import AsyncEngine

from sqldbagent.core.config import AppSettings, DatasourceSettings
from sqldbagent.core.enums import Dialect
from sqldbagent.engines.factory import DatasourceRegistry, EngineManager


def test_registry_names_are_sorted() -> None:
    """Return sorted datasource names."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(name="zeta", dialect=Dialect.SQLITE, url="sqlite://"),
            DatasourceSettings(name="alpha", dialect=Dialect.SQLITE, url="sqlite://"),
        ]
    )

    registry = DatasourceRegistry.from_settings(settings)

    if registry.names() != ["alpha", "zeta"]:
        raise AssertionError(registry.names())


def test_engine_manager_creates_sqlite_engine() -> None:
    """Create a SQLAlchemy engine from datasource settings."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="local",
                dialect=Dialect.SQLITE,
                url="sqlite+pysqlite:///:memory:",
            )
        ]
    )

    registry = DatasourceRegistry.from_settings(settings)
    engine = EngineManager(registry).create_sync_engine("local")

    if engine.dialect.name != "sqlite":
        raise AssertionError(engine.dialect.name)


def test_engine_manager_creates_async_sqlite_engine() -> None:
    """Create an async SQLAlchemy engine from datasource settings."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="local",
                dialect=Dialect.SQLITE,
                url="sqlite+pysqlite:///:memory:",
            )
        ]
    )

    registry = DatasourceRegistry.from_settings(settings)
    engine = EngineManager(registry).create_async_engine("local")

    if not isinstance(engine, AsyncEngine):
        raise AssertionError(engine)
    if not engine.url.drivername.startswith("sqlite+aiosqlite"):
        raise AssertionError(engine.url)


def test_engine_manager_applies_sqlite_query_only_policy() -> None:
    """Enable SQLite query-only mode when datasource safety is read-only."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="local",
                dialect=Dialect.SQLITE,
                url="sqlite+pysqlite:///:memory:",
            )
        ]
    )

    registry = DatasourceRegistry.from_settings(settings)
    engine = EngineManager(registry).create_sync_engine("local")

    with engine.connect() as connection:
        result = connection.exec_driver_sql("PRAGMA query_only").scalar_one()
    engine.dispose()

    if result != 1:
        raise AssertionError(result)


def test_engine_manager_adds_mssql_application_intent_for_read_only() -> None:
    """Add MSSQL read intent to the connection URL when safety is read-only."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="warehouse",
                dialect=Dialect.MSSQL,
                url=(
                    "mssql+pyodbc://sa:secret@sql.example.com:1433/demo?"
                    "driver=ODBC+Driver+18+for+SQL+Server"
                ),
            )
        ]
    )

    registry = DatasourceRegistry.from_settings(settings)
    engine = EngineManager(registry).create_sync_engine("warehouse")
    try:
        if engine.url.query.get("ApplicationIntent") != "ReadOnly":
            raise AssertionError(engine.url)
    finally:
        engine.dispose()


def test_engine_manager_adds_mssql_application_intent_to_odbc_connect() -> None:
    """Append MSSQL read intent when the URL uses an exact ODBC string."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="warehouse",
                dialect=Dialect.MSSQL,
                url=(
                    "mssql+pyodbc:///?odbc_connect="
                    "DRIVER%3D%7BODBC+Driver+18+for+SQL+Server%7D%3B"
                    "SERVER%3Dsql.example.com%3BDATABASE%3Ddemo%3BUID%3Dsa%3BPWD%3Dsecret"
                ),
            )
        ]
    )

    registry = DatasourceRegistry.from_settings(settings)
    engine = EngineManager(registry).create_sync_engine("warehouse")
    try:
        odbc_connect = engine.url.query.get("odbc_connect") or ""
        if "ApplicationIntent=ReadOnly" not in odbc_connect:
            raise AssertionError(engine.url)
    finally:
        engine.dispose()
