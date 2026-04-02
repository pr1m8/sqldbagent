# Memory Setup

## Purpose

This file defines what should be treated as durable working memory for this repository.

The goal is to keep future agent work consistent without polluting memory with ephemeral local details.

## What Should Be Remembered

Stable repo memory should capture:

- architecture rule: normalized metadata core in the middle, dialect enrichers on the edges
- delivery order: core, engines, introspection, profiling and snapshots, safety and exports, CLI, adapters, dashboard
- workflow defaults: `pdm` for environment and commands, `trunk check --fix` for hygiene, Commitizen for conventional commits
- test strategy: Postgres and MSSQL are real integration targets, SQLite is smoke-only
- safety rule: all agent-facing SQL must go through the safety layer
- docs rule: internal contributor process belongs in `docs/_internal`
- internal docs should keep general agent-platform guidance separate from dashboard-surface notes
- public docs rule: stable user-facing documentation belongs in `docs/source`
- introspection scope is intentionally large and should grow toward server, database, schema, table, view, constraints, indexes, routines, grants, comments, sizes, and storage metadata
- snapshot storage is the durable multi-server introspection cache; persisted artifacts should be organized per datasource/schema and loadable later from an index
- prompt bundles are durable agent artifacts and should be stored beside other per-datasource/schema artifacts with both JSON and Markdown forms
- prompt enhancements are durable per-datasource/schema artifacts and should preserve user-authored context while regenerating DB-aware guidance from newer snapshots
- prompt enhancements should support a distinct additional effective-prompt instruction field for direct system-prompt injection without overloading domain notes or answer-style guidance
- prompt bundles and prompt enhancements should cache token budgets for the base prompt, effective prompt, and enhancement layers so prompt size is inspectable without recomputing it every run
- token estimation should prefer `tiktoken` when available and fall back to a deterministic approximation when it is not
- LangGraph long-term memory should persist canonical datasource/schema context in the store and inject it through the shared dynamic-prompt path, not through dashboard-only state
- when long-term memory is enabled, snapshot-derived context should be able to auto-sync into the store and reuse the checkpoint Postgres database URL unless a separate store URL is configured
- live prompt exploration is a persisted read-only context layer that can be merged into prompt enhancements and optionally summarized into long-term memory; it is not a transient UI-only note
- retrieval is a helper over stored snapshot documents, not the primary execution path
- Qdrant is the default retrieval backend for indexed snapshot documents and should be raised with the main integration compose stack
- dashboard retrieval should resolve the active stored snapshot from persisted prompt or diagram artifacts when thread state has not populated snapshot identifiers yet
- datasource aliases are a settings-layer ergonomics feature; persisted artifacts still use canonical datasource names
- LangChain v1 should be used through our own strict tool surface and LangGraph checkpointers, not via the generic SQL toolkit as the primary execution path
- local Postgres is the standard agent checkpoint target when persistence is enabled, but it should be treated as separate persistence infrastructure from inspected target databases
- read-only engine policy is dialect-specific: SQLite uses `PRAGMA query_only`, Postgres sets `default_transaction_read_only`, and MSSQL should add ODBC `ApplicationIntent=ReadOnly` while still relying on the central SQL guard as the hard safety boundary
- agent middleware should own dynamic prompting, state seeding, todo handling, tool-error shaping, HITL, and summarization policy
- the dashboard Prompt tab is the current human-facing control surface for reviewing the base prompt, effective prompt, and saved prompt enhancement context
- the dashboard chat surface should stream meaningful agent progress instead of blocking behind a single spinner, while keeping the same guarded read-only execution path
- saved dashboard threads should support optional user-friendly names and remain reloadable through the shared thread registry
- new datasource/schema contexts should offer a lightweight initial annotation path so prompt enhancement starts with human context instead of waiting for a later prompt-only workflow
- the dashboard should expose explicit controls to regenerate schema-aware prompt context and to ensure or rebuild the retrieval index for the active stored snapshot
- the dashboard schema surface should always provide a server-rendered image fallback when Mermaid rendering is unavailable or inconsistent
- dashboard observability should report the effective checkpoint backend and fallback reason, not just the requested settings value
- `make dashboard-demo` should prefer durable Postgres checkpointing when local checkpoint configuration is available
- `make dashboard-demo` and `make langgraph-dev-demo` should prefer durable Postgres checkpointing plus durable Postgres-backed long-term memory when local persistence configuration is available
- Make targets should cover the common LangGraph flows directly: dev, demo-dev, dockerized up, debug, and runtime/checkpoint test entrypoints
- FastMCP serving should be settings-driven through `.env` with CLI overrides, not hard-coded transport choices
- the first chat UI surface is the Streamlit dashboard over persisted LangGraph thread IDs, not a separate frontend app
- internal dashboard notes should live under `docs/_internal/dashboard`, while reusable LangChain v1 / LangGraph patterns should live under `docs/_internal/agent-platform-kit` and the internal `agents` index
- live integration and E2E tests should load datasource config from `.env`, not rely only on raw exported shell variables
- `langgraph.json` should rely on the local project `pyproject.toml` for dependencies instead of duplicating package names
- LangSmith tracing should stay optional, `.env`-driven, and enabled through first-class settings rather than scattered env checks
- release work should use PDM build/publish flows, with commit groups kept coherent and pushed only after validation passes

## What Should Not Be Remembered

Do not persist as durable memory:

- secrets or credentials
- personal file paths
- temporary branches
- one-off debugging details
- transient container IDs or ports unless they become project defaults

## Where To Capture Stable Memory

Prefer these locations:

1. [AGENTS.md](/Users/will/Projects/sqldbagent/AGENTS.md)
2. [docs/\_internal/implementation-roadmap.md](/Users/will/Projects/sqldbagent/docs/_internal/implementation-roadmap.md)
3. [docs/\_internal/README.md](/Users/will/Projects/sqldbagent/docs/_internal/README.md)

If a rule matters to repeated implementation decisions, promote it into one of those files.

## Initial Repo Memory

The current stable memory for `sqldbagent` is:

- use `pdm`
- use `trunk check --fix`
- use Commitizen conventions
- prefer thin adapters
- keep dialect details out of shared services
- treat database safety as a first-class design constraint
- treat introspection as a major product pillar, not a thin table-listing helper
