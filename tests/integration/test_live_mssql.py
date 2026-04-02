"""Optional live MSSQL integration tests."""

from __future__ import annotations

import pytest

from sqldbagent.engines.factory import DatasourceRegistry, EngineManager
from sqldbagent.introspect.service import SQLAlchemyInspectionService


@pytest.mark.integration
@pytest.mark.enable_socket
def test_mssql_engine_can_inspect_live_schema(
    live_mssql_settings,
    live_mssql_schema: str,
) -> None:
    """Reflect and describe a live MSSQL schema from the configured datasource."""

    registry = DatasourceRegistry.from_settings(live_mssql_settings)
    engine = EngineManager(registry).create_sync_engine("mssql")
    inspector = SQLAlchemyInspectionService(engine)
    schemas = inspector.list_schemas()
    table = inspector.describe_table("users", schema=live_mssql_schema)
    engine.dispose()

    if live_mssql_schema not in schemas:
        raise AssertionError(schemas)
    if table.schema_name != live_mssql_schema:
        raise AssertionError(table)
