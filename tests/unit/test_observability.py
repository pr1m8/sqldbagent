"""Local observability service tests."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from sqldbagent.core.config import AppSettings, ArtifactSettings
from sqldbagent.observability.models import AuditEventModel
from sqldbagent.observability.service import ObservabilityService


def test_observability_service_persists_audit_and_usage_events(
    tmp_path: Path,
) -> None:
    """Persist local audit and usage events as append-only artifacts."""

    settings = AppSettings(
        datasources=[],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
    )
    service = ObservabilityService(settings=settings)

    audit_path = service.append_audit_event(
        AuditEventModel(
            event_type="query.execute",
            surface="dashboard",
            datasource_name="sqlite",
            schema_name="main",
            dialect="sqlite",
            access_mode="read_only",
            read_only=True,
            touched={"row_count": 3},
        )
    )
    model_events = service.extract_model_usage_events(
        [
            AIMessage(
                content="hello",
                usage_metadata={
                    "input_tokens": 7,
                    "output_tokens": 11,
                    "total_tokens": 18,
                },
                response_metadata={"model_name": "test-model", "provider": "fake"},
            )
        ],
        run_id="run-1",
        surface="dashboard",
        thread_id="thread-1",
        datasource_name="sqlite",
        schema_name="main",
    )
    tool_events = service.extract_tool_usage_events(
        [
            ToolMessage(
                content="tool output",
                name="list_tables",
                tool_call_id="call-1",
            )
        ],
        run_id="run-1",
        surface="dashboard",
        thread_id="thread-1",
        datasource_name="sqlite",
        schema_name="main",
    )
    service.append_model_usage_events(model_events)
    service.append_tool_usage_events(tool_events)

    if not audit_path.exists():
        raise AssertionError(audit_path)
    audit_events = service.read_recent_audit_events(datasource_name="sqlite")
    usage_events = service.read_recent_usage_events(datasource_name="sqlite")
    summary = service.summarize_usage(usage_events)

    if audit_events[0].event_type != "query.execute":
        raise AssertionError(audit_events)
    if len(usage_events) != 2:
        raise AssertionError(usage_events)
    if summary.total_tokens != 18:
        raise AssertionError(summary)
    if summary.model_event_count != 1 or summary.tool_event_count != 1:
        raise AssertionError(summary)
