"""Schema diagram export services."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import orjson

from sqldbagent.core.config import ArtifactSettings
from sqldbagent.core.models.catalog import RelationshipEdgeModel, TableModel
from sqldbagent.core.models.profile import TableProfileModel
from sqldbagent.diagrams.models import (
    DiagramBundleModel,
    SchemaGraphEdgeModel,
    SchemaGraphModel,
    SchemaGraphNodeModel,
)
from sqldbagent.snapshot.models import SnapshotBundleModel


class SchemaDiagramService:
    """Generate Mermaid and graph artifacts from stored schema snapshots."""

    def __init__(self, *, artifacts: ArtifactSettings) -> None:
        """Initialize the diagram exporter.

        Args:
            artifacts: Artifact directory settings.
        """

        self._artifacts = artifacts

    def create_diagram_bundle(
        self, snapshot: SnapshotBundleModel
    ) -> DiagramBundleModel:
        """Build Mermaid and graph artifacts for one snapshot.

        Args:
            snapshot: Snapshot bundle to visualize.

        Returns:
            DiagramBundleModel: Diagram bundle for the snapshot.
        """

        profiles = {
            self._qualify_name(profile.schema_name, profile.table_name): profile
            for profile in snapshot.profiles
        }
        graph = self._build_graph(snapshot=snapshot, profiles=profiles)
        bundle = DiagramBundleModel(
            snapshot_id=snapshot.snapshot_id,
            datasource_name=snapshot.datasource_name,
            schema_name=snapshot.regenerate.schema_name,
            mermaid_erd=self._build_mermaid(snapshot=snapshot, profiles=profiles),
            graph=graph,
        )
        content_hash = self._hash_bundle(bundle)
        return bundle.model_copy(
            update={
                "content_hash": content_hash,
                "summary": (
                    f"Diagram bundle for datasource '{snapshot.datasource_name}' "
                    f"schema '{snapshot.regenerate.schema_name}' with "
                    f"{len(graph.nodes)} graph nodes and {len(graph.edges)} edges."
                ),
            }
        )

    def save_diagram_bundle(self, bundle: DiagramBundleModel) -> Path:
        """Persist a diagram bundle and companion Mermaid and graph files.

        Args:
            bundle: Diagram bundle to persist.

        Returns:
            Path: Saved bundle path.
        """

        bundle_path = self.bundle_path(
            datasource_name=bundle.datasource_name,
            schema_name=bundle.schema_name,
            snapshot_id=bundle.snapshot_id,
        )
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_bytes(
            orjson.dumps(
                bundle.model_dump(mode="json"),
                option=orjson.OPT_INDENT_2,
            )
        )
        self.mermaid_path(
            datasource_name=bundle.datasource_name,
            schema_name=bundle.schema_name,
            snapshot_id=bundle.snapshot_id,
        ).write_text(bundle.mermaid_erd, encoding="utf-8")
        self.graph_path(
            datasource_name=bundle.datasource_name,
            schema_name=bundle.schema_name,
            snapshot_id=bundle.snapshot_id,
        ).write_bytes(
            orjson.dumps(
                bundle.graph.model_dump(mode="json"),
                option=orjson.OPT_INDENT_2,
            )
        )
        return bundle_path

    @staticmethod
    def load_diagram_bundle(path: str | Path) -> DiagramBundleModel:
        """Load a persisted diagram bundle from disk.

        Args:
            path: Saved diagram bundle path.

        Returns:
            DiagramBundleModel: Parsed diagram bundle.
        """

        return DiagramBundleModel.model_validate(orjson.loads(Path(path).read_bytes()))

    def bundle_path(
        self,
        *,
        datasource_name: str,
        schema_name: str,
        snapshot_id: str,
    ) -> Path:
        """Return the persisted diagram-bundle path for one snapshot."""

        return self.diagram_dir / datasource_name / schema_name / f"{snapshot_id}.json"

    def mermaid_path(
        self,
        *,
        datasource_name: str,
        schema_name: str,
        snapshot_id: str,
    ) -> Path:
        """Return the Mermaid ER diagram path for one snapshot."""

        return self.diagram_dir / datasource_name / schema_name / f"{snapshot_id}.mmd"

    def graph_path(
        self,
        *,
        datasource_name: str,
        schema_name: str,
        snapshot_id: str,
    ) -> Path:
        """Return the graph JSON path for one snapshot."""

        return (
            self.diagram_dir
            / datasource_name
            / schema_name
            / f"{snapshot_id}.graph.json"
        )

    @property
    def diagram_dir(self) -> Path:
        """Return the configured diagram-artifact root directory."""

        return Path(self._artifacts.root_dir) / self._artifacts.diagrams_dir

    def _build_graph(
        self,
        *,
        snapshot: SnapshotBundleModel,
        profiles: dict[str, TableProfileModel],
    ) -> SchemaGraphModel:
        """Build graph JSON payloads from one snapshot.

        Args:
            snapshot: Snapshot to render.
            profiles: Profiles keyed by qualified table name.

        Returns:
            SchemaGraphModel: Graph payload.
        """

        nodes = [
            *[
                self._table_node(
                    table=table,
                    profile=profiles.get(
                        self._qualify_name(table.schema_name, table.name)
                    ),
                )
                for table in snapshot.schema_metadata.tables
            ],
            *[
                SchemaGraphNodeModel(
                    node_id=self._qualify_name(view.schema_name, view.name),
                    label=self._qualify_name(view.schema_name, view.name),
                    kind="view",
                    schema_name=view.schema_name,
                    object_name=view.name,
                    summary=view.summary,
                    metadata={
                        "column_count": len(view.columns),
                        "definition_available": view.definition is not None,
                    },
                )
                for view in snapshot.schema_metadata.views
            ],
        ]
        edges = [self._graph_edge(edge=edge) for edge in snapshot.relationship_edges]
        return SchemaGraphModel(nodes=nodes, edges=edges)

    def _table_node(
        self,
        *,
        table: TableModel,
        profile: TableProfileModel | None,
    ) -> SchemaGraphNodeModel:
        """Build one table node for the graph export."""

        metadata: dict[str, object | None] = {
            "column_count": len(table.columns),
            "primary_key": table.primary_key,
            "index_count": len(table.indexes),
            "foreign_key_count": len(table.foreign_keys),
        }
        if profile is not None:
            metadata.update(
                {
                    "row_count": profile.row_count,
                    "storage_bytes": profile.storage_bytes,
                    "entity_kind": profile.entity_kind,
                }
            )
        return SchemaGraphNodeModel(
            node_id=self._qualify_name(table.schema_name, table.name),
            label=self._qualify_name(table.schema_name, table.name),
            kind="table",
            schema_name=table.schema_name,
            object_name=table.name,
            summary=table.summary,
            metadata=metadata,
        )

    def _graph_edge(self, *, edge: RelationshipEdgeModel) -> SchemaGraphEdgeModel:
        """Build one graph edge from a snapshot relationship."""

        return SchemaGraphEdgeModel(
            source_node_id=self._qualify_name(edge.source_schema, edge.source_table),
            target_node_id=self._qualify_name(edge.target_schema, edge.target_table),
            label=", ".join(edge.source_columns) or edge.constraint_name,
            source_columns=edge.source_columns,
            target_columns=edge.target_columns,
            constraint_name=edge.constraint_name,
            summary=edge.summary,
        )

    def _build_mermaid(
        self,
        *,
        snapshot: SnapshotBundleModel,
        profiles: dict[str, TableProfileModel],
    ) -> str:
        """Render a Mermaid ER diagram for one schema snapshot.

        Args:
            snapshot: Snapshot bundle to render.
            profiles: Profiles keyed by qualified table name.

        Returns:
            str: Mermaid ER diagram text.
        """

        lines = ["erDiagram", "  direction LR"]
        for table in snapshot.schema_metadata.tables:
            lines.extend(
                self._mermaid_entity_block(
                    table=table,
                    profile=profiles.get(
                        self._qualify_name(table.schema_name, table.name)
                    ),
                )
            )

        table_map = {
            self._qualify_name(table.schema_name, table.name): table
            for table in snapshot.schema_metadata.tables
        }
        for edge in snapshot.relationship_edges:
            target_name = self._qualify_name(edge.target_schema, edge.target_table)
            source_name = self._qualify_name(edge.source_schema, edge.source_table)
            source_table = table_map.get(source_name)
            connector = self._relationship_connector(
                source_table=source_table,
                source_columns=edge.source_columns,
            )
            edge_label = (
                edge.constraint_name or "_".join(edge.source_columns) or "references"
            )
            lines.append(
                f"  {self._entity_name(target_name)} {connector} "
                f"{self._entity_name(source_name)} : {self._mermaid_label(edge_label)}"
            )

        return "\n".join(lines)

    def _mermaid_entity_block(
        self,
        *,
        table: TableModel,
        profile: TableProfileModel | None,
    ) -> list[str]:
        """Render one Mermaid entity block for a table."""

        qualified_name = self._qualify_name(table.schema_name, table.name)
        lines = [f"  {self._entity_name(qualified_name)} {{"]
        unique_columns = {
            column_name
            for constraint in table.unique_constraints
            for column_name in constraint.columns
        }
        for column in table.columns:
            flags: list[str] = []
            if column.name in table.primary_key:
                flags.append("PK")
            if column.name in unique_columns:
                flags.append("UK")
            if any(
                column.name in foreign_key.columns for foreign_key in table.foreign_keys
            ):
                flags.append("FK")
            flag_suffix = f" {', '.join(flags)}" if flags else ""
            lines.append(
                f"    {self._mermaid_data_type(column.data_type)} {column.name}{flag_suffix}"
            )
        lines.append("  }")
        return lines

    def _relationship_connector(
        self,
        *,
        source_table: TableModel | None,
        source_columns: list[str],
    ) -> str:
        """Return a Mermaid ER connector for a foreign-key relationship."""

        if source_table is not None and self._is_unique_column_set(
            table=source_table,
            columns=source_columns,
        ):
            return "||--||"
        return "||--o{"

    def _is_unique_column_set(self, *, table: TableModel, columns: list[str]) -> bool:
        """Return whether a column set is unique on the source table."""

        column_set = set(columns)
        if not column_set:
            return False
        if column_set == set(table.primary_key):
            return True
        return any(
            column_set == set(constraint.columns)
            for constraint in table.unique_constraints
        )

    @staticmethod
    def _entity_name(qualified_name: str) -> str:
        """Return a Mermaid-safe entity identifier."""

        cleaned = "".join(
            character if character.isalnum() else "_" for character in qualified_name
        )
        normalized = cleaned.upper().strip("_") or "ENTITY"
        if not normalized[0].isalpha():
            return f"ENTITY_{normalized}"
        return normalized

    @staticmethod
    def _mermaid_data_type(data_type: str) -> str:
        """Normalize a reflected SQL type into a Mermaid-friendly token."""

        normalized = "".join(
            (character if character.isalnum() or character in {"_", "-"} else "_")
            for character in data_type
        )
        normalized = normalized.upper().strip("_")
        while "__" in normalized:
            normalized = normalized.replace("__", "_")
        normalized = normalized or "TYPE"
        if not normalized[0].isalpha():
            return f"TYPE_{normalized}"
        return normalized

    @staticmethod
    def _mermaid_label(label: str) -> str:
        """Normalize a Mermaid edge label."""

        return "".join(
            character if character.isalnum() or character == "_" else "_"
            for character in label
        )

    @staticmethod
    def _qualify_name(schema_name: str | None, object_name: str) -> str:
        """Return a schema-qualified object name."""

        if schema_name is None:
            return object_name
        return f"{schema_name}.{object_name}"

    @staticmethod
    def _hash_bundle(bundle: DiagramBundleModel) -> str:
        """Return a deterministic content hash for one diagram bundle."""

        payload = bundle.model_dump(
            mode="json",
            exclude={"created_at", "content_hash", "summary"},
        )
        return sha256(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)).hexdigest()
