"""Datasource registry and SQLAlchemy engine factories."""

from __future__ import annotations

from collections.abc import Iterable
from re import sub

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from sqldbagent.core.config import AppSettings, DatasourceSettings
from sqldbagent.core.enums import Dialect
from sqldbagent.core.errors import ConfigurationError


class DatasourceRegistry:
    """Resolve datasource configuration by name.

    Attributes:
        _datasources: Datasources keyed by stable name.
    """

    def __init__(self, datasources: Iterable[DatasourceSettings]) -> None:
        """Initialize the registry.

        Args:
            datasources: Datasources to register.

        Raises:
            ConfigurationError: If duplicate datasource names are provided.
        """

        self._datasources: dict[str, DatasourceSettings] = {}

        for datasource in datasources:
            if datasource.name in self._datasources:
                raise ConfigurationError(
                    f"duplicate datasource names: {datasource.name}"
                )
            self._datasources[datasource.name] = datasource

    @classmethod
    def from_settings(cls, settings: AppSettings) -> "DatasourceRegistry":
        """Build a registry from application settings.

        Args:
            settings: Application settings.

        Returns:
            DatasourceRegistry: Registry for the configured datasources.
        """

        return cls(settings.datasources)

    def names(self) -> list[str]:
        """Return sorted datasource names.

        Returns:
            list[str]: Sorted datasource identifiers.
        """

        return sorted(self._datasources)

    def get(self, name: str) -> DatasourceSettings:
        """Return a datasource by name.

        Args:
            name: Datasource identifier.

        Returns:
            DatasourceSettings: Matching datasource settings.

        Raises:
            ConfigurationError: If the datasource is unknown.
        """

        try:
            return self._datasources[name]
        except KeyError as exc:
            raise ConfigurationError(f"unknown datasource: {name}") from exc


