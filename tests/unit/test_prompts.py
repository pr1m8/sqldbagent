"""Prompt export tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from sqldbagent.adapters.langgraph import (
    build_snapshot_prompt_context,
    build_sqldbagent_state_seed,
)
from sqldbagent.core.bootstrap import build_service_container
from sqldbagent.core.config import AppSettings, ArtifactSettings, DatasourceSettings
from sqldbagent.core.enums import Dialect
from sqldbagent.prompts.service import SnapshotPromptService


def test_prompt_service_persists_bundle_and_markdown(tmp_path: Path) -> None:
    """Persist a prompt bundle and its Markdown companion artifact."""

    database_path = tmp_path / "prompt-service.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text("CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        )
        connection.execute(text("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    team_id INTEGER NOT NULL,
                    email TEXT UNIQUE,
                    FOREIGN KEY(team_id) REFERENCES teams(id)
                )
                """))
        connection.execute(text("INSERT INTO teams (id, name) VALUES (1, 'data')"))
        connection.execute(text("""
                INSERT INTO users (id, team_id, email) VALUES
                (1, 1, 'a@example.com'),
                (2, 1, 'b@example.com')
                """))

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        snapshot = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(snapshot)
        enhancement = container.prompt_service.load_or_create_enhancement(snapshot)
        prompt_bundle = container.prompt_service.create_prompt_bundle(
            snapshot,
            enhancement=enhancement,
        )
        prompt_path = container.prompt_service.save_prompt_bundle(prompt_bundle)
        markdown_path = container.prompt_service.markdown_path(
            datasource_name="sqlite",
            schema_name="main",
            snapshot_id=snapshot.snapshot_id,
        )
    finally:
        container.close()
        engine.dispose()

    if not prompt_path.exists():
        raise AssertionError(prompt_path)
    if not markdown_path.exists():
        raise AssertionError(markdown_path)

    loaded_bundle = SnapshotPromptService.load_prompt_bundle(prompt_path)
    if "STORED SNAPSHOT CONTEXT:" not in loaded_bundle.system_prompt:
        raise AssertionError(loaded_bundle.system_prompt)
    if loaded_bundle.base_system_prompt == loaded_bundle.system_prompt:
        raise AssertionError(loaded_bundle.model_dump())
    if loaded_bundle.enhancement is None:
        raise AssertionError(loaded_bundle.model_dump())
    if loaded_bundle.state_seed.get("latest_snapshot_id") != snapshot.snapshot_id:
        raise AssertionError(loaded_bundle.state_seed)
    if loaded_bundle.state_seed.get("prompt_enhancement_active") is not True:
        raise AssertionError(loaded_bundle.state_seed)
    markdown_text = markdown_path.read_text(encoding="utf-8")
    if "## System Prompt" not in markdown_text:
        raise AssertionError(markdown_text)
    if "## Base System Prompt" not in markdown_text:
        raise AssertionError(markdown_text)
    if "users" not in markdown_text:
        raise AssertionError(markdown_text)


def test_langgraph_context_helpers_use_latest_snapshot(tmp_path: Path) -> None:
    """Build prompt context and state seed from stored snapshot artifacts."""

    database_path = tmp_path / "context.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        )

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        snapshot = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(snapshot)
    finally:
        container.close()
        engine.dispose()

    prompt_context = build_snapshot_prompt_context(
        datasource_name="sqlite",
        settings=settings,
        schema_name="main",
    )
    state_seed = build_sqldbagent_state_seed(
        datasource_name="sqlite",
        settings=settings,
        schema_name="main",
    )

    if prompt_context is None or "Captured Objects:" not in prompt_context:
        raise AssertionError(prompt_context)
    dashboard_payload = state_seed.get("dashboard_payload", {})
    if dashboard_payload.get("headline") != "sqlite:main":
        raise AssertionError(state_seed)
    if state_seed.get("latest_snapshot_summary") is None:
        raise AssertionError(state_seed)


def test_prompt_service_updates_prompt_enhancement_context(tmp_path: Path) -> None:
    """Persist user context and merge it into the effective prompt bundle."""

    database_path = tmp_path / "prompt-enhancement.db"
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT UNIQUE, tier TEXT)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total_cents INTEGER)"
            )
        )
    engine.dispose()

    settings = AppSettings(
        datasources=[
            DatasourceSettings(
                name="sqlite",
                dialect=Dialect.SQLITE,
                url=f"sqlite+pysqlite:///{database_path}",
            )
        ],
        artifacts=ArtifactSettings(root_dir=str(tmp_path)),
    )
    container = build_service_container("sqlite", settings=settings)
    try:
        snapshot = container.snapshotter.create_schema_snapshot("main", sample_size=1)
        container.snapshotter.save_snapshot(snapshot)
        enhancement = container.prompt_service.update_prompt_enhancement(
            snapshot,
            active=True,
            user_context="Customers represent paying tenants and tiers map to billing plans.",
            business_rules="Do not treat archived tenants as churn unless cancelled_at is set.",
            answer_style="Prefer short summaries followed by table-level evidence.",
            refresh_generated=True,
        )
        enhancement_path = container.prompt_service.save_prompt_enhancement(enhancement)
        prompt_bundle = container.prompt_service.create_prompt_bundle(
            snapshot,
            enhancement=enhancement,
        )
    finally:
        container.close()

    if not enhancement_path.exists():
        raise AssertionError(enhancement_path)
    if prompt_bundle.enhancement is None:
        raise AssertionError(prompt_bundle.model_dump())
    if "paying tenants" not in prompt_bundle.system_prompt:
        raise AssertionError(prompt_bundle.system_prompt)
    if "paying tenants" in prompt_bundle.base_system_prompt:
        raise AssertionError(prompt_bundle.base_system_prompt)
    if "Entity priorities:" not in prompt_bundle.enhancement.generated_context:
        raise AssertionError(prompt_bundle.enhancement.generated_context)
