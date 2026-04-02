"""SQLite-backed CLI smoke tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from sqldbagent.cli.app import app
from sqldbagent.core.config import load_settings


def test_cli_inspect_table_with_sqlite_env(
    isolated_sqlite_env: dict[str, str], tmp_path: Path
) -> None:
    """Describe SQLite metadata through the CLI.

    Args:
        isolated_sqlite_env: Environment values pointing at a temp SQLite file.
        tmp_path: Temporary directory for the test.
    """

    del tmp_path
    database_path = isolated_sqlite_env["SQLITE_PATH"]
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
                    CONSTRAINT fk_users_team FOREIGN KEY(team_id) REFERENCES teams(id),
                    CONSTRAINT uq_users_email UNIQUE(email)
                )
                """))
        connection.execute(text("CREATE INDEX ix_users_team_id ON users(team_id)"))
        connection.execute(
            text("CREATE VIEW active_users AS SELECT id, email FROM users")
        )
        connection.execute(text("INSERT INTO teams (id, name) VALUES (1, 'data')"))
        connection.execute(text("""
                INSERT INTO users (id, team_id, email) VALUES
                (1, 1, 'a@example.com'),
                (2, 1, 'b@example.com'),
                (3, 1, NULL)
                """))
    engine.dispose()

    load_settings.cache_clear()
    runner = CliRunner()

    result = runner.invoke(app, ["inspect", "table", "sqlite", "users"])
    if result.exit_code != 0:
        raise AssertionError(result.output)
    normalized_output = result.output.replace(" ", "").replace("\n", "")
    if '"name":"users"' not in normalized_output:
        raise AssertionError(result.output)
    if '"name":"fk_users_team"' not in normalized_output:
        raise AssertionError(result.output)

    server_result = runner.invoke(app, ["inspect", "server", "sqlite"])
    if server_result.exit_code != 0:
        raise AssertionError(server_result.output)
    if '"dialect":"sqlite+pysqlite"' not in server_result.output.replace(
        " ", ""
    ).replace("\n", ""):
        raise AssertionError(server_result.output)

    tables_result = runner.invoke(app, ["inspect", "tables", "sqlite"])
    if tables_result.exit_code != 0:
        raise AssertionError(tables_result.output)
    if "users" not in tables_result.output:
        raise AssertionError(tables_result.output)

    views_result = runner.invoke(app, ["inspect", "views", "sqlite"])
    if views_result.exit_code != 0:
        raise AssertionError(views_result.output)
    if "active_users" not in views_result.output:
        raise AssertionError(views_result.output)

    schema_result = runner.invoke(app, ["inspect", "schema", "sqlite", "main"])
    if schema_result.exit_code != 0:
        raise AssertionError(schema_result.output)
    schema_output = schema_result.output.replace(" ", "").replace("\n", "")
    if '"name":"main"' not in schema_output:
        raise AssertionError(schema_result.output)
    if '"views":[{"database":"' not in schema_output:
        raise AssertionError(schema_result.output)

    database_result = runner.invoke(app, ["inspect", "database", "sqlite"])
    if database_result.exit_code != 0:
        raise AssertionError(database_result.output)
    if '"schemas":[{"database":"' not in database_result.output.replace(
        " ", ""
    ).replace("\n", ""):
        raise AssertionError(database_result.output)

    view_result = runner.invoke(app, ["inspect", "view", "sqlite", "active_users"])
    if view_result.exit_code != 0:
        raise AssertionError(view_result.output)
    if (
        '"definition":"CREATEVIEWactive_usersASSELECTid,emailFROMusers"'
        not in view_result.output.replace(" ", "").replace("\n", "")
    ):
        raise AssertionError(view_result.output)

    profile_result = runner.invoke(app, ["profile", "table", "sqlite", "users"])
    if profile_result.exit_code != 0:
        raise AssertionError(profile_result.output)
    profile_output = profile_result.output.replace(" ", "").replace("\n", "")
    if '"row_count":3' not in profile_output:
        raise AssertionError(profile_result.output)
    if '"unique_value_count":2' not in profile_output:
        raise AssertionError(profile_result.output)
    if '"entity_kind":"child_entity"' not in profile_output:
        raise AssertionError(profile_result.output)

    sample_result = runner.invoke(
        app,
        ["profile", "sample", "sqlite", "users", "--limit", "2"],
    )
    if sample_result.exit_code != 0:
        raise AssertionError(sample_result.output)
    if "a@example.com" not in sample_result.output:
        raise AssertionError(sample_result.output)

    snapshot_create_result = runner.invoke(
        app, ["snapshot", "create", "sqlite", "main"]
    )
    if snapshot_create_result.exit_code != 0:
        raise AssertionError(snapshot_create_result.output)
    snapshot_path = Path(snapshot_create_result.output.strip())
    if not snapshot_path.exists():
        raise AssertionError(snapshot_path)

    snapshot_show_result = runner.invoke(app, ["snapshot", "show", str(snapshot_path)])
    if snapshot_show_result.exit_code != 0:
        raise AssertionError(snapshot_show_result.output)
    snapshot_output = snapshot_show_result.output.replace(" ", "").replace("\n", "")
    if '"table_name":"users"' not in snapshot_output:
        raise AssertionError(snapshot_show_result.output)
    if '"content_hash":"' not in snapshot_output:
        raise AssertionError(snapshot_show_result.output)

    snapshot_list_result = runner.invoke(app, ["snapshot", "list", "sqlite", "main"])
    if snapshot_list_result.exit_code != 0:
        raise AssertionError(snapshot_list_result.output)
    if '"schema_name":"main"' not in snapshot_list_result.output.replace(
        " ", ""
    ).replace("\n", ""):
        raise AssertionError(snapshot_list_result.output)

    snapshot_latest_result = runner.invoke(
        app, ["snapshot", "latest", "sqlite", "main"]
    )
    if snapshot_latest_result.exit_code != 0:
        raise AssertionError(snapshot_latest_result.output)
    if '"snapshot_id":"' not in snapshot_latest_result.output.replace(" ", "").replace(
        "\n", ""
    ):
        raise AssertionError(snapshot_latest_result.output)

    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN team_name TEXT"))
        connection.execute(
            text("CREATE VIEW user_emails AS SELECT id, email FROM users")
        )
    engine.dispose()

    second_snapshot_create_result = runner.invoke(
        app, ["snapshot", "create", "sqlite", "main"]
    )
    if second_snapshot_create_result.exit_code != 0:
        raise AssertionError(second_snapshot_create_result.output)
    second_snapshot_path = Path(second_snapshot_create_result.output.strip())
    if not second_snapshot_path.exists():
        raise AssertionError(second_snapshot_path)

    snapshot_diff_result = runner.invoke(
        app, ["snapshot", "diff", str(snapshot_path), str(second_snapshot_path)]
    )
    if snapshot_diff_result.exit_code != 0:
        raise AssertionError(snapshot_diff_result.output)
    snapshot_diff_output = snapshot_diff_result.output.replace(" ", "").replace(
        "\n", ""
    )
    if '"table_name":"main.users"' not in snapshot_diff_output:
        raise AssertionError(snapshot_diff_result.output)
    if '"added_views":["main.user_emails"]' not in snapshot_diff_output:
        raise AssertionError(snapshot_diff_result.output)

    query_result = runner.invoke(
        app, ["query", "guard", "sqlite", "SELECT id FROM users"]
    )
    if query_result.exit_code != 0:
        raise AssertionError(query_result.output)
    query_output = query_result.output.replace(" ", "").replace("\n", "").lower()
    if '"row_limit_applied":true' not in query_output:
        raise AssertionError(query_result.output)
    if '"referenced_tables":["users"]' not in query_output:
        raise AssertionError(query_result.output)

    query_run_result = runner.invoke(
        app,
        ["query", "run", "sqlite", "SELECT id, email FROM users ORDER BY id"],
    )
    if query_run_result.exit_code != 0:
        raise AssertionError(query_run_result.output)
    if '"row_count":3' not in query_run_result.output.replace(" ", "").replace(
        "\n", ""
    ):
        raise AssertionError(query_run_result.output)

    query_run_async_result = runner.invoke(
        app,
        ["query", "run-async", "sqlite", "SELECT id, email FROM users ORDER BY id"],
    )
    if query_run_async_result.exit_code != 0:
        raise AssertionError(query_run_async_result.output)
    if '"mode":"async"' not in query_run_async_result.output.replace(" ", "").replace(
        "\n", ""
    ):
        raise AssertionError(query_run_async_result.output)

    denied_result = runner.invoke(app, ["query", "guard", "sqlite", "DROP TABLE users"])
    if denied_result.exit_code == 0:
        raise AssertionError(denied_result.output)
    if "only read-only query statements are allowed" not in denied_result.output:
        raise AssertionError(denied_result.output)
