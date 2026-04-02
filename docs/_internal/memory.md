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
- public docs rule: stable user-facing documentation belongs in `docs/source`
- introspection scope is intentionally large and should grow toward server, database, schema, table, view, constraints, indexes, routines, grants, comments, sizes, and storage metadata
- snapshot storage is the durable multi-server introspection cache; persisted artifacts should be organized per datasource/schema and loadable later from an index
- prompt bundles are durable agent artifacts and should be stored beside other per-datasource/schema artifacts with both JSON and Markdown forms
- retrieval is a helper over stored snapshot documents, not the primary execution path
- Qdrant is the default retrieval backend for indexed snapshot documents and should be raised with the main integration compose stack
- datasource aliases are a settings-layer ergonomics feature; persisted artifacts still use canonical datasource names
- LangChain v1 should be used through our own strict tool surface and LangGraph checkpointers, not via the generic SQL toolkit as the primary execution path
- local Postgres is the standard agent checkpoint target when persistence is enabled, but it should be treated as separate persistence infrastructure from inspected target databases
- agent middleware should own dynamic prompting, state seeding, todo handling, tool-error shaping, HITL, and summarization policy
- FastMCP serving should be settings-driven through `.env` with CLI overrides, not hard-coded transport choices
- the first chat UI surface is the Streamlit dashboard over persisted LangGraph thread IDs, not a separate frontend app
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