class EngineManager:
    """Create SQLAlchemy engines from datasource settings."""

    def __init__(self, registry: DatasourceRegistry) -> None:
        """Initialize the engine manager.

        Args:
            registry: Datasource registry used for engine lookup.
        """

        self._registry = registry

    def create_sync_engine(self, datasource_name: str) -> Engine:
        """Create a sync SQLAlchemy engine for a datasource.

        Args:
            datasource_name: Datasource identifier.

        Returns:
            Engine: Configured SQLAlchemy engine.
        """

        datasource = self._registry.get(datasource_name)
        return self.create_sync_engine_from_settings(datasource)

    def create_sync_engine_from_settings(
        self, datasource: DatasourceSettings
    ) -> Engine:
        """Create a sync engine directly from datasource settings.

        Args:
            datasource: Datasource settings.

        Returns:
            Engine: Configured SQLAlchemy engine.
        """

        engine_kwargs: dict[str, object] = {"echo": datasource.echo}

        if datasource.dialect.value != "sqlite":
            engine_kwargs["pool_size"] = datasource.pool.size
            engine_kwargs["max_overflow"] = datasource.pool.max_overflow
            engine_kwargs["pool_timeout"] = datasource.pool.timeout_seconds

        engine = create_engine(
            self._apply_url_policy(datasource.url, datasource),
            **engine_kwargs,
        )
        self._apply_connection_policy(engine, datasource)
        return engine

    def create_async_engine(self, datasource_name: str) -> AsyncEngine:
        """Create an async SQLAlchemy engine for a datasource.

        Args:
            datasource_name: Datasource identifier.

        Returns:
            AsyncEngine: Configured SQLAlchemy async engine.
        """

        datasource = self._registry.get(datasource_name)
        return self.create_async_engine_from_settings(datasource)

    def create_async_engine_from_settings(
        self, datasource: DatasourceSettings
    ) -> AsyncEngine:
        """Create an async engine directly from datasource settings.

        Args:
            datasource: Datasource settings.

        Returns:
            AsyncEngine: Configured SQLAlchemy async engine.
        """

        async_url = self._to_async_url(datasource.url)
        engine_kwargs: dict[str, object] = {"echo": datasource.echo}

        if datasource.dialect.value != "sqlite":
            engine_kwargs["pool_size"] = datasource.pool.size
            engine_kwargs["max_overflow"] = datasource.pool.max_overflow
            engine_kwargs["pool_timeout"] = datasource.pool.timeout_seconds

        engine = create_async_engine(
            self._apply_url_policy(async_url, datasource),
            **engine_kwargs,
        )
        self._apply_connection_policy(engine, datasource)
        return engine

    def _apply_url_policy(self, url: str, datasource: DatasourceSettings) -> str:
        """Apply dialect-specific connection-string safety policy."""

        if not datasource.safety.read_only or datasource.dialect != Dialect.MSSQL:
            return url

        parsed = make_url(url)
        query = dict(parsed.query)
        normalized_keys = {key: key.replace(" ", "").lower() for key in query}

        if "odbc_connect" in query:
            odbc_connect = str(query["odbc_connect"])
            if "applicationintent=" in odbc_connect.lower():
                query["odbc_connect"] = sub(
                    r"(?i)ApplicationIntent\s*=\s*[^;]+",
                    "ApplicationIntent=ReadOnly",
                    odbc_connect,
                )
            else:
                separator = (
                    "" if not odbc_connect or odbc_connect.endswith(";") else ";"
                )
                query["odbc_connect"] = (
                    f"{odbc_connect}{separator}ApplicationIntent=ReadOnly"
                )
            return parsed.set(query=query).render_as_string(hide_password=False)

        query = {
            key: value
            for key, value in query.items()
            if normalized_keys[key] != "applicationintent"
        }
        query["ApplicationIntent"] = "ReadOnly"
        return parsed.set(query=query).render_as_string(hide_password=False)

    def _apply_connection_policy(
        self,
        engine: Engine | AsyncEngine,
        datasource: DatasourceSettings,
    ) -> None:
        """Attach read-only and timeout policies to new engine connections."""

        target = engine.sync_engine if isinstance(engine, AsyncEngine) else engine

        if datasource.dialect == Dialect.SQLITE:
            if not datasource.safety.read_only:
                return

            @event.listens_for(target, "connect")
            def configure_sqlite_read_only(  # noqa: ANN202
                dbapi_connection: object,
                connection_record: object,
            ) -> None:
                del connection_record
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute("PRAGMA query_only = ON")
                finally:
                    cursor.close()

            return

        if datasource.dialect == Dialect.POSTGRES:

            @event.listens_for(target, "connect")
            def configure_postgres_session(  # noqa: ANN202
                dbapi_connection: object,
                connection_record: object,
            ) -> None:
                del connection_record
                cursor = dbapi_connection.cursor()
                try:
                    if datasource.safety.read_only:
                        cursor.execute("SET default_transaction_read_only = on")
                    timeout_ms = int(datasource.safety.statement_timeout_seconds * 1000)
                    cursor.execute(f"SET statement_timeout = {timeout_ms}")
                finally:
                    cursor.close()

    def _to_async_url(self, url: str) -> str:
        """Convert a sync URL to the corresponding async URL when needed.

        Args:
            url: Sync SQLAlchemy URL.

        Returns:
            str: Async-compatible SQLAlchemy URL.

        Raises:
            ConfigurationError: If the URL cannot be mapped to an async driver.
        """

        if url.startswith("sqlite+pysqlite://"):
            return url.replace("sqlite+pysqlite://", "sqlite+aiosqlite://", 1)
        if url.startswith("mssql+pyodbc://"):
            return url.replace("mssql+pyodbc://", "mssql+aioodbc://", 1)
        if url.startswith("postgresql+psycopg://"):
            return url

        raise ConfigurationError(
            f"no async URL mapping configured for datasource URL: {url}"
        )
