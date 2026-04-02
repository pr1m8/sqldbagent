"""Retrieval and vector-index models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class RetrievedDocumentModel(BaseModel):
    """One retrieved document returned from the vector store.

    Attributes:
        document_id: Stable document identifier.
        page_content: Retrieved page content.
        metadata: Filterable metadata associated with the document.
        score: Optional similarity score.
        summary: Short result summary.
    """

    document_id: str
    page_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None
    summary: str | None = None


class RetrievalIndexManifestModel(BaseModel):
    """Persisted manifest for one vector-indexing pass.

    Attributes:
        datasource_name: Datasource identifier.
        schema_name: Indexed schema name.
        snapshot_id: Snapshot identifier that was indexed.
        collection_name: Target Qdrant collection name.
        document_bundle_path: Saved document-bundle path.
        document_count: Number of indexed documents.
        embedding_provider: Embedding provider used to build vectors.
        embedding_model: Embedding model or hash backend name.
        created_at: Manifest creation timestamp.
        summary: Short index summary.
    """

    datasource_name: str
    schema_name: str
    snapshot_id: str
    collection_name: str
    document_bundle_path: str
    document_count: int
    embedding_provider: str
    embedding_model: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    summary: str | None = None


class RetrievalResultModel(BaseModel):
    """Retrieval query result.

    Attributes:
        query: User or agent retrieval query.
        datasource_name: Datasource identifier bound to the service.
        schema_name: Optional schema filter.
        table_name: Optional table filter.
        snapshot_id: Optional snapshot filter.
        collection_name: Qdrant collection that served the search.
        documents: Retrieved documents.
        summary: Short retrieval summary.
    """

    query: str
    datasource_name: str
    schema_name: str | None = None
    table_name: str | None = None
    snapshot_id: str | None = None
    collection_name: str
    documents: list[RetrievedDocumentModel] = Field(default_factory=list)
    summary: str | None = None
