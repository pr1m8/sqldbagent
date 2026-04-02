"""Document export models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ExportedDocumentModel(BaseModel):
    """Stored retrieval document.

    Attributes:
        document_id: Stable document identifier.
        page_content: Human-readable page content.
        metadata: Filterable metadata for retrieval and export.
        summary: Short summary of the document payload.
    """

    document_id: str
    page_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None


class DocumentBundleModel(BaseModel):
    """Persisted bundle of retrieval documents.

    Attributes:
        snapshot_id: Snapshot identifier that produced the documents.
        datasource_name: Datasource identifier.
        schema_name: Schema captured by the export.
        created_at: Export creation timestamp.
        content_hash: Deterministic content hash for the bundle.
        documents: Retrieval documents derived from the snapshot.
        summary: Short summary of the export bundle.
    """

    snapshot_id: str
    datasource_name: str
    schema_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_hash: str | None = None
    documents: list[ExportedDocumentModel] = Field(default_factory=list)
    summary: str | None = None
