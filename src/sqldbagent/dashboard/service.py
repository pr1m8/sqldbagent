"""Dashboard chat service built on top of the persisted LangGraph agent."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any
from uuid import uuid4

import orjson

from sqldbagent.adapters.langgraph.agent import create_sqldbagent_agent
from sqldbagent.adapters.langgraph.checkpoint import (
    create_memory_checkpointer,
    create_sync_postgres_checkpointer,
)
from sqldbagent.adapters.langgraph.model import create_runtime_chat_model
from sqldbagent.adapters.langgraph.observability import (
    build_langsmith_metadata,
    is_langsmith_tracing_enabled,
    langsmith_tracing_context,
)
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.core.config import AppSettings, load_settings
from sqldbagent.dashboard.models import ChatMessageModel, ChatSessionModel


class DashboardChatService:
    """Run persisted chat turns over the shared sqldbagent agent stack."""

    def __init__(
        self,
        *,
        settings: AppSettings | None = None,
        model: Any | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        """Initialize the dashboard chat service.

        Args:
            settings: Optional application settings.
            model: Optional prebuilt LangChain-compatible model for tests.
            checkpointer: Optional externally managed checkpointer for tests.
        """

        self._settings = settings or load_settings()
        self._model = model
        self._checkpointer = checkpointer

    @staticmethod
    def new_thread_id() -> str:
        """Return a new stable thread identifier."""

        return uuid4().hex

    def run_turn(
        self,
        *,
        thread_id: str,
        user_message: str,
        datasource_name: str,
        schema_name: str | None = None,
    ) -> ChatSessionModel:
        """Run one user turn through the persisted agent session.

        Args:
            thread_id: LangGraph thread identifier.
            user_message: User message content.
            datasource_name: Datasource identifier.
            schema_name: Optional schema focus.

        Returns:
            ChatSessionModel: Dashboard-ready state after the turn.
        """

        resolved_datasource = self._settings.resolve_datasource_name(datasource_name)
        config = {"configurable": {"thread_id": thread_id}}
        with self._agent_session(
            datasource_name=resolved_datasource,
            schema_name=schema_name,
        ) as agent:
            with langsmith_tracing_context(
                settings=self._settings,
                tags=["dashboard", resolved_datasource],
                metadata=build_langsmith_metadata(
                    surface="dashboard",
                    datasource_name=resolved_datasource,
                    schema_name=schema_name,
                    thread_id=thread_id,
                    operation="run_turn",
                ),
            ):
                result = agent.invoke(
                    {"messages": [{"role": "user", "content": user_message}]},
                    config=config,
                )
            return self._session_from_values(
                thread_id=thread_id,
                datasource_name=resolved_datasource,
                schema_name=schema_name,
                values=result,
            )

    def load_thread(
        self,
        *,
        thread_id: str,
        datasource_name: str,
        schema_name: str | None = None,
    ) -> ChatSessionModel:
        """Load the current persisted state for one thread.

        Args:
            thread_id: LangGraph thread identifier.
            datasource_name: Datasource identifier.
            schema_name: Optional schema focus.

        Returns:
            ChatSessionModel: Dashboard-ready state snapshot for the thread.
        """

        resolved_datasource = self._settings.resolve_datasource_name(datasource_name)
        config = {"configurable": {"thread_id": thread_id}}
        with self._agent_session(
            datasource_name=resolved_datasource,
            schema_name=schema_name,
        ) as agent:
            try:
                state = agent.get_state(config)
            except Exception:  # noqa: BLE001
                return ChatSessionModel(
                    thread_id=thread_id,
                    datasource_name=resolved_datasource,
                    schema_name=schema_name,
                )
            return self._session_from_values(
                thread_id=thread_id,
                datasource_name=resolved_datasource,
                schema_name=schema_name,
                values=getattr(state, "values", {}) or {},
            )

    @contextmanager
    def _agent_session(
        self,
        *,
        datasource_name: str,
        schema_name: str | None,
    ) -> Iterator[Any]:
        """Build a short-lived agent session over shared repo services."""

        container = build_service_container(datasource_name, settings=self._settings)
        try:
            model = self._model or create_runtime_chat_model(self._settings)
            if self._checkpointer is not None:
                with nullcontext(self._checkpointer) as checkpointer:
                    yield create_sqldbagent_agent(
                        services=container,
                        model=model,
                        datasource_name=datasource_name,
                        settings=self._settings,
                        schema_name=schema_name,
                        checkpointer=checkpointer,
                    )
                return

            if (
                self._settings.agent.checkpoint.backend == "postgres"
                and self._settings.agent.checkpoint.postgres_url is not None
            ):
                with create_sync_postgres_checkpointer(
                    settings=self._settings
                ) as checkpointer:
                    yield create_sqldbagent_agent(
                        services=container,
                        model=model,
                        datasource_name=datasource_name,
                        settings=self._settings,
                        schema_name=schema_name,
                        checkpointer=checkpointer,
                    )
                return

            yield create_sqldbagent_agent(
                services=container,
                model=model,
                datasource_name=datasource_name,
                settings=self._settings,
                schema_name=schema_name,
                checkpointer=create_memory_checkpointer(),
            )
        finally:
            container.close()

    def _session_from_values(
        self,
        *,
        thread_id: str,
        datasource_name: str,
        schema_name: str | None,
        values: dict[str, Any],
    ) -> ChatSessionModel:
        """Build a dashboard chat session snapshot from agent state values."""

        return ChatSessionModel(
            thread_id=thread_id,
            datasource_name=datasource_name,
            schema_name=schema_name,
            messages=self._render_messages(values.get("messages", [])),
            dashboard_payload=dict(values.get("dashboard_payload") or {}),
            observability=self._build_observability_payload(),
            latest_snapshot_id=values.get("latest_snapshot_id"),
            latest_snapshot_summary=values.get("latest_snapshot_summary"),
            tool_call_digest=list(values.get("tool_call_digest") or []),
        )

    def _build_observability_payload(self) -> dict[str, object]:
        """Build UI-friendly observability details for the active session.

        Returns:
            dict[str, object]: Checkpoint and LangSmith status details.
        """

        langsmith_settings = self._settings.langsmith
        return {
            "checkpoint_backend": self._settings.agent.checkpoint.backend,
            "checkpoint_is_durable": self._settings.agent.checkpoint.backend
            == "postgres",
            "langsmith_tracing": is_langsmith_tracing_enabled(self._settings),
            "langsmith_project": langsmith_settings.project,
            "langsmith_endpoint": langsmith_settings.endpoint,
            "langsmith_workspace_id": langsmith_settings.workspace_id,
            "langsmith_tags": list(langsmith_settings.tags),
        }

    def _render_messages(self, messages: list[Any]) -> list[ChatMessageModel]:
        """Convert LangChain/LangGraph messages into dashboard transcript rows."""

        rendered: list[ChatMessageModel] = []
        for message in messages:
            message_type = getattr(message, "type", None) or "unknown"
            if message_type == "system":
                continue
            role = {
                "human": "user",
                "ai": "assistant",
                "tool": "tool",
            }.get(message_type, "assistant")
            content = self._render_content(getattr(message, "content", ""))
            if not content and message_type == "ai":
                tool_calls = getattr(message, "tool_calls", None) or []
                if tool_calls:
                    content = "Calling tools: " + ", ".join(
                        str(call.get("name", "tool")) for call in tool_calls
                    )
            if not content:
                continue
            rendered.append(
                ChatMessageModel(
                    role=role,
                    content=content,
                    kind=message_type,
                    name=getattr(message, "name", None),
                    status=getattr(message, "status", None),
                )
            )
        return rendered

    def _render_content(self, content: Any) -> str:
        """Render a LangChain message content payload into readable text."""

        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, dict):
            return orjson.dumps(content, option=orjson.OPT_INDENT_2).decode()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict):
                    text_payload = item.get("text")
                    if text_payload is not None:
                        parts.append(str(text_payload))
                    else:
                        parts.append(
                            orjson.dumps(item, option=orjson.OPT_INDENT_2).decode()
                        )
                    continue
                parts.append(str(item))
            return "\n".join(part.strip() for part in parts if part).strip()
        return str(content).strip()
