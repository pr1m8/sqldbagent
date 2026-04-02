"""Shared pytest configuration."""

from __future__ import annotations

from os import getenv
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, Table, create_engine, text

from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.core.errors import ConfigurationError


@pytest.fixture
def isolated_sqlite_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, str]:
    """Configure environment variables for a temporary SQLite datasource.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory for the SQLite database file.

    Returns:
        dict[str, str]: Environment values used by the test.
    """

    sqlite_path = tmp_path / "sqldbagent.db"
    values = {
        "SQLITE_PATH": str(sqlite_path),
        "SQLDBAGENT_ENV": "test",
    }

    for key, value in values.items():
        monkeypatch.setenv(key, value)

    return values


def _load_env_settings() -> AppSettings:
    """Load application settings from the repo `.env` file.

    Returns:
        AppSettings: Freshly loaded application settings.
    """

    load_settings.cache_clear()
    return load_settings()


def _has_datasource(settings: AppSettings, datasource_name: str) -> bool:
    """Check whether a datasource is configured.

    Args:
        settings: Application settings loaded from `.env`.
        datasource_name: Datasource identifier to check.

    Returns:
        bool: Whether the datasource exists in settings.
    """

    try:
        settings.get_datasource(datasource_name)
    except ConfigurationError:
        return False
    return True


@pytest.fixture
def configured_app_settings() -> AppSettings:
    """Load the repository settings from `.env`.

    Returns:
        AppSettings: Repository application settings.
    """

    return _load_env_settings()


@pytest.fixture
def live_postgres_settings(configured_app_settings: AppSettings) -> AppSettings:
    """Return repo settings when the configured Postgres datasource is reachable.

    Args:
        configured_app_settings: Application settings loaded from `.env`.

    Returns:
        AppSettings: Settings with a reachable Postgres datasource.
    """

    try:
        datasource = configured_app_settings.get_datasource("postgres")
    except ConfigurationError:
        pytest.skip("postgres datasource is not configured in .env")

    engine = create_engine(datasource.url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"postgres datasource is unreachable: {exc}")
    finally:
        engine.dispose()

    return configured_app_settings


@pytest.fixture
def live_postgres_demo_settings(monkeypatch: pytest.MonkeyPatch) -> AppSettings:
    """Return repo settings when the configured demo Postgres datasource is reachable.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        AppSettings: Settings with a reachable demo Postgres datasource.
    """

    defaults = {
        "POSTGRES_DEMO_HOST": "127.0.0.1",
        "POSTGRES_DEMO_PORT": "5433",
        "POSTGRES_DEMO_DB": "sqldbagent_demo",
        "POSTGRES_DEMO_USER": "sqldbagent",
        "POSTGRES_DEMO_PASSWORD": "sqldbagent",  # nosec B105
    }
    for key, value in defaults.items():
        monkeypatch.setenv(key, getenv(key, value))

    configured_app_settings = _load_env_settings()
    try:
        datasource = configured_app_settings.get_datasource("postgres_demo")
    except ConfigurationError:
        pytest.skip("postgres_demo datasource is not configured in .env")

    engine = create_engine(datasource.url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"postgres_demo datasource is unreachable: {exc}")
    finally:
        engine.dispose()

    alembic_command_module = pytest.importorskip("alembic.command")
    alembic_config_module = pytest.importorskip("alembic.config")
    alembic_command = alembic_command_module
    alembic_config = alembic_config_module.Config("alembic.ini")
    monkeypatch_context = pytest.MonkeyPatch.context()
    with monkeypatch_context as monkeypatch:
        monkeypatch.setenv("SQLDBAGENT_ALEMBIC_DATASOURCE", "postgres_demo")
        alembic_command.upgrade(alembic_config, "head")

    return configured_app_settings


@pytest.fixture
def live_postgres_schema(live_postgres_settings: AppSettings) -> str:
    """Create a temporary Postgres schema populated for live tests.

    Args:
        live_postgres_settings: Settings whose Postgres datasource is reachable.

    Yields:
        str: Temporary schema name for the test run.
    """

    datasource = live_postgres_settings.get_datasource("postgres")
    schema_name = f"sqldbagent_{uuid4().hex[:8]}"
    engine = create_engine(datasource.url)
    try:
        with engine.begin() as connection:
            teams_create_sql = f"""
                    CREATE TABLE "{schema_name}"."teams" (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE
                    )
                    """  # nosec B608
            users_create_sql = f"""
                    CREATE TABLE "{schema_name}"."users" (
                        id INTEGER PRIMARY KEY,
                        team_id INTEGER REFERENCES "{schema_name}"."teams"(id),
                        email TEXT,
                        status TEXT NOT NULL DEFAULT 'active'
                    )
                    """  # nosec B608
            index_create_sql = f"""
                    CREATE INDEX "ix_{schema_name}_users_team_id"
                    ON "{schema_name}"."users"(team_id)
                    """  # nosec B608
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            connection.execute(text(teams_create_sql))
            connection.execute(text(users_create_sql))
            connection.execute(text(index_create_sql))
            metadata = MetaData()
            teams = Table(
                "teams", metadata, schema=schema_name, autoload_with=connection
            )
            users = Table(
                "users", metadata, schema=schema_name, autoload_with=connection
            )
            connection.execute(
                teams.insert(),
                [{"id": 1, "name": "data"}],
            )
            connection.execute(
                users.insert(),
                [
                    {
                        "id": 1,
                        "team_id": 1,
                        "email": "a@example.com",
                        "status": "active",
                    },
                    {
                        "id": 2,
                        "team_id": 1,
                        "email": "b@example.com",
                        "status": "active",
                    },
                    {
                        "id": 3,
                        "team_id": 1,
                        "email": None,
                        "status": "inactive",
                    },
                ],
            )

        yield schema_name
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        engine.dispose()


