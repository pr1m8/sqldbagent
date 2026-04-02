"""Inspection service tests."""

from sqlalchemy import create_engine, text

from sqldbagent.introspect.service import SQLAlchemyInspectionService


def test_sqlalchemy_inspection_service_describes_sqlite_table() -> None:
    """Reflect richer SQLite table metadata into normalized models."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
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
                    email TEXT NOT NULL,
                    CONSTRAINT fk_users_team FOREIGN KEY(team_id) REFERENCES teams(id),
                    CONSTRAINT uq_users_email UNIQUE(email)
                )
                """))
        connection.execute(text("CREATE INDEX ix_users_team_id ON users(team_id)"))
        connection.execute(
            text("CREATE VIEW active_users AS SELECT id, email FROM users")
        )

    service = SQLAlchemyInspectionService(engine)
    summary = service.inspect_server()
    description = service.describe_table("users")
    view = service.describe_view("active_users")
    engine.dispose()

    if summary.dialect != "sqlite+pysqlite":
        raise AssertionError(summary)
    if description.name != "users":
        raise AssertionError(description.name)
    if description.primary_key != ["id"]:
        raise AssertionError(description.primary_key)
    if [column.name for column in description.columns] != ["id", "team_id", "email"]:
        raise AssertionError(description.columns)
    if [index.name for index in description.indexes] != ["ix_users_team_id"]:
        raise AssertionError(description.indexes)
    if [fk.name for fk in description.foreign_keys] != ["fk_users_team"]:
        raise AssertionError(description.foreign_keys)
    if [constraint.name for constraint in description.unique_constraints] != [
        "uq_users_email"
    ]:
        raise AssertionError(description.unique_constraints)
    if view.name != "active_users":
        raise AssertionError(view)
    if "CREATE VIEW active_users" not in (view.definition or ""):
        raise AssertionError(view.definition)


def test_sqlalchemy_inspection_service_inspects_schema() -> None:
    """Reflect a schema-level view of SQLite tables and views."""

    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
        )
        connection.execute(
            text("CREATE VIEW active_users AS SELECT id, email FROM users")
        )

    service = SQLAlchemyInspectionService(engine)
    database = service.inspect_database()
    schema = service.inspect_schema("main")
    engine.dispose()

    if database.name != ":memory:":
        raise AssertionError(database)
    if schema.name != "main":
        raise AssertionError(schema)
    if [table.name for table in schema.tables] != ["users"]:
        raise AssertionError(schema.tables)
    if [view.name for view in schema.views] != ["active_users"]:
        raise AssertionError(schema.views)
