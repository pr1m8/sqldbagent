"""Snapshot CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import orjson

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.core.config import load_settings
from sqldbagent.snapshot.models import SnapshotBundleModel
from sqldbagent.snapshot.service import SnapshotService

typer = load_typer()
app = typer.Typer(help="Snapshot commands.")


@app.command("create")
def create(datasource: str, schema: str, sample_size: int | None = None) -> None:
    """Create and persist a schema snapshot.

    Args:
        datasource: Datasource identifier.
        schema: Schema name to snapshot.
        sample_size: Sample rows per profiled table.
    """

    settings = load_settings()
    resolved_sample_size = sample_size or settings.profiling.default_sample_size
    container = build_service_container(datasource, settings=settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot(
            schema_name=schema,
            sample_size=resolved_sample_size,
        )
        path = container.snapshotter.save_snapshot(bundle)
    finally:
        container.close()

    typer.echo(str(path))


@app.command("show")
def show(path: str) -> None:
    """Load and print a snapshot bundle.

    Args:
        path: Snapshot file path.
    """

    bundle = SnapshotService.load_snapshot(Path(path))
    typer.echo(bundle.model_dump_json(indent=2))


@app.command("list")
def list_snapshots(
    datasource: Annotated[str | None, typer.Argument()] = None,
    schema: Annotated[str | None, typer.Argument()] = None,
) -> None:
    """List saved snapshot inventory entries.

    Args:
        datasource: Optional datasource identifier filter.
        schema: Optional schema name filter.
    """

    settings = load_settings()
    resolved_datasource = (
        None if datasource is None else settings.resolve_datasource_name(datasource)
    )
    entries = SnapshotService.list_saved_snapshots(
        settings.artifacts,
        datasource_name=resolved_datasource,
        schema_name=schema,
    )
    typer.echo(
        orjson.dumps(
            [entry.model_dump(mode="json") for entry in entries],
            option=orjson.OPT_INDENT_2,
        ).decode()
    )


@app.command("latest")
def latest(datasource: str, schema: str) -> None:
    """Load and print the newest saved snapshot for a datasource/schema pair.

    Args:
        datasource: Datasource identifier.
        schema: Schema name.
    """

    settings = load_settings()
    resolved_datasource = settings.resolve_datasource_name(datasource)
    bundle = SnapshotService.load_latest_snapshot(
        settings.artifacts,
        datasource_name=resolved_datasource,
        schema_name=schema,
    )
    typer.echo(bundle.model_dump_json(indent=2))


@app.command("diff")
def diff(left_path: str, right_path: str) -> None:
    """Diff two persisted snapshot bundles.

    Args:
        left_path: Baseline snapshot file path.
        right_path: Comparison snapshot file path.
    """

    left_bundle = SnapshotService.load_snapshot(Path(left_path))
    right_bundle = SnapshotService.load_snapshot(Path(right_path))
    result = SnapshotService.diff_snapshots(left_bundle, right_bundle)
    typer.echo(result.model_dump_json(indent=2))


@app.command("regenerate")
def regenerate(path: str) -> None:
    """Regenerate a snapshot from its embedded request metadata.

    Args:
        path: Existing snapshot file path.
    """

    existing = SnapshotBundleModel.model_validate(orjson.loads(Path(path).read_bytes()))
    container = build_service_container(existing.regenerate.datasource_name)
    try:
        bundle = container.snapshotter.create_schema_snapshot(
            schema_name=existing.regenerate.schema_name,
            sample_size=existing.regenerate.sample_size,
        )
        output_path = container.snapshotter.save_snapshot(bundle)
    finally:
        container.close()

    typer.echo(str(output_path))