@pytest.fixture
def live_qdrant_settings(configured_app_settings: AppSettings) -> AppSettings:
    """Return repo settings when the configured Qdrant service is reachable.

    Args:
        configured_app_settings: Application settings loaded from `.env`.

    Returns:
        AppSettings: Settings with a reachable Qdrant service.
    """

    client_module = pytest.importorskip("qdrant_client")
    try:
        client = client_module.QdrantClient(
            url=configured_app_settings.retrieval.qdrant_url,
            api_key=configured_app_settings.retrieval.qdrant_api_key,
            grpc_port=configured_app_settings.retrieval.qdrant_grpc_port,
            prefer_grpc=configured_app_settings.retrieval.qdrant_prefer_grpc,
            check_compatibility=False,
        )
        client.get_collections()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"qdrant service is unreachable: {exc}")

    return configured_app_settings


@pytest.fixture
def live_mssql_settings(configured_app_settings: AppSettings) -> AppSettings:
    """Return repo settings when the configured MSSQL datasource is reachable.

    Args:
        configured_app_settings: Application settings loaded from `.env`.

    Returns:
        AppSettings: Settings with a reachable MSSQL datasource.
    """

    pytest.importorskip("pyodbc")
    try:
        datasource = configured_app_settings.get_datasource("mssql")
    except ConfigurationError:
        pytest.skip("mssql datasource is not configured in .env")

    engine = create_engine(datasource.url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"mssql datasource is unreachable: {exc}")
    finally:
        engine.dispose()

    return configured_app_settings


@pytest.fixture
def live_mssql_schema(live_mssql_settings: AppSettings) -> str:
    """Create a temporary MSSQL schema populated for live tests.

    Args:
        live_mssql_settings: Settings whose MSSQL datasource is reachable.

    Yields:
        str: Temporary schema name for the test run.
    """

    datasource = live_mssql_settings.get_datasource("mssql")
    schema_name = f"sqldbagent_{uuid4().hex[:8]}"
    engine = create_engine(datasource.url)
    try:
        with engine.begin() as connection:
            teams_create_sql = f"""
                    CREATE TABLE [{schema_name}].[teams] (
                        id INT NOT NULL PRIMARY KEY,
                        name NVARCHAR(255) NOT NULL UNIQUE
                    )
                    """  # nosec B608
            users_create_sql = f"""
                    CREATE TABLE [{schema_name}].[users] (
                        id INT NOT NULL PRIMARY KEY,
                        team_id INT NULL,
                        email NVARCHAR(255) NULL,
                        status NVARCHAR(32) NOT NULL DEFAULT 'active',
                        CONSTRAINT [FK_{schema_name}_users_team]
                        FOREIGN KEY(team_id) REFERENCES [{schema_name}].[teams](id)
                    )
                    """  # nosec B608
            index_create_sql = f"""
                    CREATE INDEX [IX_{schema_name}_users_team_id]
                    ON [{schema_name}].[users](team_id)
                    """  # nosec B608
            connection.execute(text(f"CREATE SCHEMA [{schema_name}]"))  # nosec B608
            connection.execute(text(teams_create_sql))
            connection.execute(text(users_create_sql))
            connection.execute(text(index_create_sql))
            connection.execute(text(f"""
                    INSERT INTO [{schema_name}].[teams] (id, name)
                    VALUES (1, 'data')
                    """))  # nosec B608
            connection.execute(text(f"""
                    INSERT INTO [{schema_name}].[users] (id, team_id, email, status)
                    VALUES
                        (1, 1, 'a@example.com', 'active'),
                        (2, 1, 'b@example.com', 'active'),
                        (3, 1, NULL, 'inactive')
                    """))  # nosec B608

        yield schema_name
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(f"DROP TABLE IF EXISTS [{schema_name}].[users]")  # nosec B608
            )
            connection.execute(
                text(f"DROP TABLE IF EXISTS [{schema_name}].[teams]")  # nosec B608
            )
            connection.execute(text(f"DROP SCHEMA [{schema_name}]"))  # nosec B608
        engine.dispose()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests when live database settings are unavailable.

    Args:
        config: Active pytest config.
        items: Collected test items.
    """

    del config
    settings = _load_env_settings()
    has_postgres = _has_datasource(settings, "postgres")
    has_mssql = _has_datasource(settings, "mssql")

    for item in items:
        if "integration" in item.keywords and not (has_postgres or has_mssql):
            item.add_marker(
                pytest.mark.skip(
                    reason="integration tests require postgres or mssql datasource config in .env"
                )
            )
