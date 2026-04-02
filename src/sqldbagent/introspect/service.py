"""Generic SQLAlchemy-backed inspection service."""

from __future__ import annotations

from sqlalchemy import Engine, inspect

from sqldbagent.core.models.catalog import (
    CheckConstraintModel,
    ColumnModel,
    DatabaseModel,
    ForeignKeyModel,
    IndexModel,
    SchemaModel,
    ServerModel,
    TableModel,
    UniqueConstraintModel,
    ViewModel,
)


class SQLAlchemyInspectionService:
    """Inspection service backed by SQLAlchemy reflection."""

    def __init__(self, engine: Engine) -> None:
        """Initialize the inspection service.

        Args:
            engine: SQLAlchemy engine used for reflection.
        """

        self._engine = engine

    def inspect_server(self) -> ServerModel:
        """Return normalized server metadata.

        Returns:
            ServerModel: Server-level metadata for the datasource.
        """

        schemas = self.list_schemas()
        return ServerModel(
            dialect=self._engine.url.drivername,
            database=self._engine.url.database,
            schemas=schemas,
            summary=(
                f"Datasource uses {self._engine.url.drivername} and exposes "
                f"{len(schemas)} schemas."
            ),
        )

    def inspect_database(self, database: str | None = None) -> DatabaseModel:
        """Return normalized database metadata.

        Args:
            database: Optional database override. Defaults to the current database.

        Returns:
            DatabaseModel: Database-level metadata with normalized schemas.
        """

        database_name = database or self._engine.url.database or "default"
        schemas = [
            self.inspect_schema(schema_name)
            for schema_name in self.list_schemas(database=database)
        ]
        return DatabaseModel(
            name=database_name,
            schemas=schemas,
            summary=(
                f"Database '{database_name}' contains {len(schemas)} reflected schemas."
            ),
        )

    def inspect_schema(self, schema: str) -> SchemaModel:
        """Return normalized schema metadata.

        Args:
            schema: Schema name to inspect.

        Returns:
            SchemaModel: Schema-level metadata with normalized tables.
        """

        table_names = self.list_tables(schema=schema)
        tables = [
            self.describe_table(table_name=table_name, schema=schema)
            for table_name in table_names
        ]
        view_names = self.list_views(schema=schema)
        views = [
            self.describe_view(view_name=view_name, schema=schema)
            for view_name in view_names
        ]
        return SchemaModel(
            database=self._engine.url.database,
            name=schema,
            tables=tables,
            views=views,
            summary=(
                f"Schema '{schema}' contains {len(tables)} tables and {len(views)} views."
            ),
        )

    def list_databases(self) -> list[str]:
        """Return the configured database name when available.

        Returns:
            list[str]: Database names visible to the datasource.
        """

        database_name = self._engine.url.database
        if database_name:
            return [database_name]
        return []

    def list_schemas(self, database: str | None = None) -> list[str]:
        """Return reflected schema names.

        Args:
            database: Optional database scope. Currently informational only.

        Returns:
            list[str]: Sorted schema names.
        """

        del database
        inspector = inspect(self._engine)
        return sorted(inspector.get_schema_names())

    def list_tables(self, schema: str | None = None) -> list[str]:
        """Return reflected table names.

        Args:
            schema: Optional schema name.

        Returns:
            list[str]: Sorted table names.
        """

        inspector = inspect(self._engine)
        return sorted(inspector.get_table_names(schema=schema))

    def list_views(self, schema: str | None = None) -> list[str]:
        """Return reflected view names.

        Args:
            schema: Optional schema name.

        Returns:
            list[str]: Sorted view names.
        """

        inspector = inspect(self._engine)
        return sorted(inspector.get_view_names(schema=schema))

    def describe_table(self, table_name: str, schema: str | None = None) -> TableModel:
        """Return normalized metadata for a table.

        Args:
            table_name: Table name to inspect.
            schema: Optional schema containing the table.

        Returns:
            TableModel: Normalized table metadata.
        """

        inspector = inspect(self._engine)
        columns = self._reflect_columns(
            inspector, relation_name=table_name, schema=schema
        )
        primary_key = inspector.get_pk_constraint(table_name, schema=schema).get(
            "constrained_columns", []
        )
        indexes = [
            IndexModel(
                name=index.get("name"),
                columns=list(index.get("column_names") or []),
                unique=bool(index.get("unique", False)),
                summary=self._summarize_index(
                    columns=list(index.get("column_names") or []),
                    unique=bool(index.get("unique", False)),
                ),
            )
            for index in inspector.get_indexes(table_name, schema=schema)
        ]
        foreign_keys = [
            ForeignKeyModel(
                name=foreign_key.get("name"),
                columns=list(foreign_key.get("constrained_columns") or []),
                referred_schema=foreign_key.get("referred_schema"),
                referred_table=foreign_key.get("referred_table") or "",
                referred_columns=list(foreign_key.get("referred_columns") or []),
                summary=self._summarize_foreign_key(
                    columns=list(foreign_key.get("constrained_columns") or []),
                    referred_schema=foreign_key.get("referred_schema"),
                    referred_table=foreign_key.get("referred_table") or "",
                    referred_columns=list(foreign_key.get("referred_columns") or []),
                ),
            )
            for foreign_key in inspector.get_foreign_keys(table_name, schema=schema)
            if foreign_key.get("referred_table")
        ]
        unique_constraints = [
            UniqueConstraintModel(
                name=constraint.get("name"),
                columns=list(constraint.get("column_names") or []),
                summary=self._summarize_unique_constraint(
                    list(constraint.get("column_names") or [])
                ),
            )
            for constraint in inspector.get_unique_constraints(
                table_name, schema=schema
            )
        ]
        check_constraints = [
            CheckConstraintModel(
                name=constraint.get("name"),
                expression=constraint.get("sqltext"),
                summary=self._summarize_check_constraint(constraint.get("sqltext")),
            )
            for constraint in inspector.get_check_constraints(table_name, schema=schema)
        ]
        summary = self._summarize_table(
            table_name=table_name,
            schema=schema,
            columns=columns,
            primary_key=list(primary_key or []),
            indexes=indexes,
            foreign_keys=foreign_keys,
            unique_constraints=unique_constraints,
            check_constraints=check_constraints,
        )

        return TableModel(
            database=self._engine.url.database,
            schema_name=schema,
            name=table_name,
            columns=columns,
            primary_key=list(primary_key or []),
            indexes=indexes,
            foreign_keys=foreign_keys,
            unique_constraints=unique_constraints,
            check_constraints=check_constraints,
            description=self._reflect_table_comment(
                inspector, table_name=table_name, schema=schema
            ),
            summary=summary,
        )

    def describe_view(self, view_name: str, schema: str | None = None) -> ViewModel:
        """Return normalized metadata for a view.

        Args:
            view_name: View name to inspect.
            schema: Optional schema containing the view.

        Returns:
            ViewModel: Normalized view metadata.
        """

        inspector = inspect(self._engine)
        columns = self._reflect_columns(
            inspector, relation_name=view_name, schema=schema
        )
        return ViewModel(
            database=self._engine.url.database,
            schema_name=schema,
            name=view_name,
            columns=columns,
            definition=self._reflect_view_definition(
                inspector, view_name=view_name, schema=schema
            ),
            summary=(
                f"View '{self._qualify_name(schema, view_name)}' exposes "
                f"{len(columns)} columns."
            ),
        )

    def _reflect_columns(
        self, inspector: any, relation_name: str, schema: str | None
    ) -> list[ColumnModel]:
        """Reflect normalized column metadata.

        Args:
            inspector: SQLAlchemy inspector.
            relation_name: Table or view name.
            schema: Optional schema name.

        Returns:
            list[ColumnModel]: Reflected columns.
        """

        return [
            ColumnModel(
                name=column["name"],
                data_type=str(column["type"]),
                nullable=bool(column.get("nullable", True)),
                default=(
                    None
                    if column.get("default") is None
                    else str(column.get("default"))
                ),
                description=(
                    None
                    if column.get("comment") is None
                    else str(column.get("comment"))
                ),
                summary=self._summarize_column(
                    column_name=column["name"],
                    data_type=str(column["type"]),
                    nullable=bool(column.get("nullable", True)),
                    default=column.get("default"),
                ),
            )
            for column in inspector.get_columns(relation_name, schema=schema)
        ]

    def _reflect_table_comment(
        self, inspector: any, table_name: str, schema: str | None
    ) -> str | None:
        """Reflect a table comment when supported by the dialect.

        Args:
            inspector: SQLAlchemy inspector.
            table_name: Table name.
            schema: Optional schema name.

        Returns:
            str | None: Table comment text when available.
        """

        try:
            payload = inspector.get_table_comment(table_name, schema=schema)
        except NotImplementedError:
            return None

        return payload.get("text")

    def _reflect_view_definition(
        self, inspector: any, view_name: str, schema: str | None
    ) -> str | None:
        """Reflect a view definition when supported by the dialect.

        Args:
            inspector: SQLAlchemy inspector.
            view_name: View name.
            schema: Optional schema name.

        Returns:
            str | None: View definition SQL when available.
        """

        try:
            return inspector.get_view_definition(view_name, schema=schema)
        except NotImplementedError:
            return None

    def _summarize_column(
        self,
        *,
        column_name: str,
        data_type: str,
        nullable: bool,
        default: object | None,
    ) -> str:
        """Build a short human-readable summary for one column."""

        parts = [f"{column_name} ({data_type})", "nullable" if nullable else "required"]
        if default is not None:
            parts.append(f"default={default}")
        return ", ".join(parts)

    def _summarize_index(self, *, columns: list[str], unique: bool) -> str:
        """Build a short human-readable summary for one index."""

        kind = "unique index" if unique else "index"
        joined = ", ".join(columns) if columns else "no columns"
        return f"{kind} on {joined}"

    def _summarize_foreign_key(
        self,
        *,
        columns: list[str],
        referred_schema: str | None,
        referred_table: str,
        referred_columns: list[str],
    ) -> str:
        """Build a short human-readable summary for one foreign key."""

        target = self._qualify_name(referred_schema, referred_table)
        source_columns = ", ".join(columns) if columns else "unknown columns"
        target_columns = ", ".join(referred_columns) if referred_columns else "unknown"
        return f"{source_columns} references {target} ({target_columns})"

    def _summarize_unique_constraint(self, columns: list[str]) -> str:
        """Build a short human-readable summary for one unique constraint."""

        joined = ", ".join(columns) if columns else "no columns"
        return f"unique constraint on {joined}"

    def _summarize_check_constraint(self, expression: str | None) -> str | None:
        """Build a short human-readable summary for one check constraint."""

        if expression is None:
            return None
        return f"check constraint: {expression}"

    def _summarize_table(
        self,
        *,
        table_name: str,
        schema: str | None,
        columns: list[ColumnModel],
        primary_key: list[str],
        indexes: list[IndexModel],
        foreign_keys: list[ForeignKeyModel],
        unique_constraints: list[UniqueConstraintModel],
        check_constraints: list[CheckConstraintModel],
    ) -> str:
        """Build a short human-readable summary for one table."""

        qualified_name = self._qualify_name(schema, table_name)
        pk_text = (
            f"primary key on {', '.join(primary_key)}"
            if primary_key
            else "no reflected primary key"
        )
        return (
            f"Table '{qualified_name}' has {len(columns)} columns, {pk_text}, "
            f"{len(indexes)} indexes, {len(unique_constraints)} unique constraints, "
            f"{len(check_constraints)} checks, and {len(foreign_keys)} foreign keys."
        )

    def _qualify_name(self, schema: str | None, name: str) -> str:
        """Return a schema-qualified name when a schema is present."""

        if schema:
            return f"{schema}.{name}"
        return name
