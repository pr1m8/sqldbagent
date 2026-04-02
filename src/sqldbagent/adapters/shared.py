"""Shared adapter helpers."""

from __future__ import annotations

from typing import Any

from sqldbagent.core.errors import AdapterDependencyError


def require_dependency(module_name: str, extra_name: str) -> Any:
    """Import an optional dependency with a clear install hint.

    Args:
        module_name: Import path for the optional dependency.
        extra_name: Package or extra to suggest in the error message.

    Returns:
        Any: Imported module object.

    Raises:
        AdapterDependencyError: If the dependency is unavailable.
    """

    try:
        return __import__(module_name, fromlist=["*"])
    except ImportError as exc:
        raise AdapterDependencyError(
            f"Optional dependency '{module_name}' is required. Install with `pdm add '{extra_name}'` "
            f"or install the matching project extra."
        ) from exc
