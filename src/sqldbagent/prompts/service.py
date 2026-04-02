"""Prompt export services built on stored snapshots and agent context."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import orjson

from sqldbagent.adapters.langgraph.prompts import create_sqldbagent_system_prompt
from sqldbagent.core.agent_context import (
    build_snapshot_prompt_context,
    build_sqldbagent_state_seed,
)
from sqldbagent.core.config import AppSettings, ArtifactSettings, load_settings
from sqldbagent.prompts.models import PromptBundleModel, PromptSectionModel
from sqldbagent.snapshot.models import SnapshotBundleModel


class SnapshotPromptService:
    """Persist descriptive prompt bundles derived from stored snapshots."""

    def __init__(
        self,
        *,
        artifacts: ArtifactSettings,
        settings: AppSettings | None = None,
    ) -> None:
        """Initialize the prompt exporter.

        Args:
            artifacts: Artifact directory settings.
            settings: Optional application settings for prompt generation.
        """

        self._artifacts = artifacts
        self._settings = settings or load_settings()

    def create_prompt_bundle(self, snapshot: SnapshotBundleModel) -> PromptBundleModel:
        """Build a persisted prompt bundle for one snapshot.

        Args:
            snapshot: Snapshot bundle to export.

        Returns:
            PromptBundleModel: Durable prompt bundle for the snapshot.
        """

        schema_name = snapshot.regenerate.schema_name
        sections = [
            PromptSectionModel(
                title="Role",
                content=(
                    f"Agent name: {self._settings.agent.name}\n"
                    "Mission: safe database intelligence over normalized metadata, "
                    "stored artifacts, retrieval, profiling, and guarded SQL."
                ),
            ),
            PromptSectionModel(
                title="Active Context",
                content=(
                    f"Datasource: {snapshot.datasource_name}\n"
                    f"Schema: {schema_name}\n"
                    f"Snapshot ID: {snapshot.snapshot_id}"
                ),
            ),
            PromptSectionModel(
                title="Stored Snapshot Context",
                content=build_snapshot_prompt_context(
                    datasource_name=snapshot.datasource_name,
                    settings=self._settings,
                    schema_name=schema_name,
                )
                or "No stored snapshot context was available.",
            ),
            PromptSectionModel(
                title="Workflow",
                content=(
                    "1. Inspect schemas, tables, and views before running SQL.\n"
                    "2. Reuse stored snapshot, diagram, and document artifacts before live reads.\n"
                    "3. Prefer retrieval over stored documents when it can answer the question.\n"
                    "4. Use safe_query_sql only when metadata and artifacts are insufficient.\n"
                    "5. Mark any inference explicitly and distinguish it from observed facts."
                ),
            ),
        ]
        state_seed = build_sqldbagent_state_seed(
            datasource_name=snapshot.datasource_name,
            settings=self._settings,
            schema_name=schema_name,
        )
        bundle = PromptBundleModel(
            snapshot_id=snapshot.snapshot_id,
            datasource_name=snapshot.datasource_name,
            schema_name=schema_name,
            system_prompt=create_sqldbagent_system_prompt(
                datasource_name=snapshot.datasource_name,
                settings=self._settings,
                schema_name=schema_name,
            ),
            sections=sections,
            state_seed=state_seed,
        )
        return bundle.model_copy(
            update={
                "content_hash": self._hash_bundle(bundle),
                "summary": (
                    f"Prompt bundle for datasource '{snapshot.datasource_name}' "
                    f"schema '{schema_name}' using snapshot '{snapshot.snapshot_id}'."
                ),
            }
        )

    def save_prompt_bundle(self, bundle: PromptBundleModel) -> Path:
        """Persist one prompt bundle and a companion Markdown file.

        Args:
            bundle: Prompt bundle to persist.

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
        self.markdown_path(
            datasource_name=bundle.datasource_name,
            schema_name=bundle.schema_name,
            snapshot_id=bundle.snapshot_id,
        ).write_text(self.render_markdown(bundle), encoding="utf-8")
        return bundle_path

    @staticmethod
    def load_prompt_bundle(path: str | Path) -> PromptBundleModel:
        """Load a persisted prompt bundle from disk.

        Args:
            path: Saved prompt-bundle path.

        Returns:
            PromptBundleModel: Parsed prompt bundle.
        """

        return PromptBundleModel.model_validate(orjson.loads(Path(path).read_bytes()))

    def bundle_path(
        self,
        *,
        datasource_name: str,
        schema_name: str,
        snapshot_id: str,
    ) -> Path:
        """Return the JSON bundle path for one prompt export."""

        return self.prompt_dir / datasource_name / schema_name / f"{snapshot_id}.json"

    def markdown_path(
        self,
        *,
        datasource_name: str,
        schema_name: str,
        snapshot_id: str,
    ) -> Path:
        """Return the Markdown prompt path for one prompt export."""

        return self.prompt_dir / datasource_name / schema_name / f"{snapshot_id}.md"

    @property
    def prompt_dir(self) -> Path:
        """Return the configured prompt-artifact root directory."""

        return Path(self._artifacts.root_dir) / self._artifacts.prompts_dir

    def render_markdown(self, bundle: PromptBundleModel) -> str:
        """Render a human-readable Markdown prompt artifact.

        Args:
            bundle: Prompt bundle to render.

        Returns:
            str: Markdown representation of the prompt bundle.
        """

        section_lines = []
        for section in bundle.sections:
            section_lines.extend([f"## {section.title}", "", section.content, ""])
        state_json = orjson.dumps(
            bundle.state_seed,
            option=orjson.OPT_INDENT_2,
        ).decode()
        return "\n".join(
            [
                f"# Prompt Bundle: {bundle.datasource_name}.{bundle.schema_name}",
                "",
                f"- Snapshot ID: `{bundle.snapshot_id}`",
                f"- Summary: {bundle.summary or 'No summary available.'}",
                "",
                *section_lines,
                "## State Seed",
                "",
                "```json",
                state_json,
                "```",
                "",
                "## System Prompt",
                "",
                "```text",
                bundle.system_prompt,
                "```",
            ]
        ).strip()

    @staticmethod
    def _hash_bundle(bundle: PromptBundleModel) -> str:
        """Return a deterministic content hash for one prompt bundle."""

        payload = orjson.dumps(
            bundle.model_dump(
                mode="json",
                exclude={"content_hash", "summary", "created_at"},
            ),
            option=orjson.OPT_SORT_KEYS,
        )
        return sha256(payload).hexdigest()
