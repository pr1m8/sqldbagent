"""Snapshot document export services."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import orjson

from sqldbagent.adapters.shared import require_dependency
from sqldbagent.core.config import ArtifactSettings
from sqldbagent.core.models.catalog import RelationshipEdgeModel, TableModel, ViewModel
from sqldbagent.core.models.profile import TableProfileModel
from sqldbagent.docs.models import DocumentBundleModel, ExportedDocumentModel
from sqldbagent.snapshot.models import SnapshotBundleModel


class SnapshotDocumentService:
    """Export snapshot bundles into retrieval-ready documents."""

    def __init__(self, *, artifacts: ArtifactSettings) -> None:
        """Initialize the document exporter.

        Args:
            artifacts: Artifact directory settings.
        """

        self._artifacts = artifacts

    def create_document_bundle(
        self,
        snapshot: SnapshotBundleModel,
    ) -> DocumentBundleModel:
        """Build a persisted document bundle for one snapshot.

        Args:
            snapshot: Snapshot bundle to export.

        Returns:
            DocumentBundleModel: Retrieval-ready document bundle.
        """

        profiles = {
            self._qualify_name(profile.schema_name, profile.table_name): profile
            for profile in snapshot.profiles
        }
        documents: list[ExportedDocumentModel] = [
            self._schema_overview_document(snapshot),
            *[
                self._table_document(
                    snapshot=snapshot,
                    table=table,
                    profile=profiles.get(
                        self._qualify_name(table.schema_name, table.name)
                    ),
                )
                for table in snapshot.schema_metadata.tables
            ],
            *[
                self._view_document(snapshot=snapshot, view=view)
                for view in snapshot.schema_metadata.views
            ],
            *[
                self._relationship_document(snapshot=snapshot, edge=edge)
                for edge in snapshot.relationship_edges
            ],
        ]
        bundle = DocumentBundleModel(
            snapshot_id=snapshot.snapshot_id,
            datasource_name=snapshot.datasource_name,
            schema_name=snapshot.regenerate.schema_name,
            documents=documents,
        )
        content_hash = self._hash_bundle(bundle)
        return bundle.model_copy(
            update={
                "content_hash": content_hash,
                "summary": (
                    f"Document bundle for datasource '{snapshot.datasource_name}' "
                    f"schema '{snapshot.regenerate.schema_name}' with "
                    f"{len(documents)} retrieval documents."
                ),
            }
        )

    def save_document_bundle(self, bundle: DocumentBundleModel) -> Path:
        """Persist one document bundle to disk.

        Args:
            bundle: Document bundle to persist.

        Returns:
            Path: Saved document-bundle path.
        """

        path = self.document_path(
            datasource_name=bundle.datasource_name,
            schema_name=bundle.schema_name,
            snapshot_id=bundle.snapshot_id,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            orjson.dumps(
                bundle.model_dump(mode="json"),
                option=orjson.OPT_INDENT_2,
            )
        )
        return path

    @staticmethod
    def load_document_bundle(path: str | Path) -> DocumentBundleModel:
        """Load a saved document bundle from disk.

        Args:
            path: Bundle path to load.

        Returns:
            DocumentBundleModel: Parsed document bundle.
        """

        return DocumentBundleModel.model_validate(orjson.loads(Path(path).read_bytes()))

    def export_langchain_documents(self, bundle: DocumentBundleModel) -> list[Any]:
        """Convert a stored bundle into LangChain `Document` instances.

        Args:
            bundle: Stored bundle to convert.

        Returns:
            list[Any]: LangChain `Document` instances.
        """

        documents_module = require_dependency("langchain_core.documents", "langchain")
        document_class = documents_module.Document
        return [
            document_class(
                id=document.document_id,
                page_content=document.page_content,
                metadata=document.metadata,
            )
            for document in bundle.documents
        ]

    def document_path(
        self,
        *,
        datasource_name: str,
        schema_name: str,
        snapshot_id: str,
    ) -> Path:
        """Return the bundle path for one snapshot export.

        Args:
            datasource_name: Datasource identifier.
            schema_name: Schema name.
            snapshot_id: Snapshot identifier.

        Returns:
            Path: Bundle path beneath the configured document root.
        """

        return self.document_dir / datasource_name / schema_name / f"{snapshot_id}.json"

    @property
    def document_dir(self) -> Path:
        """Return the configured document-export root directory."""

        return Path(self._artifacts.root_dir) / self._artifacts.documents_dir

    def _schema_overview_document(
        self, snapshot: SnapshotBundleModel
    ) -> ExportedDocumentModel:
        """Render a schema overview document."""

        schema = snapshot.schema_metadata
        table_names = ", ".join(table.name for table in schema.tables) or "none"
        view_names = ", ".join(view.name for view in schema.views) or "none"
        relationship_summaries = [
            edge.summary
            or (
                f"{self._qualify_name(edge.source_schema, edge.source_table)} -> "
                f"{self._qualify_name(edge.target_schema, edge.target_table)}"
            )
            for edge in snapshot.relationship_edges
        ]
        page_content = "\n".join(
            [
                f"Schema Overview: {schema.name}",
                f"Datasource: {snapshot.datasource_name}",
                f"Snapshot ID: {snapshot.snapshot_id}",
                f"Schema summary: {schema.summary or 'No schema summary available.'}",
                f"Tables: {table_names}",
                f"Views: {view_names}",
                "Relationships:",
                *[
                    f"- {relationship}"
                    for relationship in (
                        relationship_summaries
                        or ["No foreign-key relationships were captured."]
                    )
                ],
            ]
        )
        return ExportedDocumentModel(
            document_id=self._document_id(
                snapshot.snapshot_id,
                "schema_overview",
                schema.name,
            ),
            page_content=page_content,
            metadata={
                "datasource_name": snapshot.datasource_name,
                "schema_name": schema.name,
                "snapshot_id": snapshot.snapshot_id,
                "artifact_type": "schema_overview",
            },
            summary=f"Schema overview for '{schema.name}'.",
        )

    def _table_document(
        self,
        *,
        snapshot: SnapshotBundleModel,
        table: TableModel,
        profile: TableProfileModel | None,
    ) -> ExportedDocumentModel:
        """Render one table document."""

        column_lines = [
            (
                f"- {column.name}: {column.data_type}; "
                f"nullable={column.nullable}; "
                f"default={column.default or 'none'}; "
                f"description={column.description or 'none'}"
            )
            for column in table.columns
        ]
        index_lines = [
            f"- {index.name or 'unnamed'} on {', '.join(index.columns) or 'no columns'}; "
            f"unique={index.unique}"
            for index in table.indexes
        ]
        unique_lines = [
            f"- {constraint.name or 'unnamed'} on {', '.join(constraint.columns)}"
            for constraint in table.unique_constraints
        ]
        foreign_key_lines = [
            f"- {foreign_key.summary or 'Foreign key without summary.'}"
            for foreign_key in table.foreign_keys
        ]
        profile_lines = (
            [
                f"Entity classification: {profile.entity_kind or 'unknown'}",
                f"Row count: {profile.row_count if profile.row_count is not None else 'unknown'}",
                f"Relationship count: {profile.relationship_count}",
                (
                    "Storage: "
                    f"{profile.storage_bytes if profile.storage_bytes is not None else 'unknown'} "
                    f"bytes ({profile.storage_scope or 'unknown scope'})"
                ),
                (
                    "Column profile highlights: "
                    + "; ".join(
                        column.summary or f"{column.name} has no summary."
                        for column in profile.columns
                    )
                ),
                (
                    "Sample rows: "
                    + (
                        orjson.dumps(profile.sample_rows[:3]).decode("utf-8")
                        if profile.sample_rows
                        else "none"
                    )
                ),
            ]
            if profile is not None
            else ["No profile was stored for this table."]
        )
        page_content = "\n".join(
            [
                f"Table: {self._qualify_name(table.schema_name, table.name)}",
                f"Datasource: {snapshot.datasource_name}",
                f"Snapshot ID: {snapshot.snapshot_id}",
                f"Table summary: {table.summary or 'No table summary available.'}",
                f"Description: {table.description or 'none'}",
                (
                    "Primary key: "
                    + (", ".join(table.primary_key) if table.primary_key else "none")
                ),
                "Columns:",
                *(column_lines or ["- No columns were captured."]),
                "Indexes:",
                *(index_lines or ["- No indexes were captured."]),
                "Unique constraints:",
                *(unique_lines or ["- No unique constraints were captured."]),
                "Foreign keys:",
                *(foreign_key_lines or ["- No foreign keys were captured."]),
                "Profile:",
                *profile_lines,
            ]
        )
        metadata = {
            "datasource_name": snapshot.datasource_name,
            "schema_name": table.schema_name,
            "table_name": table.name,
            "snapshot_id": snapshot.snapshot_id,
            "artifact_type": "table",
            "primary_key": table.primary_key,
        }
        if profile is not None and profile.entity_kind is not None:
            metadata["entity_kind"] = profile.entity_kind
        return ExportedDocumentModel(
            document_id=self._document_id(snapshot.snapshot_id, "table", table.name),
            page_content=page_content,
            metadata=metadata,
            summary=table.summary or f"Table document for '{table.name}'.",
        )

    def _view_document(
        self,
        *,
        snapshot: SnapshotBundleModel,
        view: ViewModel,
    ) -> ExportedDocumentModel:
        """Render one view document."""

        column_lines = [
            (
                f"- {column.name}: {column.data_type}; "
                f"nullable={column.nullable}; "
                f"description={column.description or 'none'}"
            )
            for column in view.columns
        ]
        page_content = "\n".join(
            [
                f"View: {self._qualify_name(view.schema_name, view.name)}",
                f"Datasource: {snapshot.datasource_name}",
                f"Snapshot ID: {snapshot.snapshot_id}",
                f"View summary: {view.summary or 'No view summary available.'}",
                "Columns:",
                *(column_lines or ["- No columns were captured."]),
                f"Definition: {view.definition or 'definition unavailable'}",
            ]
        )
        return ExportedDocumentModel(
            document_id=self._document_id(snapshot.snapshot_id, "view", view.name),
            page_content=page_content,
            metadata={
                "datasource_name": snapshot.datasource_name,
                "schema_name": view.schema_name,
                "view_name": view.name,
                "snapshot_id": snapshot.snapshot_id,
                "artifact_type": "view",
            },
            summary=view.summary or f"View document for '{view.name}'.",
        )

    def _relationship_document(
        self,
        *,
        snapshot: SnapshotBundleModel,
        edge: RelationshipEdgeModel,
    ) -> ExportedDocumentModel:
        """Render one relationship document."""

        source_name = self._qualify_name(edge.source_schema, edge.source_table)
        target_name = self._qualify_name(edge.target_schema, edge.target_table)
        summary = edge.summary or (
            f"{source_name} references {target_name} through "
            f"{', '.join(edge.source_columns) or 'unknown columns'}."
        )
        page_content = "\n".join(
            [
                f"Relationship: {source_name} -> {target_name}",
                f"Datasource: {snapshot.datasource_name}",
                f"Snapshot ID: {snapshot.snapshot_id}",
                f"Summary: {summary}",
                f"Source columns: {', '.join(edge.source_columns) or 'none'}",
                f"Target columns: {', '.join(edge.target_columns) or 'none'}",
                f"Constraint name: {edge.constraint_name or 'unnamed'}",
            ]
        )
        return ExportedDocumentModel(
            document_id=self._document_id(
                snapshot.snapshot_id,
                "relationship",
                f"{edge.source_table}:{edge.target_table}",
            ),
            page_content=page_content,
            metadata={
                "datasource_name": snapshot.datasource_name,
                "schema_name": edge.source_schema,
                "source_table": edge.source_table,
                "target_table": edge.target_table,
                "snapshot_id": snapshot.snapshot_id,
                "artifact_type": "relationship",
            },
            summary=summary,
        )

    @staticmethod
    def _qualify_name(schema_name: str | None, object_name: str) -> str:
        """Return a qualified object name."""

        if schema_name is None:
            return object_name
        return f"{schema_name}.{object_name}"

    @staticmethod
    def _document_id(snapshot_id: str, artifact_type: str, object_name: str) -> str:
        """Build a stable document identifier."""

        return str(uuid5(NAMESPACE_URL, f"{snapshot_id}:{artifact_type}:{object_name}"))

    @staticmethod
    def _hash_bundle(bundle: DocumentBundleModel) -> str:
        """Return a deterministic content hash for one document bundle."""

        payload = bundle.model_dump(
            mode="json",
            exclude={"created_at", "content_hash", "summary"},
        )
        return sha256(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)).hexdigest()
