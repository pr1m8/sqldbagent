"""Schema diagram bundle models."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class SchemaGraphNodeModel(BaseModel):
    """One node in the exported schema graph.

    Attributes:
        node_id: Stable node identifier.
        label: Human-readable label for the node.
        kind: Graph node kind such as table or view.
        schema_name: Optional schema containing the object.
        object_name: Unqualified database object name.
        summary: Optional human-readable summary for the object.
        metadata: Additional machine-readable node metadata.
    """

    node_id: str
    label: str
    kind: str
    schema_name: str | None = None
    object_name: str
    summary: str | None = None
    metadata: dict[str, object | None] = Field(default_factory=dict)


class SchemaGraphEdgeModel(BaseModel):
    """One relationship edge in the exported schema graph.

    Attributes:
        source_node_id: Source node identifier.
        target_node_id: Target node identifier.
        relationship_type: Relationship kind.
        label: Human-readable edge label.
        source_columns: Source column names.
        target_columns: Target column names.
        constraint_name: Optional database constraint name.
        summary: Optional human-readable summary.
    """

    source_node_id: str
    target_node_id: str
    relationship_type: str = "foreign_key"
    label: str | None = None
    source_columns: list[str] = Field(default_factory=list)
    target_columns: list[str] = Field(default_factory=list)
    constraint_name: str | None = None
    summary: str | None = None


class SchemaGraphModel(BaseModel):
    """Graph JSON representation for a schema snapshot.

    Attributes:
        nodes: Graph nodes.
        edges: Graph edges.
    """

    nodes: list[SchemaGraphNodeModel] = Field(default_factory=list)
    edges: list[SchemaGraphEdgeModel] = Field(default_factory=list)


class DiagramBundleModel(BaseModel):
    """Persisted schema diagram bundle.

    Attributes:
        snapshot_id: Source snapshot identifier.
        created_at: Diagram creation timestamp.
        datasource_name: Datasource identifier.
        schema_name: Schema represented by the diagram.
        mermaid_erd: Mermaid ER diagram text.
        graph: Graph JSON payload.
        content_hash: Deterministic bundle hash.
        summary: Human-readable summary for downstream tools and docs.
    """

    snapshot_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    datasource_name: str
    schema_name: str
    mermaid_erd: str
    graph: SchemaGraphModel
    content_hash: str | None = None
    summary: str | None = None
