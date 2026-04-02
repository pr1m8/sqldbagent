"""LangGraph CLI and SDK runtime entrypoints."""

from __future__ import annotations

import atexit
from contextlib import ExitStack
from typing import Any

from sqldbagent.adapters.langgraph.agent import create_sqldbagent_agent
from sqldbagent.adapters.langgraph.checkpoint import create_sync_postgres_checkpointer
from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.bootstrap import ServiceContainer, build_service_container
from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.core.errors import ConfigurationError

_RESOURCE_STACK = ExitStack()
_RUNTIME_CONTAINER: ServiceContainer | None = None


def create_runtime_agent(settings: AppSettings | None = None) -> Any:
    """Build the default LangGraph runtime agent.

    Args:
        settings: Optional application settings override.

    Returns:
        Any: Compiled LangGraph agent for LangGraph CLI or SDK usage.
    """

    global _RUNTIME_CONTAINER

    resolved_settings = settings or load_settings()
    datasource_name = resolved_settings.resolve_default_datasource_name()
    schema_name = resolved_settings.default_schema_name
    _RUNTIME_CONTAINER = build_service_container(
        datasource_name,
        settings=resolved_settings,
        include_async_engine=False,
    )
    checkpointer = None
    if (
        resolved_settings.agent.checkpoint.backend == "postgres"
        and resolved_settings.agent.checkpoint.postgres_url is not None
    ):
        checkpointer = _RESOURCE_STACK.enter_context(
            create_sync_postgres_checkpointer(settings=resolved_settings)
        )
    return create_sqldbagent_agent(
        services=_RUNTIME_CONTAINER,
        model=_build_runtime_model(resolved_settings),
        datasource_name=datasource_name,
        settings=resolved_settings,
        schema_name=schema_name,
        checkpointer=checkpointer,
    )


def get_langgraph_sdk_client(url: str | None = None) -> Any:
    """Build a LangGraph SDK client.

    Args:
        url: Optional LangGraph server URL.

    Returns:
        Any: LangGraph SDK client instance.
    """

    sdk_module = require_dependency("langgraph_sdk", "langgraph-sdk")
    return sdk_module.get_client(url=url)


def _build_runtime_model(settings: AppSettings) -> Any:
    """Build the default runtime chat model."""

    provider = settings.llm.default_provider
    model_name = settings.llm.default_model
    if provider is None or model_name is None:
        raise ConfigurationError("LLM provider and model must be configured")

    if provider == "openai":
        openai_module = require_dependency("langchain_openai", "langchain-openai")
        return openai_module.ChatOpenAI(
            model=model_name,
            api_key=settings.llm.openai_api_key,
            base_url=settings.llm.openai_base_url,
            reasoning_effort=settings.llm.reasoning_effort,
        )

    if provider == "anthropic":
        anthropic_module = require_dependency(
            "langchain_anthropic",
            "langchain-anthropic",
        )
        effort = _normalize_anthropic_effort(settings.llm.reasoning_effort)
        kwargs = {
            "model_name": model_name,
            "api_key": settings.llm.anthropic_api_key,
            "base_url": settings.llm.anthropic_base_url,
        }
        if effort is not None:
            kwargs["effort"] = effort
        return anthropic_module.ChatAnthropic(**kwargs)

    return f"{provider}:{model_name}"


def _normalize_anthropic_effort(reasoning_effort: str | None) -> str | None:
    """Translate OpenAI-style effort labels to Anthropic-compatible values."""

    if reasoning_effort is None:
        return None
    mapping = {
        "xhigh": "max",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }
    return mapping.get(reasoning_effort)


def _cleanup_runtime_resources() -> None:
    """Dispose runtime resources on process exit."""

    global _RUNTIME_CONTAINER

    try:
        _RESOURCE_STACK.close()
    finally:
        if _RUNTIME_CONTAINER is not None:
            _RUNTIME_CONTAINER.close()
            _RUNTIME_CONTAINER = None


agent = create_runtime_agent()

atexit.register(_cleanup_runtime_resources)
