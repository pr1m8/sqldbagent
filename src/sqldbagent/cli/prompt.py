"""Prompt export CLI commands."""

from __future__ import annotations

from pathlib import Path

import orjson

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.prompts.service import SnapshotPromptService
from sqldbagent.snapshot.service import SnapshotService

typer = load_typer()
app = typer.Typer(help="Prompt export commands.")


@app.command("export")
def export(datasource: str, schema: str) -> None:
    """Export a durable prompt bundle from the latest saved schema snapshot.

    Args:
        datasource: Datasource identifier.
        schema: Schema whose latest saved snapshot should be exported.
    """

    container = build_service_container(datasource)
    try:
        bundle = container.snapshotter.load_latest_saved_snapshot(schema)
        prompt_bundle = container.prompt_service.create_prompt_bundle(bundle)
        path = container.prompt_service.save_prompt_bundle(prompt_bundle)
    finally:
        container.close()

    typer.echo(str(path))


@app.command("show")
def show(path: str) -> None:
    """Load and print a saved prompt bundle.

    Args:
        path: Prompt-bundle path.
    """

    bundle = SnapshotPromptService.load_prompt_bundle(Path(path))
    typer.echo(
        orjson.dumps(
            bundle.model_dump(mode="json"),
            option=orjson.OPT_INDENT_2,
        ).decode()
    )


@app.command("export-from-snapshot")
def export_from_snapshot(path: str) -> None:
    """Export a prompt bundle from a specific snapshot path.

    Args:
        path: Snapshot path to export from.
    """

    snapshot = SnapshotService.load_snapshot(Path(path))
    container = build_service_container(snapshot.datasource_name)
    try:
        prompt_bundle = container.prompt_service.create_prompt_bundle(snapshot)
        output_path = container.prompt_service.save_prompt_bundle(prompt_bundle)
    finally:
        container.close()

    typer.echo(str(output_path))
