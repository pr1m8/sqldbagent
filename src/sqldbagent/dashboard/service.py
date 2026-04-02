"""Dashboard chat service built on top of the persisted LangGraph agent."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from pathlib import Path
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
from sqldbagent.dashboard.models import (
    ChatMessageModel,
    ChatSessionModel,
    DashboardThreadEntryModel,
)
from sqldbagent.diagrams.models import DiagramBundleModel
from sqldbagent.prompts.models import PromptBundleModel
from sqldbagent.snapshot.models import SnapshotBundleModel
from sqldbagent.snapshot.service import SnapshotService

_MAX_EXAMPLE_QUESTIONS = 5


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
            session = self._session_from_values(
                thread_id=thread_id,
                datasource_name=resolved_datasource,
                schema_name=schema_name,
                values=result,
                diagram_bundle=self._load_or_create_diagram_bundle(
                    datasource_name=resolved_datasource,
                    schema_name=schema_name,
                    values=result,
                ),
                prompt_bundle=self._load_or_create_prompt_bundle(
                    datasource_name=resolved_datasource,
                    schema_name=schema_name,
                    values=result,
                ),
            )
            self._upsert_thread_entry(session)
            return session.model_copy(
                update={
                    "available_threads": self.list_threads(
                        datasource_name=resolved_datasource,
                        schema_name=schema_name,
                    )
                }
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
                    available_threads=self.list_threads(
                        datasource_name=resolved_datasource,
                        schema_name=schema_name,
                    ),
                )
            session = self._session_from_values(
                thread_id=thread_id,
                datasource_name=resolved_datasource,
                schema_name=schema_name,
                values=getattr(state, "values", {}) or {},
                diagram_bundle=self._load_or_create_diagram_bundle(
                    datasource_name=resolved_datasource,
                    schema_name=schema_name,
                    values=getattr(state, "values", {}) or {},
                ),
                prompt_bundle=self._load_or_create_prompt_bundle(
                    datasource_name=resolved_datasource,
                    schema_name=schema_name,
                    values=getattr(state, "values", {}) or {},
                ),
            )
            if session.messages or session.latest_snapshot_id:
                self._upsert_thread_entry(session)
            return session.model_copy(
                update={
                    "available_threads": self.list_threads(
                        datasource_name=resolved_datasource,
                        schema_name=schema_name,
                    )
                }
            )

    def list_threads(
        self,
        *,
        datasource_name: str | None = None,
        schema_name: str | None = None,
    ) -> list[DashboardThreadEntryModel]:
        """List persisted dashboard thread summaries.

        Args:
            datasource_name: Optional datasource filter.
            schema_name: Optional schema filter.

        Returns:
            list[DashboardThreadEntryModel]: Matching thread summaries ordered by
            most recently updated first.
        """

        entries = self._read_thread_entries()
        filtered = [
            entry
            for entry in entries
            if (datasource_name is None or entry.datasource_name == datasource_name)
            and (schema_name is None or entry.schema_name == schema_name)
        ]
        return sorted(filtered, key=lambda entry: entry.updated_at, reverse=True)

    def render_prompt_markdown(self, bundle: PromptBundleModel) -> str:
        """Render one stored prompt bundle as Markdown for dashboard downloads.

        Args:
            bundle: Prompt bundle to render.

        Returns:
            str: Human-readable Markdown prompt artifact.
        """

        container = build_service_container(
            bundle.datasource_name,
            settings=self._settings,
        )
        try:
            prompt_service = container.prompt_service
            if prompt_service is None:
                return bundle.model_dump_json(indent=2)
            return prompt_service.render_markdown(bundle)
        finally:
            container.close()

    def update_prompt_bundle_enhancement(
        self,
        *,
        datasource_name: str,
        schema_name: str,
        active: bool,
        user_context: str | None,
        business_rules: str | None,
        answer_style: str | None,
        refresh_generated: bool = False,
    ) -> PromptBundleModel | None:
        """Update prompt-enhancement state and regenerate the prompt bundle.

        Args:
            datasource_name: Datasource identifier.
            schema_name: Schema name.
            active: Whether the enhancement should be active.
            user_context: Freeform user context or domain notes.
            business_rules: Business rules and caveats.
            answer_style: Preferred answer style for downstream outputs.
            refresh_generated: Whether DB-aware guidance should be regenerated.

        Returns:
            PromptBundleModel | None: Updated prompt bundle or `None` when no
            snapshot exists yet for the schema.
        """

        resolved_datasource = self._settings.resolve_datasource_name(datasource_name)
        snapshot = self._resolve_session_snapshot(
            datasource_name=resolved_datasource,
            schema_name=schema_name,
            values={},
        )
        if snapshot is None:
            return None
        container = build_service_container(
            resolved_datasource, settings=self._settings
        )
        try:
            prompt_service = container.prompt_service
            if prompt_service is None:
                return None
            enhancement = prompt_service.update_prompt_enhancement(
                snapshot,
                active=active,
                user_context=user_context,
                business_rules=business_rules,
                answer_style=answer_style,
                refresh_generated=refresh_generated,
            )
            bundle = prompt_service.create_prompt_bundle(
                snapshot,
                enhancement=enhancement,
            )
            prompt_service.save_prompt_bundle(bundle)
            return bundle
        finally:
            container.close()

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
        diagram_bundle: DiagramBundleModel | None = None,
        prompt_bundle: PromptBundleModel | None = None,
    ) -> ChatSessionModel:
        """Build a dashboard chat session snapshot from agent state values."""

        snapshot = self._resolve_session_snapshot(
            datasource_name=datasource_name,
            schema_name=schema_name,
            values=values,
        )
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
            diagram_bundle=diagram_bundle,
            prompt_bundle=prompt_bundle,
            example_questions=self._build_example_questions(
                snapshot=snapshot,
                schema_name=schema_name,
            ),
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

    def _load_or_create_diagram_bundle(
        self,
        *,
        datasource_name: str,
        schema_name: str | None,
        values: dict[str, Any],
    ) -> DiagramBundleModel | None:
        """Load or create the latest diagram bundle for one dashboard session."""

        snapshot = self._resolve_session_snapshot(
            datasource_name=datasource_name,
            schema_name=schema_name,
            values=values,
        )
        if snapshot is None:
            return None
        container = build_service_container(datasource_name, settings=self._settings)
        try:
            diagram_service = container.diagram_service
            if diagram_service is None:
                return None
            bundle_path = diagram_service.bundle_path(
                datasource_name=datasource_name,
                schema_name=snapshot.regenerate.schema_name,
                snapshot_id=snapshot.snapshot_id,
            )
            if bundle_path.exists():
                return diagram_service.load_diagram_bundle(bundle_path)
            bundle = diagram_service.create_diagram_bundle(snapshot)
            diagram_service.save_diagram_bundle(bundle)
            return bundle
        finally:
            container.close()

    def _load_or_create_prompt_bundle(
        self,
        *,
        datasource_name: str,
        schema_name: str | None,
        values: dict[str, Any],
    ) -> PromptBundleModel | None:
        """Load or create the latest prompt bundle for one dashboard session."""

        snapshot = self._resolve_session_snapshot(
            datasource_name=datasource_name,
            schema_name=schema_name,
            values=values,
        )
        if snapshot is None:
            return None
        container = build_service_container(datasource_name, settings=self._settings)
        try:
            prompt_service = container.prompt_service
            if prompt_service is None:
                return None
            enhancement = prompt_service.load_or_create_enhancement(snapshot)
            bundle = prompt_service.create_prompt_bundle(
                snapshot,
                enhancement=enhancement,
            )
            prompt_service.save_prompt_bundle(bundle)
            return bundle
        finally:
            container.close()

    def _resolve_session_snapshot(
        self,
        *,
        datasource_name: str,
        schema_name: str | None,
        values: dict[str, Any],
    ) -> SnapshotBundleModel | None:
        """Resolve the most relevant snapshot bundle for dashboard artifacts."""

        requested_snapshot_id = values.get("latest_snapshot_id")
        entries = SnapshotService.list_saved_snapshots(
            self._settings.artifacts,
            datasource_name=datasource_name,
            schema_name=schema_name,
        )
        root = SnapshotService._snapshot_dir_from_artifacts(self._settings.artifacts)
        if requested_snapshot_id is not None:
            for entry in entries:
                if entry.snapshot_id == requested_snapshot_id:
                    return SnapshotService.load_snapshot(root / entry.path)
        if entries:
            return SnapshotService.load_snapshot(root / entries[0].path)
        return None

    def _build_example_questions(
        self,
        *,
        snapshot: SnapshotBundleModel | None,
        schema_name: str | None,
    ) -> list[str]:
        """Build snapshot-aware starter questions for the dashboard chat.

        Args:
            snapshot: Relevant stored snapshot for the active session.
            schema_name: Optional schema focus.

        Returns:
            list[str]: Ordered starter questions for the dashboard UI.
        """

        resolved_schema = schema_name or "default"
        questions = [
            f"Summarize the main entities and relationships in the {resolved_schema} schema.",
            f"Which tables in the {resolved_schema} schema are largest by row count or storage?",
            f"What data quality, uniqueness, or identifier signals stand out in the {resolved_schema} schema?",
        ]
        if snapshot is None:
            return questions[:_MAX_EXAMPLE_QUESTIONS]

        demo_questions = self._build_demo_example_questions(snapshot)
        if demo_questions:
            questions = [*demo_questions, *questions]

        profiles_by_table = {
            profile.table_name: profile
            for profile in snapshot.profiles
            if profile.schema_name == snapshot.regenerate.schema_name
        }
        ranked_tables = sorted(
            snapshot.schema_metadata.tables,
            key=lambda table: (
                (
                    (profiles_by_table.get(table.name).storage_bytes or 0)
                    if profiles_by_table.get(table.name) is not None
                    else 0
                ),
                (
                    (profiles_by_table.get(table.name).row_count or 0)
                    if profiles_by_table.get(table.name) is not None
                    else 0
                ),
                (
                    (profiles_by_table.get(table.name).relationship_count or 0)
                    if profiles_by_table.get(table.name) is not None
                    else 0
                ),
            ),
            reverse=True,
        )
        if ranked_tables:
            top_table = ranked_tables[0]
            qualified_name = ".".join(
                part for part in [top_table.schema_name, top_table.name] if part
            )
            questions.append(
                f"Profile {qualified_name} and explain its key columns, sample rows, and likely business meaning."
            )

        if snapshot.relationship_edges:
            edge = snapshot.relationship_edges[0]
            source_name = ".".join(
                part for part in [edge.source_schema, edge.source_table] if part
            )
            target_name = ".".join(
                part for part in [edge.target_schema, edge.target_table] if part
            )
            questions.append(
                f"How do {source_name} and {target_name} relate, and what is the safest join path between them?"
            )

        if snapshot.schema_metadata.views:
            questions.append(
                f"Which views in the {resolved_schema} schema are most useful, and what does each one represent?"
            )

        seen: set[str] = set()
        unique_questions: list[str] = []
        for question in questions:
            if question in seen:
                continue
            seen.add(question)
            unique_questions.append(question)
            if len(unique_questions) == _MAX_EXAMPLE_QUESTIONS:
                break
        return unique_questions

    @staticmethod
    def _build_demo_example_questions(snapshot: SnapshotBundleModel) -> list[str]:
        """Build tailored starter questions for the bundled demo schema.

        Args:
            snapshot: Relevant stored snapshot for the active session.

        Returns:
            list[str]: Demo-specific starter questions when the known demo
            tables are present; otherwise an empty list.
        """

        table_names = {table.name for table in snapshot.schema_metadata.tables}
        required_tables = {
            "customers",
            "orders",
            "order_items",
            "products",
            "support_tickets",
        }
        if not required_tables.issubset(table_names):
            return []

        schema_name = snapshot.regenerate.schema_name
        return [
            (
                f"Summarize the customer lifecycle in {schema_name}: how customers, "
                "orders, order_items, products, and support_tickets connect."
            ),
            (
                "Which customers look most commercially important based on order "
                "activity, and what evidence supports that?"
            ),
            (
                "Explain the safest join path to analyze revenue by customer "
                "segment and product category."
            ),
            (
                "What support-ticket patterns stand out by customer segment, "
                "priority, and order activity?"
            ),
            (
                "Profile the most important business identifiers in the demo "
                "schema, including customer_code, order_number, sku, and ticket_number."
            ),
        ]

    @property
    def _thread_registry_path(self) -> Path:
        """Return the persisted dashboard thread-registry path."""

        return (
            Path(self._settings.artifacts.root_dir)
            / "dashboard"
            / "thread-registry.json"
        )

    def _read_thread_entries(self) -> list[DashboardThreadEntryModel]:
        """Read the persisted dashboard thread registry from disk."""

        path = self._thread_registry_path
        if not path.exists():
            return []
        raw_entries = orjson.loads(path.read_bytes())
        return [DashboardThreadEntryModel.model_validate(item) for item in raw_entries]

    def _write_thread_entries(self, entries: list[DashboardThreadEntryModel]) -> None:
        """Persist the dashboard thread registry to disk."""

        path = self._thread_registry_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            orjson.dumps(
                [entry.model_dump(mode="json") for entry in entries],
                option=orjson.OPT_INDENT_2,
            )
        )

    def _upsert_thread_entry(self, session: ChatSessionModel) -> None:
        """Create or update one persisted dashboard thread summary."""

        now = datetime.now(UTC)
        last_user_message = next(
            (
                self._summarize_preview(message.content)
                for message in reversed(session.messages)
                if message.role == "user"
            ),
            None,
        )
        last_assistant_message = next(
            (
                self._summarize_preview(message.content)
                for message in reversed(session.messages)
                if message.role == "assistant"
            ),
            None,
        )
        entries = self._read_thread_entries()
        entry_key = (
            session.thread_id,
            session.datasource_name,
            session.schema_name,
        )
        for index, entry in enumerate(entries):
            if (
                entry.thread_id,
                entry.datasource_name,
                entry.schema_name,
            ) == entry_key:
                entries[index] = entry.model_copy(
                    update={
                        "updated_at": now,
                        "message_count": len(session.messages),
                        "latest_snapshot_id": session.latest_snapshot_id,
                        "last_user_message": last_user_message,
                        "last_assistant_message": last_assistant_message,
                    }
                )
                self._write_thread_entries(entries)
                return
        entries.append(
            DashboardThreadEntryModel(
                thread_id=session.thread_id,
                datasource_name=session.datasource_name,
                schema_name=session.schema_name,
                created_at=now,
                updated_at=now,
                message_count=len(session.messages),
                latest_snapshot_id=session.latest_snapshot_id,
                last_user_message=last_user_message,
                last_assistant_message=last_assistant_message,
            )
        )
        self._write_thread_entries(entries)

    @staticmethod
    def _summarize_preview(content: str, *, limit: int = 96) -> str:
        """Collapse one message into a compact preview line."""

        normalized = " ".join(content.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "…"
