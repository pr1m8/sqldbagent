"""Schema diagram service tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from sqldbagent.core.config import ArtifactSettings
from sqldbagent.core.models.catalog import (
    ColumnModel,
    ForeignKeyModel,
    TableModel,
    UniqueConstraintModel,
)
from sqldbagent.diagrams.service import SchemaDiagramService
from sqldbagent.introspect.service import SQLAlchemyInspectionService
from sqldbagent.profile.service import SQLAlchemyProfilingService
from sqldbagent.snapshot.service import SnapshotService


def test_schema_diagram_service_renders_mermaid_and_graph(tmp_path: Path) -> None:
    """Render Mermaid and graph JSON from a stored schema snapshot."""

    database_path = tmp_path / "diagram.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)"
            )
        )
        connection.execute(text("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    team_id INTEGER NOT NULL REFERENCES teams(id),
                    email TEXT
                )
                """))
        connection.execute(text("INSERT INTO teams (id, name) VALUES (1, 'data')"))
        connection.execute(text("""
                INSERT INTO users (id, team_id, email)
                VALUES (1, 1, 'a@example.com')
                """))

    inspector = SQLAlchemyInspectionService(engine)
    profiler = SQLAlchemyProfilingService(engine=engine, inspector=inspector)
    snapshotter = SnapshotService(
        datasource_name="sqlite",
        inspector=inspector,
        profiler=profiler,
        artifacts=ArtifactSettings(root_dir=str(tmp_path), snapshots_dir="snapshots"),
    )
    bundle = snapshotter.create_schema_snapshot("main", sample_size=1)
    diagram_service = SchemaDiagramService(
        artifacts=ArtifactSettings(root_dir=str(tmp_path), diagrams_dir="diagrams")
    )
    diagram_bundle = diagram_service.create_diagram_bundle(bundle)
    path = diagram_service.save_diagram_bundle(diagram_bundle)
    loaded = SchemaDiagramService.load_diagram_bundle(path)
    mermaid_path = diagram_service.mermaid_path(
        datasource_name="sqlite",
        schema_name="main",
        snapshot_id=diagram_bundle.snapshot_id,
    )
    graph_path = diagram_service.graph_path(
        datasource_name="sqlite",
        schema_name="main",
        snapshot_id=diagram_bundle.snapshot_id,
    )
    engine.dispose()

    if "erDiagram" not in loaded.mermaid_erd:
        raise AssertionError(loaded.mermaid_erd)
    if "MAIN_TEAMS" not in loaded.mermaid_erd:
        raise AssertionError(loaded.mermaid_erd)
    if "MAIN_USERS" not in loaded.mermaid_erd:
        raise AssertionError(loaded.mermaid_erd)
    if "direction LR" not in loaded.mermaid_erd:
        raise AssertionError(loaded.mermaid_erd)
    if "MAIN_TEAMS ||--o{ MAIN_USERS" not in loaded.mermaid_erd:
        raise AssertionError(loaded.mermaid_erd)
    if "%%" in loaded.mermaid_erd:
        raise AssertionError(loaded.mermaid_erd)
    if len(loaded.graph.nodes) != 2:
        raise AssertionError(loaded.graph.nodes)
    if len(loaded.graph.edges) != 1:
        raise AssertionError(loaded.graph.edges)
    if not mermaid_path.exists():
        raise AssertionError(mermaid_path)
    if not graph_path.exists():
        raise AssertionError(graph_path)


def test_schema_diagram_service_formats_multiple_mermaid_keys() -> None:
    """Render multiple Mermaid attribute keys using Mermaid's comma syntax."""

    service = SchemaDiagramService(artifacts=ArtifactSettings())
    lines = service._mermaid_entity_block(  # noqa: SLF001
        table=TableModel(
            schema_name="public",
            name="order_items",
            columns=[
                ColumnModel(name="id", data_type="INTEGER"),
                ColumnModel(name="order_id", data_type="INTEGER"),
            ],
            primary_key=["order_id"],
            foreign_keys=[
                ForeignKeyModel(columns=["order_id"], referred_table="orders"),
            ],
            unique_constraints=[
                UniqueConstraintModel(columns=["order_id"]),
            ],
        ),
        profile=None,
    )

    if "INTEGER order_id PK, UK, FK" not in "\n".join(lines):
        raise AssertionError(lines)
