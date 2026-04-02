"""LangSmith tracing helpers for LangGraph-backed surfaces."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import AppSettings, load_settings


def is_langsmith_tracing_enabled(settings: AppSettings | None = None) -> bool:
    """Return whether LangSmith tracing is enabled and configured.

    Args:
        settings: Optional application settings.

    Returns:
        bool: `True` when tracing is enabled and an API key is available.
    """

    resolved_settings = settings or load_settings()
    return bool(
        resolved_settings.langsmith.tracing and resolved_settings.langsmith.api_key
    )


def create_langsmith_client(settings: AppSettings | None = None) -> Any | None:
    """Create a LangSmith client when tracing is configured.

    Args:
        settings: Optional application settings.

    Returns:
        Any | None: LangSmith client instance, or `None` when tracing is disabled.
    """

    resolved_settings = settings or load_settings()
    if not is_langsmith_tracing_enabled(resolved_settings):
        return None

    langsmith_module = require_dependency("langsmith", "langsmith")
    return langsmith_module.Client(
        api_key=resolved_settings.langsmith.api_key,
        api_url=resolved_settings.langsmith.endpoint,
        workspace_id=resolved_settings.langsmith.workspace_id,
    )


def build_langsmith_metadata(
    *,
    surface: str,
    datasource_name: str,
    schema_name: str | None = None,
    thread_id: str | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    """Build standard LangSmith trace metadata for sqldbagent surfaces.

    Args:
        surface: Calling surface name such as `dashboard` or `runtime`.
        datasource_name: Datasource identifier for the active run.
        schema_name: Optional schema focus.
        thread_id: Optional thread identifier.
        operation: Optional operation label.

    Returns:
        dict[str, Any]: Trace metadata payload.
    """

    metadata: dict[str, Any] = {
        "surface": surface,
        "datasource_name": datasource_name,
    }
    if schema_name is not None:
        metadata["schema_name"] = schema_name
    if thread_id is not None:
        metadata["thread_id"] = thread_id
    if operation is not None:
        metadata["operation"] = operation
    return metadata


@contextmanager
def langsmith_tracing_context(
    *,
    settings: AppSettings | None = None,
    tags: Sequence[str] = (),
    metadata: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Apply a LangSmith tracing context around a surface operation.

    Args:
        settings: Optional application settings.
        tags: Additional trace tags for the active surface.
        metadata: Optional metadata merged into the trace context.

    Yields:
        None: Control returns to the wrapped operation.
    """

    resolved_settings = settings or load_settings()
    if not is_langsmith_tracing_enabled(resolved_settings):
        yield
        return

    langsmith_module = require_dependency("langsmith", "langsmith")
    merged_tags = [
        *resolved_settings.langsmith.tags,
        *[tag for tag in tags if tag not in resolved_settings.langsmith.tags],
    ]
    with langsmith_module.tracing_context(
        project_name=resolved_settings.langsmith.project,
        tags=merged_tags or None,
        metadata=metadata or None,
        enabled=True,
        client=create_langsmith_client(resolved_settings),
    ):
        yield
