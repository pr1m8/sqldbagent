"""MCP CLI tests."""

from __future__ import annotations

from typing import Any

from typer.testing import CliRunner

from sqldbagent.cli.app import app
from sqldbagent.core.config import AppSettings, DatasourceSettings, MCPSettings
from sqldbagent.core.enums import Dialect


def test_mcp_serve_uses_settings_defaults(monkeypatch) -> None:
    """Serve MCP with the configured transport defaults."""

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url="sqlite+pysqlite:///:memory:",
            )
        ],
        mcp=MCPSettings(
            transport="streamable-http",
            host="127.0.0.1",
            port=7777,
            path="/sqldbagent",
            show_banner=False,
            stateless_http=True,
        ),
    )

    run_calls: list[dict[str, Any]] = []

    class StubServer:
        """Minimal FastMCP stub used by the CLI test."""

        def run(self, **kwargs: Any) -> None:
            """Record CLI kwargs instead of starting a server."""

            run_calls.append(kwargs)

    class StubContainer:
        """Minimal service container stub for the CLI test."""

        def close(self) -> None:
            """Match the real container close interface."""

    monkeypatch.setattr("sqldbagent.cli.mcp.load_settings", lambda: settings)
    monkeypatch.setattr(
        "sqldbagent.cli.mcp.build_service_container",
        lambda *args, **kwargs: StubContainer(),
    )
    monkeypatch.setattr(
        "sqldbagent.cli.mcp.create_mcp_server",
        lambda container: StubServer(),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["mcp", "serve"])
    if result.exit_code != 0:
        raise AssertionError(result.output)
    if len(run_calls) != 1:
        raise AssertionError(run_calls)
    run_kwargs = run_calls[0]
    if run_kwargs.get("transport") != "streamable-http":
        raise AssertionError(run_kwargs)
    if run_kwargs.get("host") != "127.0.0.1":
        raise AssertionError(run_kwargs)
    if run_kwargs.get("port") != 7777:
        raise AssertionError(run_kwargs)
    if run_kwargs.get("path") != "/sqldbagent":
        raise AssertionError(run_kwargs)
    if run_kwargs.get("stateless_http") is not True:
        raise AssertionError(run_kwargs)
