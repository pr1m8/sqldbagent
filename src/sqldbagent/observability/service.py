"""Append-only local observability artifact service."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson
from pydantic import ValidationError

from sqldbagent.core.config import AppSettings, ArtifactSettings, load_settings
from sqldbagent.core.serialization import to_jsonable
from sqldbagent.observability.models import (
    AuditEventModel,
    CostEstimateModel,
    ModelUsageEventModel,
    RunUsageSummaryModel,
    ToolUsageEventModel,
)

_AUDIT_DIR = "audit"
_EVENTS_DIR = "events"
_USAGE_DIR = "usage"


class ObservabilityService:
    """Persist and summarize local usage and audit events.

    The service writes append-only JSONL artifacts under the configured artifact
    root. It does not participate in SQL execution or agent control flow; it is
    a side-channel for explaining what happened after the guarded path ran.
    """

    def __init__(
        self,
        *,
        artifacts: ArtifactSettings | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        """Initialize the observability service."""

        resolved_settings = settings or load_settings()
        self._settings = resolved_settings
        self._artifacts = artifacts or resolved_settings.artifacts

    def append_audit_event(self, event: AuditEventModel) -> Path:
        """Append one audit event and return the JSONL path."""

        path = self._daily_path(_EVENTS_DIR, event.started_at)
        self._append_jsonl(path, event)
        return path

    def append_model_usage_event(self, event: ModelUsageEventModel) -> Path:
        """Append one model-usage event and return the JSONL path."""

        path = self._daily_path(_USAGE_DIR, event.created_at)
        self._append_jsonl(path, event)
        return path

    def append_tool_usage_event(self, event: ToolUsageEventModel) -> Path:
        """Append one tool-usage event and return the JSONL path."""

        path = self._daily_path(_USAGE_DIR, event.created_at)
        self._append_jsonl(path, event)
        return path

    def append_model_usage_events(self, events: Iterable[ModelUsageEventModel]) -> int:
        """Append model-usage events and return the number written."""

        count = 0
        for event in events:
            self.append_model_usage_event(event)
            count += 1
        return count

    def append_tool_usage_events(self, events: Iterable[ToolUsageEventModel]) -> int:
        """Append tool-usage events and return the number written."""

        count = 0
        for event in events:
            self.append_tool_usage_event(event)
            count += 1
        return count

    def extract_model_usage_events(
        self,
        messages: Iterable[Any],
        *,
        run_id: str,
        surface: str,
        thread_id: str | None = None,
        datasource_name: str | None = None,
        schema_name: str | None = None,
    ) -> list[ModelUsageEventModel]:
        """Extract model usage events from LangChain-like messages."""

        events: list[ModelUsageEventModel] = []
        for message in messages:
            usage = _extract_usage_metadata(message)
            if not usage:
                continue
            model_name = (
                _extract_model_name(message) or self._settings.llm.default_model
            )
            provider = (
                _extract_provider_name(message) or self._settings.llm.default_provider
            )
            input_tokens = _first_int(
                usage,
                "input_tokens",
                "prompt_tokens",
                "input_token_count",
            )
            output_tokens = _first_int(
                usage,
                "output_tokens",
                "completion_tokens",
                "output_token_count",
            )
            total_tokens = _first_int(usage, "total_tokens", "total_token_count")
            if total_tokens is None:
                total_tokens = _sum_optional_ints(input_tokens, output_tokens)
            cache_read_tokens = _extract_nested_int(
                usage,
                ("input_token_details", "cache_read"),
                ("input_token_details", "cache_read_tokens"),
                ("prompt_tokens_details", "cached_tokens"),
            )
            cache_write_tokens = _extract_nested_int(
                usage,
                ("input_token_details", "cache_creation"),
                ("input_token_details", "cache_write"),
            )
            reasoning_tokens = _extract_nested_int(
                usage,
                ("output_token_details", "reasoning"),
                ("completion_tokens_details", "reasoning_tokens"),
            )
            events.append(
                ModelUsageEventModel(
                    run_id=run_id,
                    thread_id=thread_id,
                    datasource_name=datasource_name,
                    schema_name=schema_name,
                    surface=surface,
                    provider=provider,
                    model=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_write_tokens=cache_write_tokens,
                    reasoning_tokens=reasoning_tokens,
                    cost=CostEstimateModel(pricing_source="not_configured"),
                    metadata={
                        "message_type": getattr(message, "type", None),
                        "usage_metadata": to_jsonable(usage),
                    },
                )
            )
        return events

    def extract_tool_usage_events(
        self,
        messages: Iterable[Any],
        *,
        run_id: str,
        surface: str,
        thread_id: str | None = None,
        datasource_name: str | None = None,
        schema_name: str | None = None,
    ) -> list[ToolUsageEventModel]:
        """Extract tool events from LangChain-like tool messages."""

        events: list[ToolUsageEventModel] = []
        for message in messages:
            if getattr(message, "type", None) != "tool":
                continue
            content = str(getattr(message, "content", "") or "")
            events.append(
                ToolUsageEventModel(
                    run_id=run_id,
                    thread_id=thread_id,
                    datasource_name=datasource_name,
                    schema_name=schema_name,
                    surface=surface,
                    tool_name=str(getattr(message, "name", "tool") or "tool"),
                    status=getattr(message, "status", None),
                    output_characters=len(content),
                    compressed_output_characters=min(len(content), 160),
                    metadata={
                        "tool_call_id": getattr(message, "tool_call_id", None),
                    },
                )
            )
        return events

    def read_recent_audit_events(
        self,
        *,
        limit: int = 100,
        datasource_name: str | None = None,
        schema_name: str | None = None,
    ) -> list[AuditEventModel]:
        """Read recent audit events from local artifacts."""

        rows = self._read_recent_rows(_EVENTS_DIR, limit=limit * 3)
        events: list[AuditEventModel] = []
        for row in rows:
            event = _parse_audit_event(row)
            if event is None:
                continue
            if datasource_name is not None and event.datasource_name != datasource_name:
                continue
            if schema_name is not None and event.schema_name != schema_name:
                continue
            events.append(event)
            if len(events) >= limit:
                break
        return events

    def read_recent_usage_events(
        self,
        *,
        limit: int = 100,
        datasource_name: str | None = None,
        schema_name: str | None = None,
    ) -> list[ModelUsageEventModel | ToolUsageEventModel]:
        """Read recent model and tool usage events from local artifacts."""

        rows = self._read_recent_rows(_USAGE_DIR, limit=limit * 3)
        events: list[ModelUsageEventModel | ToolUsageEventModel] = []
        for row in rows:
            event = _parse_usage_event(row)
            if event is None:
                continue
            if datasource_name is not None and event.datasource_name != datasource_name:
                continue
            if schema_name is not None and event.schema_name != schema_name:
                continue
            events.append(event)
            if len(events) >= limit:
                break
        return events

    def summarize_usage(
        self,
        events: Iterable[ModelUsageEventModel | ToolUsageEventModel],
    ) -> RunUsageSummaryModel:
        """Summarize local usage events."""

        event_list = list(events)
        model_events = [
            event for event in event_list if isinstance(event, ModelUsageEventModel)
        ]
        tool_events = [
            event for event in event_list if isinstance(event, ToolUsageEventModel)
        ]
        started_at = _min_datetime([_event_created_at(event) for event in event_list])
        completed_at = _max_datetime([_event_created_at(event) for event in event_list])
        total_costs = [
            event.cost.total_cost
            for event in model_events
            if event.cost is not None and event.cost.total_cost is not None
        ]
        return RunUsageSummaryModel(
            event_count=len(event_list),
            model_event_count=len(model_events),
            tool_event_count=len(tool_events),
            total_input_tokens=sum(event.input_tokens or 0 for event in model_events),
            total_output_tokens=sum(event.output_tokens or 0 for event in model_events),
            total_tokens=sum(event.total_tokens or 0 for event in model_events),
            total_cost_usd=round(sum(total_costs), 8) if total_costs else None,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _daily_path(self, child_dir: str, timestamp: datetime) -> Path:
        """Build a daily JSONL path for one observability child directory."""

        date_value = timestamp.astimezone(UTC).date().isoformat()
        return (
            Path(self._artifacts.root_dir)
            / _AUDIT_DIR
            / child_dir
            / f"{date_value}.jsonl"
        )

    def _append_jsonl(self, path: Path, model: Any) -> None:
        """Append one JSON-serializable model to a JSONL artifact."""

        path.parent.mkdir(parents=True, exist_ok=True)
        payload = model.model_dump(mode="json")
        with path.open("ab") as handle:
            handle.write(orjson.dumps(payload, option=orjson.OPT_APPEND_NEWLINE))

    def _read_recent_rows(self, child_dir: str, *, limit: int) -> list[dict[str, Any]]:
        """Read recent JSONL rows newest-first from one child directory."""

        directory = Path(self._artifacts.root_dir) / _AUDIT_DIR / child_dir
        if not directory.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.jsonl"), reverse=True):
            lines = path.read_bytes().splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                try:
                    row = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
                if len(rows) >= limit:
                    return rows
        return rows


def _extract_usage_metadata(message: Any) -> dict[str, Any] | None:
    """Extract provider usage metadata from one LangChain-like message."""

    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict) and usage:
        return usage
    response_metadata = getattr(message, "response_metadata", None)
    if isinstance(response_metadata, dict):
        token_usage = response_metadata.get("token_usage")
        if isinstance(token_usage, dict) and token_usage:
            return token_usage
        usage_metadata = response_metadata.get("usage_metadata")
        if isinstance(usage_metadata, dict) and usage_metadata:
            return usage_metadata
    additional_kwargs = getattr(message, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict):
        token_usage = additional_kwargs.get("token_usage")
        if isinstance(token_usage, dict) and token_usage:
            return token_usage
    return None


def _parse_audit_event(row: dict[str, Any]) -> AuditEventModel | None:
    """Parse one audit row, returning `None` for stale or corrupt rows."""

    try:
        return AuditEventModel.model_validate(row)
    except ValidationError:
        return None


def _parse_usage_event(
    row: dict[str, Any],
) -> ModelUsageEventModel | ToolUsageEventModel | None:
    """Parse one usage row, returning `None` for stale or corrupt rows."""

    try:
        if "tool_name" in row:
            return ToolUsageEventModel.model_validate(row)
        return ModelUsageEventModel.model_validate(row)
    except ValidationError:
        return None


def _extract_model_name(message: Any) -> str | None:
    """Extract model name from one LangChain-like message."""

    response_metadata = getattr(message, "response_metadata", None)
    if isinstance(response_metadata, dict):
        for key in ("model_name", "model", "model_id"):
            value = response_metadata.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _extract_provider_name(message: Any) -> str | None:
    """Extract provider name from one LangChain-like message."""

    response_metadata = getattr(message, "response_metadata", None)
    if isinstance(response_metadata, dict):
        for key in ("provider", "ls_provider"):
            value = response_metadata.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _first_int(payload: dict[str, Any], *keys: str) -> int | None:
    """Return the first integer-like value for any key."""

    for key in keys:
        value = payload.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
    return None


def _extract_nested_int(
    payload: dict[str, Any],
    *paths: tuple[str, str],
) -> int | None:
    """Return the first integer-like value for any nested key path."""

    for parent_key, child_key in paths:
        parent = payload.get(parent_key)
        if not isinstance(parent, dict):
            continue
        value = parent.get(child_key)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
    return None


def _sum_optional_ints(*values: int | None) -> int | None:
    """Sum integers only when at least one is present."""

    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _event_created_at(
    event: ModelUsageEventModel | ToolUsageEventModel,
) -> datetime:
    """Return the created timestamp for a usage event."""

    return event.created_at


def _min_datetime(values: list[datetime]) -> datetime | None:
    """Return the earliest timestamp from a list."""

    return min(values) if values else None


def _max_datetime(values: list[datetime]) -> datetime | None:
    """Return the latest timestamp from a list."""

    return max(values) if values else None
