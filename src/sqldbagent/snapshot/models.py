"""Snapshot bundle models."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from sqldbagent.core.models.catalog import RelationshipEdgeModel, SchemaModel
from sqldbagent.core.models.profile import TableProfileModel


class SnapshotRequestModel(BaseModel):
    """Snapshot regeneration request.

    Attributes:
        datasource_name: Datasource identifier.
        schema_name: Schema name captured by the snapshot.
        sample_size: Sample size used for table profiling.
    """

    datasource_name: str
    schema_name: str
    sample_size: int = 5


class SnapshotBundleModel(BaseModel):
    """Normalized persisted snapshot bundle.

    Attributes:
        snapshot_id: Stable snapshot identifier.
        format_version: Snapshot format version.
        created_at: Snapshot creation timestamp.
        datasource_name: Datasource identifier.
        schema_metadata: Normalized schema metadata.
        relationship_edges: Relationship graph edges derived from foreign keys.
        profiles: Per-table profiles captured with the snapshot.
        content_hash: Deterministic content hash for deduplication and drift detection.
        summary: Generated short summary.
        regenerate: Request payload that can rebuild the snapshot later.
    """

    snapshot_id: str = Field(default_factory=lambda: str(uuid4()))
    format_version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    datasource_name: str
    schema_metadata: SchemaModel
    relationship_edges: list[RelationshipEdgeModel] = Field(default_factory=list)
    profiles: list[TableProfileModel] = Field(default_factory=list)
    content_hash: str | None = None
    summary: str | None = None
    regenerate: SnapshotRequestModel


class SnapshotInventoryEntryModel(BaseModel):
    """Stored snapshot inventory entry.

    Attributes:
        datasource_name: Datasource identifier.
        schema_name: Captured schema name.
        snapshot_id: Snapshot identifier.
        created_at: Snapshot creation timestamp.
        content_hash: Snapshot content hash.
        path: Relative snapshot path under the snapshot root.
        summary: Summary context for the stored snapshot.
    """

    datasource_name: str
    schema_name: str
    snapshot_id: str
    created_at: datetime
    content_hash: str | None = None
    path: str
    summary: str | None = None


class TableDiffModel(BaseModel):
    """Per-table snapshot diff details.

    Attributes:
        table_name: Qualified or unqualified table name.
        added_columns: Columns present only in the right snapshot.
        removed_columns: Columns present only in the left snapshot.
        changed_columns: Columns present in both snapshots but with changed metadata.
        metadata_changed: Whether non-column metadata changed.
        profile_changed: Whether the normalized table profile changed.
        summary: Generated short summary.
    """

    table_name: str
    added_columns: list[str] = Field(default_factory=list)
    removed_columns: list[str] = Field(default_factory=list)
    changed_columns: list[str] = Field(default_factory=list)
    metadata_changed: bool = False
    profile_changed: bool = False
    summary: str | None = None


class SnapshotDiffModel(BaseModel):
    """High-level diff between two snapshot bundles.

    Attributes:
        left_snapshot_id: Baseline snapshot identifier.
        right_snapshot_id: Comparison snapshot identifier.
        left_content_hash: Baseline content hash.
        right_content_hash: Comparison content hash.
        added_tables: Tables added in the right snapshot.
        removed_tables: Tables removed from the right snapshot.
        changed_tables: Tables present in both snapshots with metadata changes.
        added_views: Views added in the right snapshot.
        removed_views: Views removed from the right snapshot.
        added_relationships: Relationships added in the right snapshot.
        removed_relationships: Relationships removed from the right snapshot.
        summary: Generated short summary.
    """

    left_snapshot_id: str
    right_snapshot_id: str
    left_content_hash: str | None = None
    right_content_hash: str | None = None
    added_tables: list[str] = Field(default_factory=list)
    removed_tables: list[str] = Field(default_factory=list)
    changed_tables: list[TableDiffModel] = Field(default_factory=list)
    added_views: list[str] = Field(default_factory=list)
    removed_views: list[str] = Field(default_factory=list)
    added_relationships: list[str] = Field(default_factory=list)
    removed_relationships: list[str] = Field(default_factory=list)
    summary: str | None = None
