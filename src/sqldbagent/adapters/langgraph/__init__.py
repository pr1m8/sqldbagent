"""LangGraph adapter surface."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "build_snapshot_prompt_context",
    "build_sqldbagent_dashboard_payload",
    "build_sqldbagent_state_seed",
    "create_async_postgres_checkpointer",
    "create_async_postgres_checkpointed_agent",
    "create_memory_checkpointer",
    "create_sqldbagent_agent",
    "create_sqldbagent_middleware",
    "create_sqldbagent_system_prompt",
    "create_sync_postgres_checkpointer",
    "create_sync_postgres_checkpointed_agent",
    "SQLDBAgentContext",
    "SQLDBAgentState",
]

_EXPORTS = {
    "build_snapshot_prompt_context": (
        "sqldbagent.core.agent_context",
        "build_snapshot_prompt_context",
    ),
    "build_sqldbagent_dashboard_payload": (
        "sqldbagent.core.agent_context",
        "build_sqldbagent_dashboard_payload",
    ),
    "build_sqldbagent_state_seed": (
        "sqldbagent.core.agent_context",
        "build_sqldbagent_state_seed",
    ),
    "create_async_postgres_checkpointer": (
        "sqldbagent.adapters.langgraph.checkpoint",
        "create_async_postgres_checkpointer",
    ),
    "create_async_postgres_checkpointed_agent": (
        "sqldbagent.adapters.langgraph.agent",
        "create_async_postgres_checkpointed_agent",
    ),
    "create_memory_checkpointer": (
        "sqldbagent.adapters.langgraph.checkpoint",
        "create_memory_checkpointer",
    ),
    "create_sqldbagent_agent": (
        "sqldbagent.adapters.langgraph.agent",
        "create_sqldbagent_agent",
    ),
    "create_sqldbagent_middleware": (
        "sqldbagent.adapters.langgraph.middleware",
        "create_sqldbagent_middleware",
    ),
    "create_sqldbagent_system_prompt": (
        "sqldbagent.adapters.langgraph.prompts",
        "create_sqldbagent_system_prompt",
    ),
    "create_sync_postgres_checkpointer": (
        "sqldbagent.adapters.langgraph.checkpoint",
        "create_sync_postgres_checkpointer",
    ),
    "create_sync_postgres_checkpointed_agent": (
        "sqldbagent.adapters.langgraph.agent",
        "create_sync_postgres_checkpointed_agent",
    ),
    "SQLDBAgentContext": (
        "sqldbagent.adapters.langgraph.state",
        "SQLDBAgentContext",
    ),
    "SQLDBAgentState": (
        "sqldbagent.adapters.langgraph.state",
        "SQLDBAgentState",
    ),
}


def __getattr__(name: str) -> Any:
    """Lazily resolve adapter exports to avoid bootstrap-time cycles."""

    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORTS[name]
    module = import_module(module_name)
    return getattr(module, attribute_name)
