"""Snapshot service tests."""

from pathlib import Path

from sqlalchemy import create_engine, text

from sqldbagent.core.config import ArtifactSettings
from sqldbagent.introspect.service import SQLAlchemyInspectionService
from sqldbagent.profile.service import SQLAlchemyProfilingService
from sqldbagent.snapshot.service import SnapshotService


def test_snapshot_service_saves_and_loads_schema_snapshot(tmp_path: Path) -> None:
    """Persist and reload a schema snapshot bundle."""

    database_path = tmp_path / "snapshot.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
        )

    inspector = SQLAlchemyInspectionService(engine)
    profiler = SQLAlchemyProfilingService(engine=engine, inspector=inspector)
    snapshotter = SnapshotService(
        datasource_name="sqlite",
        inspector=inspector,
        profiler=profiler,
        artifacts=ArtifactSettings(root_dir=str(tmp_path), snapshots_dir="snapshots"),
    )

    bundle = snapshotter.create_schema_snapshot("main", sample_size=1)
    path = snapshotter.save_snapshot(bundle)
    loaded = SnapshotService.load_snapshot(path)
    inventory = SnapshotService.list_saved_snapshots(
        ArtifactSettings(root_dir=str(tmp_path), snapshots_dir="snapshots"),
        datasource_name="sqlite",
        schema_name="main",
    )
    latest = SnapshotService.load_latest_snapshot(
        ArtifactSettings(root_dir=str(tmp_path), snapshots_dir="snapshots"),
        datasource_name="sqlite",
        schema_name="main",
    )
    engine.dispose()

    if not path.exists():
        raise AssertionError(path)
    if loaded.schema_metadata.name != "main":
        raise AssertionError(loaded)
    if loaded.content_hash is None:
        raise AssertionError(loaded.content_hash)
    if [profile.table_name for profile in loaded.profiles] != ["users"]:
        raise AssertionError(loaded.profiles)
    if len(inventory) != 1:
        raise AssertionError(inventory)
    if latest.snapshot_id != loaded.snapshot_id:
        raise AssertionError(latest)


def test_snapshot_service_diffs_snapshots(tmp_path: Path) -> None:
    """Diff two schema snapshots and report structural changes."""

    database_path = tmp_path / "snapshot-diff.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
        )

    inspector = SQLAlchemyInspectionService(engine)
    profiler = SQLAlchemyProfilingService(engine=engine, inspector=inspector)
    snapshotter = SnapshotService(
        datasource_name="sqlite",
        inspector=inspector,
        profiler=profiler,
        artifacts=ArtifactSettings(root_dir=str(tmp_path), snapshots_dir="snapshots"),
    )

    left = snapshotter.create_schema_snapshot("main", sample_size=1)

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN team_id INTEGER"))
        connection.execute(
            text("CREATE VIEW active_users AS SELECT id, email FROM users")
        )

    right = snapshotter.create_schema_snapshot("main", sample_size=1)
    diff = SnapshotService.diff_snapshots(left, right)
    engine.dispose()

    if diff.added_views != ["main.active_users"]:
        raise AssertionError(diff)
    if [table.table_name for table in diff.changed_tables] != ["main.users"]:
        raise AssertionError(diff.changed_tables)
    if diff.changed_tables[0].added_columns != ["team_id"]:
        raise AssertionError(diff.changed_tables[0])
