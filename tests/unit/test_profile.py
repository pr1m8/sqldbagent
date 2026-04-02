"""Profiling service tests."""

from sqlalchemy import create_engine, text

from sqldbagent.introspect.service import SQLAlchemyInspectionService
from sqldbagent.profile.service import SQLAlchemyProfilingService


def test_sqlalchemy_profiling_service_profiles_sqlite_table(tmp_path) -> None:
    """Profile a SQLite table with exact counts and samples."""

    database_path = tmp_path / "profile.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("""
                CREATE TABLE teams (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                )
                """))
        connection.execute(text("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    team_id INTEGER,
                    email TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    CONSTRAINT fk_users_team FOREIGN KEY(team_id) REFERENCES teams(id)
                )
                """))
        connection.execute(text("INSERT INTO teams (id, name) VALUES (1, 'data')"))
        connection.execute(text("""
                INSERT INTO users (id, team_id, email, is_active) VALUES
                (1, 1, 'a@example.com', 1),
                (2, 1, 'b@example.com', 1),
                (3, 1, NULL, 0)
                """))

    inspector = SQLAlchemyInspectionService(engine)
    profiler = SQLAlchemyProfilingService(engine=engine, inspector=inspector)
    profile = profiler.profile_table("users", sample_size=2)
    samples = profiler.sample_table("users", limit=2)
    engine.dispose()

    if profile.row_count != 3:
        raise AssertionError(profile)
    if not profile.row_count_exact:
        raise AssertionError(profile)
    if profile.storage_bytes is None or profile.storage_bytes <= 0:
        raise AssertionError(profile.storage_bytes)
    if len(profile.relationships) != 1:
        raise AssertionError(profile.relationships)
    if profile.entity_kind != "child_entity":
        raise AssertionError(profile.entity_kind)
    column_profiles = {column.name: column for column in profile.columns}
    if column_profiles["email"].unique_value_count != 2:
        raise AssertionError(column_profiles["email"])
    if column_profiles["email"].null_count != 1:
        raise AssertionError(column_profiles["email"])
    if column_profiles["email"].top_values[0]["count"] != 1:
        raise AssertionError(column_profiles["email"].top_values)
    if column_profiles["is_active"].unique_value_count != 2:
        raise AssertionError(column_profiles["is_active"])
    if column_profiles["is_active"].min_value is not None:
        raise AssertionError(column_profiles["is_active"])
    if column_profiles["is_active"].max_value is not None:
        raise AssertionError(column_profiles["is_active"])
    if len(samples) != 2:
        raise AssertionError(samples)
