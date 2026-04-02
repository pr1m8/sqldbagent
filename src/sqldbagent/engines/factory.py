"""Datasource registry and SQLAlchemy engine factories."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from sqldbagent.core.config import AppSettings, DatasourceSettings
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

        return create_engine(datasource.url, **engine_kwargs)

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

        return create_async_engine(async_url, **engine_kwargs)

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
