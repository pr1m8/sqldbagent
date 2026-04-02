"""Document export tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from sqldbagent.core.config import ArtifactSettings
from sqldbagent.docs.service import SnapshotDocumentService
from sqldbagent.introspect.service import SQLAlchemyInspectionService
from sqldbagent.profile.service import SQLAlchemyProfilingService
from sqldbagent.snapshot.service import SnapshotService


def test_snapshot_document_service_exports_and_saves_bundle(tmp_path: Path) -> None:
    """Export a snapshot into retrieval-ready documents and persist them."""

    database_path = tmp_path / "documents.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL, status TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, email, status) VALUES "
                "(1, 'a@example.com', 'active'),"
                "(2, 'b@example.com', 'inactive')"
            )
        )

    artifacts = ArtifactSettings(
        root_dir=str(tmp_path),
        snapshots_dir="snapshots",
        documents_dir="documents",
    )
    inspector = SQLAlchemyInspectionService(engine)
    profiler = SQLAlchemyProfilingService(engine=engine, inspector=inspector)
    snapshotter = SnapshotService(
        datasource_name="sqlite",
        inspector=inspector,
        profiler=profiler,
        artifacts=artifacts,
    )
    document_service = SnapshotDocumentService(artifacts=artifacts)

    snapshot = snapshotter.create_schema_snapshot("main", sample_size=1)
    bundle = document_service.create_document_bundle(snapshot)
    path = document_service.save_document_bundle(bundle)
    loaded = SnapshotDocumentService.load_document_bundle(path)
    engine.dispose()

    if not path.exists():
        raise AssertionError(path)
    if len(bundle.documents) < 2:
        raise AssertionError(bundle)
    if "Schema Overview: main" not in bundle.documents[0].page_content:
        raise AssertionError(bundle.documents[0])
    if not any(
        document.metadata.get("table_name") == "users" for document in bundle.documents
    ):
        raise AssertionError(bundle.documents)
    if loaded.content_hash != bundle.content_hash:
        raise AssertionError(loaded)
