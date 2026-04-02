"""Model-building helpers for LangChain/LangGraph runtime surfaces."""

from __future__ import annotations

from typing import Any

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import AppSettings
from sqldbagent.core.errors import ConfigurationError


def create_runtime_chat_model(settings: AppSettings) -> Any:
    """Build the default runtime chat model from configured provider settings.

    Args:
        settings: Application settings carrying provider configuration.

    Returns:
        Any: LangChain-compatible chat model instance or provider-qualified name.
    """

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
