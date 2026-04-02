"""Canonical normalized catalog models."""

from pydantic import BaseModel, Field


class ColumnModel(BaseModel):
    """Normalized column metadata.

    Attributes:
        name: Column name.
        data_type: Normalized logical or physical data type.
        nullable: Whether the column accepts null values.
        default: Optional default expression.
        description: Optional normalized description.
        summary: Generated short summary for humans and downstream prompts.
    """

    name: str
    data_type: str
    nullable: bool = True
    default: str | None = None
    description: str | None = None
    summary: str | None = None


class CheckConstraintModel(BaseModel):
    """Normalized check constraint metadata.

    Attributes:
        name: Constraint name when available.
        expression: Check expression SQL when available.
        summary: Generated short summary.
    """

    name: str | None = None
    expression: str | None = None
    summary: str | None = None


class IndexModel(BaseModel):
    """Normalized index metadata.

    Attributes:
        name: Index name.
        columns: Indexed column names.
        unique: Whether the index is unique.
        summary: Generated short summary.
    """

    name: str | None = None
    columns: list[str] = Field(default_factory=list)
    unique: bool = False
    summary: str | None = None


class ForeignKeyModel(BaseModel):
    """Normalized foreign key metadata.

    Attributes:
        name: Constraint name when available.
        columns: Local constrained columns.
        referred_schema: Referenced schema name when available.
        referred_table: Referenced table name.
        referred_columns: Referenced column names.
        summary: Generated short summary.
    """

    name: str | None = None
    columns: list[str] = Field(default_factory=list)
    referred_schema: str | None = None
    referred_table: str
    referred_columns: list[str] = Field(default_factory=list)
    summary: str | None = None


class UniqueConstraintModel(BaseModel):
    """Normalized unique constraint metadata.

    Attributes:
        name: Constraint name when available.
        columns: Columns covered by the unique constraint.
        summary: Generated short summary.
    """

    name: str | None = None
    columns: list[str] = Field(default_factory=list)
    summary: str | None = None


class RelationshipEdgeModel(BaseModel):
    """Normalized relationship edge derived from a foreign key.

    Attributes:
        source_schema: Schema of the referencing table when available.
        source_table: Referencing table.
        source_columns: Referencing columns.
        target_schema: Schema of the referenced table when available.
        target_table: Referenced table.
        target_columns: Referenced columns.
        constraint_name: Foreign key constraint name.
        summary: Generated short summary.
    """

    source_schema: str | None = None
    source_table: str
    source_columns: list[str] = Field(default_factory=list)
    target_schema: str | None = None
    target_table: str
    target_columns: list[str] = Field(default_factory=list)
    constraint_name: str | None = None
    summary: str | None = None


class TableModel(BaseModel):
    """Normalized table metadata.

    Attributes:
        database: Optional database name containing the table.
        schema_name: Optional schema name containing the table.
        name: Table name.
        columns: Normalized column metadata.
        primary_key: Ordered primary key column names.
        indexes: Normalized index metadata.
        foreign_keys: Normalized foreign key metadata.
        unique_constraints: Normalized unique constraint metadata.
        check_constraints: Normalized check constraint metadata.
        description: Optional normalized description.
        summary: Generated short summary.
    """

    database: str | None = None
    schema_name: str | None = None
    name: str
    columns: list[ColumnModel] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)
    indexes: list[IndexModel] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyModel] = Field(default_factory=list)
    unique_constraints: list[UniqueConstraintModel] = Field(default_factory=list)
    check_constraints: list[CheckConstraintModel] = Field(default_factory=list)
    description: str | None = None
    summary: str | None = None


class ViewModel(BaseModel):
    """Normalized view metadata.

    Attributes:
        database: Optional database containing the view.
        schema_name: Optional schema containing the view.
        name: View name.
        columns: Reflected view columns.
        definition: View definition SQL when available.
        summary: Generated short summary.
    """

    database: str | None = None
    schema_name: str | None = None
    name: str
    columns: list[ColumnModel] = Field(default_factory=list)
    definition: str | None = None
    summary: str | None = None


class ServerModel(BaseModel):
    """Normalized server metadata.

    Attributes:
        dialect: Dialect or driver name used by the datasource.
        database: Current database name when available.
        schemas: Visible schema names.
        summary: Generated short summary.
    """

    dialect: str
    database: str | None = None
    schemas: list[str] = Field(default_factory=list)
    summary: str | None = None


class SchemaModel(BaseModel):
    """Normalized schema metadata.

    Attributes:
        database: Optional database name containing the schema.
        name: Schema name.
        tables: Normalized tables within the schema.
        views: Normalized views within the schema.
        summary: Generated short summary.
    """

    database: str | None = None
    name: str
    tables: list[TableModel] = Field(default_factory=list)
    views: list[ViewModel] = Field(default_factory=list)
    summary: str | None = None


class DatabaseModel(BaseModel):
    """Normalized database metadata.

    Attributes:
        name: Database name.
        schemas: Normalized schema metadata in the database.
        summary: Generated short summary.
    """

    name: str
    schemas: list[SchemaModel] = Field(default_factory=list)
    summary: str | None = None
