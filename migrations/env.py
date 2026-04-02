"""Alembic environment for the switchable demo datasource."""

from __future__ import annotations

from logging.config import fileConfig
from os import getenv

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import URL

from sqldbagent.core.config import load_settings
from sqldbagent.core.errors import ConfigurationError

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _datasource_url() -> str:
    """Resolve the datasource URL Alembic should migrate."""

    settings = load_settings()
    datasource_name = getenv("SQLDBAGENT_ALEMBIC_DATASOURCE", "postgres_demo")
    try:
        return settings.get_datasource(datasource_name).url
    except ConfigurationError:
        if datasource_name != "postgres_demo":
            raise
        return URL.create(
            "postgresql+psycopg",
            username=getenv("POSTGRES_DEMO_USER", "sqldbagent"),
            password=getenv("POSTGRES_DEMO_PASSWORD", "sqldbagent"),
            host=getenv("POSTGRES_DEMO_HOST", "127.0.0.1"),
            port=int(getenv("POSTGRES_DEMO_PORT", "5433")),
            database=getenv("POSTGRES_DEMO_DB", "sqldbagent_demo"),
        ).render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    context.configure(
        url=_datasource_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _datasource_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
