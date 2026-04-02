"""Document export CLI commands."""

from __future__ import annotations

from pathlib import Path

import orjson

from sqldbagent.cli._typer import load_typer
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.docs.service import SnapshotDocumentService
from sqldbagent.snapshot.service import SnapshotService

typer = load_typer()
app = typer.Typer(help="Document export commands.")


@app.command("export")
def export(datasource: str, schema: str) -> None:
    """Export retrieval-ready documents from the latest saved schema snapshot.

    Args:
        datasource: Datasource identifier.
        schema: Schema name whose latest saved snapshot should be exported.
    """

    container = build_service_container(datasource)
    try:
        bundle = container.snapshotter.load_latest_saved_snapshot(schema)
        document_bundle = container.document_service.create_document_bundle(bundle)
        path = container.document_service.save_document_bundle(document_bundle)
    finally:
        container.close()

    typer.echo(str(path))


@app.command("show")
def show(path: str) -> None:
    """Load and print a saved document bundle.

    Args:
        path: Document-bundle path.
    """

    bundle = SnapshotDocumentService.load_document_bundle(Path(path))
    typer.echo(
        orjson.dumps(
            bundle.model_dump(mode="json"),
            option=orjson.OPT_INDENT_2,
        ).decode()
    )


@app.command("export-from-snapshot")
def export_from_snapshot(path: str) -> None:
    """Export retrieval-ready documents from a specific snapshot path.

    Args:
        path: Snapshot path to export from.
    """

    snapshot = SnapshotService.load_snapshot(Path(path))
    container = build_service_container(snapshot.datasource_name)
    try:
        document_bundle = container.document_service.create_document_bundle(snapshot)
        output_path = container.document_service.save_document_bundle(document_bundle)
    finally:
        container.close()

    typer.echo(str(output_path))
