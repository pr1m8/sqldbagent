"""Dashboard app helper tests."""

from __future__ import annotations

from sqldbagent.core.config import AgentCheckpointSettings, AgentSettings, AppSettings
from sqldbagent.dashboard.app import (
    _build_checkpoint_status,
    _resolve_dashboard_checkpointer,
)


def test_resolve_dashboard_checkpointer_reuses_session_memory_saver() -> None:
    """Reuse one in-memory saver for the whole Streamlit session."""

    session_state: dict[str, object] = {}
    settings = AppSettings(
        datasources=[],
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(backend="memory"),
        ),
    )

    first = _resolve_dashboard_checkpointer(session_state, settings)
    second = _resolve_dashboard_checkpointer(session_state, settings)

    if first is None or second is None:
        raise AssertionError(session_state)
    if first is not second:
        raise AssertionError("Expected the same memory checkpointer instance")


def test_resolve_dashboard_checkpointer_defers_to_postgres_backend() -> None:
    """Avoid injecting a memory saver when Postgres checkpointing is enabled."""

    session_state: dict[str, object] = {}
    settings = AppSettings(
        datasources=[],
        agent=AgentSettings(
            checkpoint=AgentCheckpointSettings(
                backend="postgres",
                postgres_url="postgresql+psycopg://demo:demo@127.0.0.1:5432/demo",
            ),
        ),
    )

    resolved = _resolve_dashboard_checkpointer(session_state, settings)

    if resolved is not None:
        raise AssertionError(resolved)
    if "dashboard_checkpointer" in session_state:
        raise AssertionError(session_state)


def test_build_checkpoint_status_reflects_backend() -> None:
    """Describe the dashboard persistence mode in plain language."""

    memory_status = _build_checkpoint_status(
        AppSettings(
            datasources=[],
            agent=AgentSettings(
                checkpoint=AgentCheckpointSettings(backend="memory"),
            ),
        )
    )
    postgres_status = _build_checkpoint_status(
        AppSettings(
            datasources=[],
            agent=AgentSettings(
                checkpoint=AgentCheckpointSettings(
                    backend="postgres",
                    postgres_url="postgresql+psycopg://demo:demo@127.0.0.1:5432/demo",
                ),
            ),
        )
    )

    if "Streamlit session" not in memory_status:
        raise AssertionError(memory_status)
    if "Postgres" not in postgres_status:
        raise AssertionError(postgres_status)
