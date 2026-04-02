"""Shared enums."""

from enum import StrEnum


class Dialect(StrEnum):
    """Supported database dialects."""

    POSTGRES = "postgres"
    MSSQL = "mssql"
    SQLITE = "sqlite"
