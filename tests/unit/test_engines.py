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
