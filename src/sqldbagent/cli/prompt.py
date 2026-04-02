"""Prompt export CLI commands."""

from __future__ import annotations

from pathlib import Path

import orjson

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.core.config import load_settings
from sqldbagent.prompts.service import SnapshotPromptService
from sqldbagent.snapshot.service import SnapshotService

typer = load_typer()
app = typer.Typer(help="Prompt export commands.")
enhancement_app = typer.Typer(help="Prompt enhancement commands.")
app.add_typer(enhancement_app, name="enhancement")


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


@enhancement_app.command("show")
def show_enhancement(datasource: str, schema: str) -> None:
    """Load and print the saved prompt enhancement for one schema.

    Args:
        datasource: Datasource identifier.
        schema: Schema name.
    """

    resolved_datasource = load_settings().resolve_datasource_name(datasource)
    container = build_service_container(resolved_datasource)
    try:
        if container.prompt_service is None:
            raise typer.Exit(code=1)
        enhancement = container.prompt_service.load_saved_enhancement(
            datasource_name=resolved_datasource,
            schema_name=schema,
        )
    finally:
        container.close()

    if enhancement is None:
        typer.echo("No saved prompt enhancement was found.")
        raise typer.Exit(code=1)
    typer.echo(enhancement.model_dump_json(indent=2))


@enhancement_app.command("save")
def save_enhancement(
    datasource: str,
    schema: str,
    user_context: str = typer.Option(
        "", "--user-context", help="Freeform domain notes."
    ),
    business_rules: str = typer.Option(
        "",
        "--business-rules",
        help="Business rules or caveats to keep in the prompt.",
    ),
    answer_style: str = typer.Option(
        "",
        "--answer-style",
        help="Preferred answer style for the agent.",
    ),
    active: bool = typer.Option(
        True,
        "--active/--inactive",
        help="Whether the saved enhancement should be merged into prompts.",
    ),
    refresh_generated: bool = typer.Option(
        False,
        "--refresh-generated",
        help="Regenerate the DB-aware guidance from the latest stored snapshot.",
    ),
) -> None:
    """Save prompt-enhancement context for one datasource/schema pair.

    Args:
        datasource: Datasource identifier.
        schema: Schema name.
        user_context: Freeform domain notes.
        business_rules: Business rules or caveats.
        answer_style: Preferred answer style for agent responses.
        active: Whether the enhancement should be active.
        refresh_generated: Whether to refresh DB-aware guidance from the snapshot.
    """

    resolved_datasource = load_settings().resolve_datasource_name(datasource)
    container = build_service_container(resolved_datasource)
    try:
        if container.snapshotter is None or container.prompt_service is None:
            raise typer.Exit(code=1)
        snapshot = container.snapshotter.load_latest_saved_snapshot(schema)
        enhancement = container.prompt_service.update_prompt_enhancement(
            snapshot,
            active=active,
            user_context=user_context,
            business_rules=business_rules,
            answer_style=answer_style,
            refresh_generated=refresh_generated,
        )
        container.prompt_service.save_prompt_enhancement(enhancement)
        bundle = container.prompt_service.create_prompt_bundle(
            snapshot,
            enhancement=enhancement,
        )
        container.prompt_service.save_prompt_bundle(bundle)
        path = container.prompt_service.enhancement_path(
            datasource_name=resolved_datasource,
            schema_name=schema,
        )
    finally:
        container.close()

    typer.echo(str(path))
