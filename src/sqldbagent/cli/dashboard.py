"""Dashboard CLI commands."""

from __future__ import annotations

import os
import subprocess  # nosec B404
import sys
from pathlib import Path

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.cli._typer import load_typer

typer = load_typer()
app = typer.Typer(help="Dashboard commands.")


@app.command("serve")
def serve(
    datasource: str | None = None,
    schema: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8501,
    headless: bool = True,
) -> None:
    """Run the Streamlit dashboard chat surface.

    Args:
        datasource: Optional default datasource for the dashboard session.
        schema: Optional default schema for the dashboard session.
        host: Dashboard bind address.
        port: Dashboard port.
        headless: Whether Streamlit should run without auto-opening a browser.
    """

    require_dependency("streamlit", "streamlit")
    app_path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    env = os.environ.copy()
    if datasource is not None:
        env["SQLDBAGENT_DEFAULT_DATASOURCE"] = datasource
    if schema is not None:
        env["SQLDBAGENT_DEFAULT_SCHEMA"] = schema
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true" if headless else "false",
        "--browser.gatherUsageStats",
        "false",
    ]
    raise typer.Exit(
        code=subprocess.run(command, env=env, check=False).returncode  # nosec B603
    )
