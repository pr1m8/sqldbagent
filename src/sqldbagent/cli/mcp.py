"""MCP CLI commands."""

from __future__ import annotations

from typing import Annotated, Any

from sqldbagent.adapters.mcp import create_mcp_server
from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.core.config import load_settings

typer = load_typer()
app = typer.Typer(help="FastMCP commands.")


@app.command("serve")
def serve(
    datasource: Annotated[str | None, typer.Argument()] = None,
    transport: Annotated[str | None, typer.Option("--transport")] = None,
    host: Annotated[str | None, typer.Option("--host")] = None,
    port: Annotated[int | None, typer.Option("--port")] = None,
    path: Annotated[str | None, typer.Option("--path")] = None,
    show_banner: Annotated[
        bool | None, typer.Option("--show-banner/--no-show-banner")
    ] = None,
    stateless_http: Annotated[
        bool | None, typer.Option("--stateless-http/--stateful-http")
    ] = None,
) -> None:
    """Serve the sqldbagent FastMCP adapter.

    Args:
        datasource: Optional datasource identifier. Uses the configured default when omitted.
        transport: Optional transport override.
        host: Optional host override for HTTP transports.
        port: Optional port override for HTTP transports.
        path: Optional path override for HTTP transports.
        show_banner: Optional FastMCP banner override.
        stateless_http: Optional stateless HTTP override.
    """

    settings = load_settings()
    resolved_datasource = datasource or settings.resolve_default_datasource_name()
    container = build_service_container(
        resolved_datasource,
        settings=settings,
        include_async_engine=True,
    )
    try:
        server = create_mcp_server(container)
        resolved_transport = transport or settings.mcp.transport
        run_kwargs: dict[str, Any] = {
            "transport": resolved_transport,
            "show_banner": (
                settings.mcp.show_banner if show_banner is None else show_banner
            ),
        }
        if resolved_transport != "stdio":
            run_kwargs.update(
                {
                    "host": host or settings.mcp.host,
                    "port": settings.mcp.port if port is None else port,
                    "log_level": settings.mcp.log_level,
                }
            )
            if resolved_transport in {"http", "sse", "streamable-http"}:
                run_kwargs["path"] = path or settings.mcp.path
            if resolved_transport == "streamable-http":
                run_kwargs["stateless_http"] = (
                    settings.mcp.stateless_http
                    if stateless_http is None
                    else stateless_http
                )
        server.run(**run_kwargs)
    finally:
        container.close()
