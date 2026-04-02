"""Prompt export services built on stored snapshots and agent context."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import orjson

from sqldbagent.adapters.langgraph.prompts import (
    create_sqldbagent_base_system_prompt,
    create_sqldbagent_system_prompt,
)
from sqldbagent.core.agent_context import (
    build_snapshot_prompt_context,
    build_sqldbagent_state_seed,
)
from sqldbagent.core.config import AppSettings, ArtifactSettings, load_settings
from sqldbagent.prompts.enhancement import (
    PromptEnhancementService,
    render_prompt_enhancement_text,
)
from sqldbagent.prompts.models import (
    PromptBundleModel,
    PromptEnhancementModel,
    PromptExplorationModel,
    PromptSectionModel,
)
from sqldbagent.prompts.tokens import estimate_prompt_bundle_tokens
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
        self._enhancements = PromptEnhancementService(artifacts=artifacts)

    def create_prompt_bundle(
        self,
        snapshot: SnapshotBundleModel,
        *,
        enhancement: PromptEnhancementModel | None = None,
    ) -> PromptBundleModel:
        """Build a persisted prompt bundle for one snapshot.

        Args:
            snapshot: Snapshot bundle to export.
            enhancement: Optional preloaded prompt enhancement.

        Returns:
            PromptBundleModel: Durable prompt bundle for the snapshot.
        """

        schema_name = snapshot.regenerate.schema_name
        datasource = self._settings.get_datasource(snapshot.datasource_name)
        resolved_enhancement = (
            enhancement or self._enhancements.load_or_create_enhancement(snapshot)
        )
        base_system_prompt = create_sqldbagent_base_system_prompt(
            datasource_name=snapshot.datasource_name,
            settings=self._settings,
            schema_name=schema_name,
        )
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
                    f"Dialect: {datasource.dialect.value}\n"
                    f"Schema: {schema_name}\n"
                    f"Snapshot ID: {snapshot.snapshot_id}\n"
                    "Default access mode: read_only\n"
                    "Writable access available: "
                    + ("yes" if datasource.safety.allow_writes else "no")
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
        enhancement_text = render_prompt_enhancement_text(resolved_enhancement)
        system_prompt = create_sqldbagent_system_prompt(
            datasource_name=snapshot.datasource_name,
            settings=self._settings,
            schema_name=schema_name,
            enhancement=resolved_enhancement,
        )
        if enhancement_text is not None:
            sections.append(
                PromptSectionModel(
                    title="Prompt Enhancement",
                    content=enhancement_text,
                )
            )
        state_seed = build_sqldbagent_state_seed(
            datasource_name=snapshot.datasource_name,
            settings=self._settings,
            schema_name=schema_name,
        )
        state_seed["prompt_enhancement_active"] = resolved_enhancement.active
        state_seed["prompt_enhancement_summary"] = resolved_enhancement.summary
        bundle = PromptBundleModel(
            snapshot_id=snapshot.snapshot_id,
            datasource_name=snapshot.datasource_name,
            schema_name=schema_name,
            base_system_prompt=base_system_prompt,
            system_prompt=system_prompt,
            sections=sections,
            enhancement=resolved_enhancement,
            token_estimates=estimate_prompt_bundle_tokens(
                base_system_prompt=base_system_prompt,
                system_prompt=system_prompt,
                enhancement_text=enhancement_text,
                model=self._settings.llm.default_model,
            ),
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

    def load_or_create_enhancement(
        self,
        snapshot: SnapshotBundleModel,
        *,
        refresh_generated: bool = False,
    ) -> PromptEnhancementModel:
        """Load or create the prompt enhancement for one snapshot.

        Args:
            snapshot: Snapshot bundle backing the enhancement.
            refresh_generated: Whether to force DB-guidance regeneration.

        Returns:
            PromptEnhancementModel: Stored or generated enhancement artifact.
        """

        enhancement = self._enhancements.load_or_create_enhancement(
            snapshot,
            refresh_generated=refresh_generated,
        )
        self._enhancements.save_prompt_enhancement(enhancement)
        return enhancement

    def update_prompt_enhancement(
        self,
        snapshot: SnapshotBundleModel,
        *,
        active: bool,
        user_context: str | None,
        business_rules: str | None,
        additional_effective_context: str | None,
        answer_style: str | None,
        refresh_generated: bool = False,
    ) -> PromptEnhancementModel:
        """Update and persist the prompt enhancement for one snapshot.

        Args:
            snapshot: Snapshot bundle backing the enhancement.
            active: Whether the enhancement should be active.
            user_context: Freeform user context or domain notes.
            business_rules: Business rules and caveats.
            additional_effective_context: Extra instructions that should be
                merged directly into the effective system prompt.
            answer_style: Preferred answer style for downstream outputs.
            refresh_generated: Whether to force DB-guidance regeneration.

        Returns:
            PromptEnhancementModel: Persisted enhancement artifact.
        """

        enhancement = self._enhancements.update_enhancement(
            snapshot,
            active=active,
            user_context=user_context,
            business_rules=business_rules,
            additional_effective_context=additional_effective_context,
            answer_style=answer_style,
            refresh_generated=refresh_generated,
        )
        self._enhancements.save_prompt_enhancement(enhancement)
        return enhancement

    def save_prompt_exploration(
        self,
        snapshot: SnapshotBundleModel,
        *,
        exploration: PromptExplorationModel,
    ) -> PromptEnhancementModel:
        """Persist live exploration context into the schema enhancement.

        Args:
            snapshot: Snapshot bundle backing the prompt enhancement.
            exploration: Live exploration block to persist.

        Returns:
            PromptEnhancementModel: Updated prompt enhancement artifact.
        """

        enhancement = self._enhancements.save_exploration_context(
            snapshot,
            exploration=exploration,
        )
        self._enhancements.save_prompt_enhancement(enhancement)
        return enhancement

    def save_prompt_enhancement(self, enhancement: PromptEnhancementModel) -> Path:
        """Persist one prompt-enhancement artifact.

        Args:
            enhancement: Enhancement artifact to persist.

        Returns:
            Path: Saved enhancement path.
        """

        return self._enhancements.save_prompt_enhancement(enhancement)

    def load_saved_enhancement(
        self,
        *,
        datasource_name: str,
        schema_name: str,
    ) -> PromptEnhancementModel | None:
        """Load a saved prompt enhancement when one exists.

        Args:
            datasource_name: Datasource identifier.
            schema_name: Schema name.

        Returns:
            PromptEnhancementModel | None: Saved enhancement or `None`.
        """

        return self._enhancements.load_saved_enhancement(
            datasource_name=datasource_name,
            schema_name=schema_name,
        )

    def enhancement_path(self, *, datasource_name: str, schema_name: str) -> Path:
        """Return the persisted prompt-enhancement path.

        Args:
            datasource_name: Datasource identifier.
            schema_name: Schema name.

        Returns:
            Path: Enhancement JSON path.
        """

        return self._enhancements.enhancement_path(
            datasource_name=datasource_name,
            schema_name=schema_name,
        )

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
                "## Token Budget",
                "",
                f"- Base prompt tokens: `{bundle.token_estimates.get('base_system_prompt_tokens', 'unknown')}`",
                f"- System prompt tokens: `{bundle.token_estimates.get('system_prompt_tokens', 'unknown')}`",
                f"- Enhancement tokens: `{bundle.token_estimates.get('enhancement_text_tokens', 'unknown')}`",
                f"- Prompt delta tokens: `{bundle.token_estimates.get('prompt_delta_tokens', 'unknown')}`",
                "",
                *section_lines,
                "## Base System Prompt",
                "",
                "```text",
                bundle.base_system_prompt,
                "```",
                "",
                "## State Seed",
                "",
                "```json",
                state_json,
                "```",
                "",
                "## Token Estimates JSON",
                "",
                "```json",
                orjson.dumps(
                    bundle.token_estimates,
                    option=orjson.OPT_INDENT_2,
                ).decode(),
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
