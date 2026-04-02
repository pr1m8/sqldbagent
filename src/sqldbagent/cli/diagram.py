"""Diagram CLI commands."""

from __future__ import annotations

from pathlib import Path

import orjson

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.diagrams.service import SchemaDiagramService
from sqldbagent.snapshot.service import SnapshotService

typer = load_typer()
app = typer.Typer(help="Schema diagram commands.")


@app.command("schema")
def schema(datasource: str, schema_name: str) -> None:
    """Generate diagram artifacts from the latest saved schema snapshot.

    Args:
        datasource: Datasource identifier.
        schema_name: Schema name whose latest saved snapshot should be visualized.
    """

    container = build_service_container(datasource)
    try:
        snapshot = container.snapshotter.load_latest_saved_snapshot(schema_name)
        diagram_bundle = container.diagram_service.create_diagram_bundle(snapshot)
        path = container.diagram_service.save_diagram_bundle(diagram_bundle)
        payload = diagram_bundle.model_dump(mode="json")
        payload["path"] = path.as_posix()
        payload["mermaid_path"] = container.diagram_service.mermaid_path(
            datasource_name=diagram_bundle.datasource_name,
            schema_name=diagram_bundle.schema_name,
            snapshot_id=diagram_bundle.snapshot_id,
        ).as_posix()
        payload["graph_path"] = container.diagram_service.graph_path(
            datasource_name=diagram_bundle.datasource_name,
            schema_name=diagram_bundle.schema_name,
            snapshot_id=diagram_bundle.snapshot_id,
        ).as_posix()
    finally:
        container.close()

    typer.echo(orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode())


@app.command("show")
def show(path: str) -> None:
    """Load and print a saved diagram bundle.

    Args:
        path: Diagram-bundle path.
    """

    bundle = SchemaDiagramService.load_diagram_bundle(Path(path))
    typer.echo(
        orjson.dumps(
            bundle.model_dump(mode="json"), option=orjson.OPT_INDENT_2
        ).decode()
    )


@app.command("from-snapshot")
def from_snapshot(path: str) -> None:
    """Generate diagram artifacts from a specific saved snapshot path.

    Args:
        path: Snapshot path to visualize.
    """

    snapshot = SnapshotService.load_snapshot(Path(path))
    container = build_service_container(snapshot.datasource_name)
    try:
        diagram_bundle = container.diagram_service.create_diagram_bundle(snapshot)
        output_path = container.diagram_service.save_diagram_bundle(diagram_bundle)
        payload = diagram_bundle.model_dump(mode="json")
        payload["path"] = output_path.as_posix()
        payload["mermaid_path"] = container.diagram_service.mermaid_path(
            datasource_name=diagram_bundle.datasource_name,
            schema_name=diagram_bundle.schema_name,
            snapshot_id=diagram_bundle.snapshot_id,
        ).as_posix()
        payload["graph_path"] = container.diagram_service.graph_path(
            datasource_name=diagram_bundle.datasource_name,
            schema_name=diagram_bundle.schema_name,
            snapshot_id=diagram_bundle.snapshot_id,
        ).as_posix()
    finally:
        container.close()

    typer.echo(orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode())
