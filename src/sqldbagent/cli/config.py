"""Configuration CLI commands."""

from __future__ import annotations

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.config import load_settings

typer = load_typer()
app = typer.Typer(help="Configuration commands.")


@app.command("validate")
def validate() -> None:
    """Validate application settings."""

    load_settings()
    typer.echo("Configuration is valid.")
