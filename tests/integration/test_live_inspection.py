"""Optional live database integration tests."""

from __future__ import annotations

import pytest

from sqldbagent.engines.factory import DatasourceRegistry, EngineManager
from sqldbagent.introspect.service import SQLAlchemyInspectionService


@pytest.mark.integration
def test_postgres_datasource_is_constructed_from_env(
    configured_app_settings,
) -> None:
    """Build and validate a Postgres datasource from environment settings."""

    datasource = configured_app_settings.get_datasource("postgres")

    if datasource.dialect.value != "postgres":
        raise AssertionError(datasource)


@pytest.mark.integration
def test_postgres_engine_can_inspect_live_schema(
    live_postgres_settings,
    live_postgres_schema: str,
) -> None:
    """Reflect and describe a live Postgres schema from the configured datasource."""

    registry = DatasourceRegistry.from_settings(live_postgres_settings)
    engine = EngineManager(registry).create_sync_engine("postgres")
    inspector = SQLAlchemyInspectionService(engine)
    schemas = inspector.list_schemas()
    table = inspector.describe_table("users", schema=live_postgres_schema)

    if live_postgres_schema not in schemas:
        raise AssertionError(schemas)
    if table.schema_name != live_postgres_schema:
        raise AssertionError(table)
