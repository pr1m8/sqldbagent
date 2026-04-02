"""Snapshot persistence service."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

import orjson

from sqldbagent.core.config import ArtifactSettings
from sqldbagent.core.models.catalog import RelationshipEdgeModel
from sqldbagent.introspect.service import SQLAlchemyInspectionService
from sqldbagent.profile.service import SQLAlchemyProfilingService
from sqldbagent.snapshot.models import (
    SnapshotBundleModel,
    SnapshotDiffModel,
    SnapshotInventoryEntryModel,
    SnapshotRequestModel,
    TableDiffModel,
)


class SnapshotService:
    """Create, persist, reload, and diff normalized snapshot bundles."""

    def __init__(
        self,
        *,
        datasource_name: str,
        inspector: SQLAlchemyInspectionService,
        profiler: SQLAlchemyProfilingService,
        artifacts: ArtifactSettings,
    ) -> None:
        """Initialize the snapshot service.

        Args:
            datasource_name: Datasource identifier.
            inspector: Inspection service used for schema metadata.
            profiler: Profiling service used for table profiles.
            artifacts: Artifact persistence settings.
        """

        self._datasource_name = datasource_name
        self._inspector = inspector
        self._profiler = profiler
        self._artifacts = artifacts

    def create_schema_snapshot(
        self, schema_name: str, *, sample_size: int = 5
    ) -> SnapshotBundleModel:
        """Create a snapshot bundle for one schema.

        Args:
            schema_name: Schema name to capture.
            sample_size: Sample rows per table profile.

        Returns:
            SnapshotBundleModel: Snapshot bundle.
        """

        schema_metadata = self._inspector.inspect_schema(schema_name)
        profiles = [
            self._profiler.profile_table(
                table_name=table.name,
                schema=schema_name,
                sample_size=sample_size,
            )
            for table in schema_metadata.tables
        ]
        relationship_edges = self._build_relationship_edges(schema_metadata)

        bundle = SnapshotBundleModel(
            datasource_name=self._datasource_name,
            schema_metadata=schema_metadata,
            relationship_edges=relationship_edges,
            profiles=profiles,
            regenerate=SnapshotRequestModel(
                datasource_name=self._datasource_name,
                schema_name=schema_name,
                sample_size=sample_size,
            ),
        )
        content_hash = self._hash_bundle(bundle)
        return bundle.model_copy(
            update={
                "content_hash": content_hash,
                "summary": self._summarize_bundle(
                    schema_name=schema_name,
                    table_count=len(schema_metadata.tables),
                    view_count=len(schema_metadata.views),
                    profile_count=len(profiles),
                    relationship_count=len(relationship_edges),
                    content_hash=content_hash,
                ),
            }
        )

    def save_snapshot(self, bundle: SnapshotBundleModel) -> Path:
        """Persist a snapshot bundle to disk and update the inventory index.

        Args:
            bundle: Snapshot bundle to persist.

        Returns:
            Path: Snapshot file path.
        """

        schema_name = bundle.regenerate.schema_name
        relative_path = (
            Path(self._datasource_name) / schema_name / f"{bundle.snapshot_id}.json"
        )
        path = self.snapshot_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            orjson.dumps(
                bundle.model_dump(mode="json"),
                option=orjson.OPT_INDENT_2,
            )
        )

        entry = SnapshotInventoryEntryModel(
            datasource_name=bundle.datasource_name,
            schema_name=schema_name,
            snapshot_id=bundle.snapshot_id,
            created_at=bundle.created_at,
            content_hash=bundle.content_hash,
            path=relative_path.as_posix(),
            summary=bundle.summary,
        )
        self._upsert_inventory_entry(entry)
        return path

    @staticmethod
    def load_snapshot(path: str | Path) -> SnapshotBundleModel:
        """Load a snapshot bundle from disk.

        Args:
            path: Snapshot file path.

        Returns:
            SnapshotBundleModel: Loaded snapshot bundle.
        """

        data = orjson.loads(Path(path).read_bytes())
        return SnapshotBundleModel.model_validate(data)

    @staticmethod
    def diff_snapshots(
        left: SnapshotBundleModel,
        right: SnapshotBundleModel,
    ) -> SnapshotDiffModel:
        """Diff two snapshot bundles.

        Args:
            left: Baseline snapshot bundle.
            right: Comparison snapshot bundle.

        Returns:
            SnapshotDiffModel: Snapshot diff payload.
        """

        left_tables = {
            SnapshotService._qualify_static(table.schema_name, table.name): table
            for table in left.schema_metadata.tables
        }
        right_tables = {
            SnapshotService._qualify_static(table.schema_name, table.name): table
            for table in right.schema_metadata.tables
        }
        left_profiles = {
            SnapshotService._qualify_static(
                profile.schema_name, profile.table_name
            ): profile
            for profile in left.profiles
        }
        right_profiles = {
            SnapshotService._qualify_static(
                profile.schema_name, profile.table_name
            ): profile
            for profile in right.profiles
        }

        added_tables = sorted(set(right_tables) - set(left_tables))
        removed_tables = sorted(set(left_tables) - set(right_tables))
        changed_tables = [
            SnapshotService._diff_table(
                table_name=table_name,
                left_table=left_tables[table_name],
                right_table=right_tables[table_name],
                left_profile=left_profiles.get(table_name),
                right_profile=right_profiles.get(table_name),
            )
            for table_name in sorted(set(left_tables) & set(right_tables))
        ]
        changed_tables = [
            table_diff
            for table_diff in changed_tables
            if table_diff.added_columns
            or table_diff.removed_columns
            or table_diff.changed_columns
            or table_diff.metadata_changed
            or table_diff.profile_changed
        ]

        left_views = {
            SnapshotService._qualify_static(view.schema_name, view.name)
            for view in left.schema_metadata.views
        }
        right_views = {
            SnapshotService._qualify_static(view.schema_name, view.name)
            for view in right.schema_metadata.views
        }
        added_views = sorted(right_views - left_views)
        removed_views = sorted(left_views - right_views)

        left_relationships = {
            SnapshotService._relationship_signature(edge)
            for edge in left.relationship_edges
        }
        right_relationships = {
            SnapshotService._relationship_signature(edge)
            for edge in right.relationship_edges
        }
        added_relationships = sorted(right_relationships - left_relationships)
        removed_relationships = sorted(left_relationships - right_relationships)

        diff = SnapshotDiffModel(
            left_snapshot_id=left.snapshot_id,
            right_snapshot_id=right.snapshot_id,
            left_content_hash=left.content_hash,
            right_content_hash=right.content_hash,
            added_tables=added_tables,
            removed_tables=removed_tables,
            changed_tables=changed_tables,
            added_views=added_views,
            removed_views=removed_views,
            added_relationships=added_relationships,
            removed_relationships=removed_relationships,
        )
        return diff.model_copy(
            update={"summary": SnapshotService._summarize_diff(diff)}
        )

    @staticmethod
    def list_saved_snapshots(
        artifacts: ArtifactSettings,
        *,
        datasource_name: str | None = None,
        schema_name: str | None = None,
    ) -> list[SnapshotInventoryEntryModel]:
        """List saved snapshots from the inventory index.

        Args:
            artifacts: Artifact persistence settings.
            datasource_name: Optional datasource filter.
            schema_name: Optional schema filter.

        Returns:
            list[SnapshotInventoryEntryModel]: Matching saved snapshots.
        """

        entries = SnapshotService._read_inventory(artifacts)
        filtered = [
            entry
            for entry in entries
            if (datasource_name is None or entry.datasource_name == datasource_name)
            and (schema_name is None or entry.schema_name == schema_name)
        ]
        return sorted(filtered, key=lambda entry: entry.created_at, reverse=True)

    @staticmethod
    def load_latest_snapshot(
        artifacts: ArtifactSettings,
        *,
        datasource_name: str,
        schema_name: str,
    ) -> SnapshotBundleModel:
        """Load the newest saved snapshot for a datasource/schema pair.

        Args:
            artifacts: Artifact persistence settings.
            datasource_name: Datasource identifier.
            schema_name: Captured schema name.

        Returns:
            SnapshotBundleModel: Latest matching snapshot.

        Raises:
            FileNotFoundError: If no matching snapshot exists.
        """

        entries = SnapshotService.list_saved_snapshots(
            artifacts,
            datasource_name=datasource_name,
            schema_name=schema_name,
        )
        if not entries:
            raise FileNotFoundError(
                f"no saved snapshots found for datasource '{datasource_name}' schema '{schema_name}'"
            )

        root = SnapshotService._snapshot_dir_from_artifacts(artifacts)
        return SnapshotService.load_snapshot(root / entries[0].path)

    @property
    def snapshot_dir(self) -> Path:
        """Return the configured snapshot directory.

        Returns:
            Path: Snapshot directory path.
        """

        return self._snapshot_dir_from_artifacts(self._artifacts)

    @property
    def datasource_name(self) -> str:
        """Return the datasource name bound to this service."""

        return self._datasource_name

    @property
    def artifacts(self) -> ArtifactSettings:
        """Return the artifact settings bound to this service."""

        return self._artifacts

    def load_latest_saved_snapshot(self, schema_name: str) -> SnapshotBundleModel:
        """Load the newest saved snapshot for the bound datasource and schema.

        Args:
            schema_name: Schema whose latest snapshot should be loaded.

        Returns:
            SnapshotBundleModel: Latest matching saved snapshot.
        """

        return self.load_latest_snapshot(
            self._artifacts,
            datasource_name=self._datasource_name,
            schema_name=schema_name,
        )

    @property
    def inventory_path(self) -> Path:
        """Return the snapshot inventory file path.

        Returns:
            Path: Inventory index path.
        """

        return self.snapshot_dir / "index.json"

    def _build_relationship_edges(
        self,
        schema_metadata: Any,
    ) -> list[RelationshipEdgeModel]:
        """Build relationship graph edges from reflected foreign keys.

        Args:
            schema_metadata: Normalized schema metadata.

        Returns:
            list[RelationshipEdgeModel]: Relationship edges.
        """

        return [
            RelationshipEdgeModel(
                source_schema=table.schema_name,
                source_table=table.name,
                source_columns=foreign_key.columns,
                target_schema=foreign_key.referred_schema,
                target_table=foreign_key.referred_table,
                target_columns=foreign_key.referred_columns,
                constraint_name=foreign_key.name,
                summary=(
                    f"{self._qualify_name(table.schema_name, table.name)} references "
                    f"{self._qualify_name(foreign_key.referred_schema, foreign_key.referred_table)}."
                ),
            )
            for table in schema_metadata.tables
            for foreign_key in table.foreign_keys
        ]

    def _hash_bundle(self, bundle: SnapshotBundleModel) -> str:
        """Return a deterministic content hash for a snapshot bundle.

        Args:
            bundle: Snapshot bundle to hash.

        Returns:
            str: SHA-256 content hash.
        """

        payload = bundle.model_dump(
            mode="json",
            exclude={"snapshot_id", "created_at", "content_hash", "summary"},
        )
        return sha256(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)).hexdigest()

    def _summarize_bundle(
        self,
        *,
        schema_name: str,
        table_count: int,
        view_count: int,
        profile_count: int,
        relationship_count: int,
        content_hash: str,
    ) -> str:
        """Build a short human-readable summary for one snapshot bundle.

        Args:
            schema_name: Captured schema name.
            table_count: Number of tables in the bundle.
            view_count: Number of views in the bundle.
            profile_count: Number of table profiles in the bundle.
            relationship_count: Number of relationship edges.
            content_hash: Deterministic bundle content hash.

        Returns:
            str: Short summary text.
        """

        return (
            f"Snapshot for datasource '{self._datasource_name}' schema '{schema_name}' "
            f"captures {table_count} tables, {view_count} views, {profile_count} table "
            f"profiles, and {relationship_count} relationships. Content hash: "
            f"{content_hash[:12]}."
        )

    def _upsert_inventory_entry(self, entry: SnapshotInventoryEntryModel) -> None:
        """Insert or update one inventory entry."""

        entries = self._read_inventory(self._artifacts)
        filtered = [
            existing
            for existing in entries
            if existing.snapshot_id != entry.snapshot_id
        ]
        filtered.append(entry)
        filtered = sorted(filtered, key=lambda item: item.created_at, reverse=True)
        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
        self.inventory_path.write_bytes(
            orjson.dumps(
                [item.model_dump(mode="json") for item in filtered],
                option=orjson.OPT_INDENT_2,
            )
        )

    @staticmethod
    def _read_inventory(
        artifacts: ArtifactSettings,
    ) -> list[SnapshotInventoryEntryModel]:
        """Read the snapshot inventory index from disk."""

        inventory_path = (
            SnapshotService._snapshot_dir_from_artifacts(artifacts) / "index.json"
        )
        if not inventory_path.exists():
            return []

        data = orjson.loads(inventory_path.read_bytes())
        return [SnapshotInventoryEntryModel.model_validate(item) for item in data]

    def _qualify_name(self, schema: str | None, name: str) -> str:
        """Return a schema-qualified name when a schema is present.

        Args:
            schema: Optional schema name.
            name: Unqualified object name.

        Returns:
            str: Qualified name.
        """

        return self._qualify_static(schema, name)

    @staticmethod
    def _diff_table(
        *,
        table_name: str,
        left_table: Any,
        right_table: Any,
        left_profile: Any,
        right_profile: Any,
    ) -> TableDiffModel:
        """Diff one table across two snapshots."""

        left_columns = {column.name: column for column in left_table.columns}
        right_columns = {column.name: column for column in right_table.columns}
        added_columns = sorted(set(right_columns) - set(left_columns))
        removed_columns = sorted(set(left_columns) - set(right_columns))
        changed_columns = sorted(
            column_name
            for column_name in set(left_columns) & set(right_columns)
            if SnapshotService._model_payload(left_columns[column_name])
            != SnapshotService._model_payload(right_columns[column_name])
        )

        left_table_payload = SnapshotService._model_payload(
            left_table,
            exclude={"columns", "summary"},
        )
        right_table_payload = SnapshotService._model_payload(
            right_table,
            exclude={"columns", "summary"},
        )
        metadata_changed = left_table_payload != right_table_payload

        left_profile_payload = (
            None
            if left_profile is None
            else SnapshotService._model_payload(left_profile, exclude={"summary"})
        )
        right_profile_payload = (
            None
            if right_profile is None
            else SnapshotService._model_payload(right_profile, exclude={"summary"})
        )
        profile_changed = left_profile_payload != right_profile_payload

        return TableDiffModel(
            table_name=table_name,
            added_columns=added_columns,
            removed_columns=removed_columns,
            changed_columns=changed_columns,
            metadata_changed=metadata_changed,
            profile_changed=profile_changed,
            summary=SnapshotService._summarize_table_diff(
                table_name=table_name,
                added_columns=added_columns,
                removed_columns=removed_columns,
                changed_columns=changed_columns,
                metadata_changed=metadata_changed,
                profile_changed=profile_changed,
            ),
        )

    @staticmethod
    def _relationship_signature(edge: RelationshipEdgeModel) -> str:
        """Return a stable relationship edge signature."""

        return (
            f"{SnapshotService._qualify_static(edge.source_schema, edge.source_table)}:"
            f"{','.join(edge.source_columns)}->"
            f"{SnapshotService._qualify_static(edge.target_schema, edge.target_table)}:"
            f"{','.join(edge.target_columns)}"
        )

    @staticmethod
    def _model_payload(
        model: Any,
        exclude: set[str] | None = None,
    ) -> dict[str, object]:
        """Return a normalized JSON payload for model comparison."""

        return model.model_dump(mode="json", exclude=exclude or set())

    @staticmethod
    def _qualify_static(schema: str | None, name: str) -> str:
        """Return a schema-qualified name when a schema is present."""

        if schema:
            return f"{schema}.{name}"
        return name

    @staticmethod
    def _snapshot_dir_from_artifacts(artifacts: ArtifactSettings) -> Path:
        """Return the snapshot root directory from artifact settings."""

        return Path(artifacts.root_dir) / artifacts.snapshots_dir

    @staticmethod
    def _summarize_table_diff(
        *,
        table_name: str,
        added_columns: list[str],
        removed_columns: list[str],
        changed_columns: list[str],
        metadata_changed: bool,
        profile_changed: bool,
    ) -> str:
        """Build a short human-readable summary for one table diff."""

        parts: list[str] = []
        if added_columns:
            parts.append(f"added columns: {', '.join(added_columns)}")
        if removed_columns:
            parts.append(f"removed columns: {', '.join(removed_columns)}")
        if changed_columns:
            parts.append(f"changed columns: {', '.join(changed_columns)}")
        if metadata_changed:
            parts.append("non-column metadata changed")
        if profile_changed:
            parts.append("profile changed")

        joined = "; ".join(parts) if parts else "no changes"
        return f"Table '{table_name}' diff: {joined}."

    @staticmethod
    def _summarize_diff(diff: SnapshotDiffModel) -> str:
        """Build a short human-readable summary for a snapshot diff."""

        return (
            f"Snapshot diff found {len(diff.added_tables)} added tables, "
            f"{len(diff.removed_tables)} removed tables, {len(diff.changed_tables)} "
            f"changed tables, {len(diff.added_views)} added views, "
            f"{len(diff.removed_views)} removed views, {len(diff.added_relationships)} "
            f"added relationships, and {len(diff.removed_relationships)} removed "
            f"relationships."
        )
