"""SQL safety services."""

from __future__ import annotations

from typing import Any

__all__ = ["QueryGuardResult", "QueryGuardService", "SafeQueryService"]


def __getattr__(name: str) -> Any:
    """Load safety exports lazily to avoid import cycles."""

    if name == "QueryGuardResult":
        from sqldbagent.safety.models import QueryGuardResult

        return QueryGuardResult
    if name == "QueryGuardService":
        from sqldbagent.safety.guard import QueryGuardService

        return QueryGuardService
    if name == "SafeQueryService":
        from sqldbagent.safety.execution import SafeQueryService

        return SafeQueryService
    raise AttributeError(name)
