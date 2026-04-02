"""Introspection service contracts."""

from sqldbagent.introspect.base import InspectionService
from sqldbagent.introspect.service import SQLAlchemyInspectionService

__all__ = ["InspectionService", "SQLAlchemyInspectionService"]
