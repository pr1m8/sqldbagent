"""Shared Typer dependency loading."""

from __future__ import annotations

from typing import Any

from sqldbagent.adapters.shared import require_dependency


def load_typer() -> Any:
    """Import Typer lazily.

    Returns:
        Any: Typer module.
    """

    return require_dependency("typer", "typer")
