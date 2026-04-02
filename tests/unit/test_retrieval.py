"""Retrieval service tests."""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient
from sqlalchemy import create_engine, text

from sqldbagent.core.config import (
    ArtifactSettings,
    EmbeddingSettings,
    LLMSettings,
    RetrievalSettings,
)
from sqldbagent.docs.service import SnapshotDocumentService
from sqldbagent.introspect.service import SQLAlchemyInspectionService
from sqldbagent.profile.service import SQLAlchemyProfilingService
from sqldbagent.retrieval.service import SnapshotRetrievalService
from sqldbagent.snapshot.service import SnapshotService


def test_retrieval_service_indexes_and_queries_snapshot_documents(
    tmp_path: Path,
) -> None:
    """Index snapshot documents into local Qdrant mode and retrieve them."""

    database_path = tmp_path / "retrieval.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL, team_id INTEGER)"
            )
        )
        connection.execute(
            text("CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        )
        connection.execute(
            text(
                "INSERT INTO users (id, email, team_id) VALUES "
                "(1, 'a@example.com', 1),"
                "(2, 'b@example.com', 1)"
            )
        )
        connection.execute(text("INSERT INTO teams (id, name) VALUES (1, 'data')"))

    artifacts = ArtifactSettings(
        root_dir=str(tmp_path),
        snapshots_dir="snapshots",
        documents_dir="documents",
        vectorstores_dir="vectorstores",
        embeddings_cache_dir="embeddings-cache",
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
    retrieval_service = SnapshotRetrievalService(
        datasource_name="sqlite",
        snapshotter=snapshotter,
        document_service=document_service,
        artifacts=artifacts,
        embeddings_settings=EmbeddingSettings(provider="hash", dimensions=64),
        llm_settings=LLMSettings(),
        retrieval_settings=RetrievalSettings(qdrant_url="http://127.0.0.1:6333"),
        client=QdrantClient(location=":memory:"),
    )

    snapshot = snapshotter.create_schema_snapshot("main", sample_size=1)
    manifest = retrieval_service.index_snapshot_bundle(
        snapshot, recreate_collection=True
    )
    result = retrieval_service.retrieve(
        "Which table stores user email addresses?",
        schema_name="main",
        limit=3,
    )
    engine.dispose()

    if manifest.document_count < 2:
        raise AssertionError(manifest)
    if not result.documents:
        raise AssertionError(result)
    if not any(
        document.metadata.get("table_name") == "users" for document in result.documents
    ):
        raise AssertionError(result.documents)


def test_retrieval_service_auto_indexes_latest_snapshot_on_first_query(
    tmp_path: Path,
) -> None:
    """Bootstrap retrieval documents automatically when a snapshot exists."""

    database_path = tmp_path / "retrieval-auto-index.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL, team_id INTEGER)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, email, team_id) VALUES (1, 'a@example.com', 1)"
            )
        )

    artifacts = ArtifactSettings(
        root_dir=str(tmp_path),
        snapshots_dir="snapshots",
        documents_dir="documents",
        vectorstores_dir="vectorstores",
        embeddings_cache_dir="embeddings-cache",
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
    retrieval_service = SnapshotRetrievalService(
        datasource_name="sqlite",
        snapshotter=snapshotter,
        document_service=document_service,
        artifacts=artifacts,
        embeddings_settings=EmbeddingSettings(provider="hash", dimensions=64),
        llm_settings=LLMSettings(),
        retrieval_settings=RetrievalSettings(qdrant_url="http://127.0.0.1:6333"),
        client=QdrantClient(location=":memory:"),
    )

    snapshot = snapshotter.create_schema_snapshot("main", sample_size=1)
    snapshotter.save_snapshot(snapshot)
    result = retrieval_service.retrieve(
        "Which table stores email addresses?",
        schema_name="main",
        snapshot_id=snapshot.snapshot_id,
        limit=3,
    )
    engine.dispose()

    if not result.documents:
        raise AssertionError(result)
    if "Auto-indexed snapshot documents." not in (result.summary or ""):
        raise AssertionError(result.summary)


def test_retrieval_service_detects_exists_conflicts() -> None:
    """Recognize duplicate-create conflicts from Qdrant responses."""

    conflict = RuntimeError(
        "Unexpected Response: 409 (Conflict) Raw response content: already exists"
    )
    other = RuntimeError("connection refused")

    if (
        SnapshotRetrievalService._is_qdrant_exists_conflict(conflict) is not True
    ):  # noqa: SLF001
        raise AssertionError(conflict)
    if (
        SnapshotRetrievalService._is_qdrant_exists_conflict(other) is not False
    ):  # noqa: SLF001
        raise AssertionError(other)
