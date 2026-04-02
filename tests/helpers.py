"""Shared test helpers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.tools import BaseTool


class ToolReadyFakeMessagesListChatModel(FakeMessagesListChatModel):
    """Fake chat model that satisfies LangChain agent tool binding in tests."""

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ToolReadyFakeMessagesListChatModel:
        """Return the same model after accepting tool metadata.

        Args:
            tools: Tool definitions bound by the agent runtime.
            tool_choice: Optional tool choice hint.
            **kwargs: Provider-specific binding arguments.

        Returns:
            ToolReadyFakeMessagesListChatModel: The current fake model instance.
        """

        del tools, tool_choice, kwargs
        return self
