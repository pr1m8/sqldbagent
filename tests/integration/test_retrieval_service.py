"""Retrieval service integration tests."""

from __future__ import annotations

import pytest

from sqldbagent.core.bootstrap import build_service_container


@pytest.mark.integration
@pytest.mark.enable_socket
def test_retrieval_service_indexes_and_queries_live_qdrant(
    live_postgres_settings,
    live_postgres_schema: str,
    live_qdrant_settings,
) -> None:
    """Index a live Postgres snapshot into Qdrant and retrieve schema context."""

    del live_qdrant_settings
    settings = live_postgres_settings.model_copy(
        update={
            "embeddings": live_postgres_settings.embeddings.model_copy(
                update={"provider": "hash", "dimensions": 64}
            )
        }
    )
    container = build_service_container("postgres", settings=settings)
    try:
        bundle = container.snapshotter.create_schema_snapshot(
            live_postgres_schema,
            sample_size=1,
        )
        container.snapshotter.save_snapshot(bundle)
        manifest = container.retrieval_service.index_snapshot_bundle(
            bundle,
            recreate_collection=True,
        )
        result = container.retrieval_service.retrieve(
            "Which table stores user email addresses?",
            schema_name=live_postgres_schema,
            limit=4,
        )
    finally:
        container.close()

    if manifest.document_count <= 0:
        raise AssertionError(manifest)
    if not result.documents:
        raise AssertionError(result)
    if not any(
        document.metadata.get("table_name") == "users" for document in result.documents
    ):
        raise AssertionError(result.documents)
