# AGENTS.md

## Purpose

This repository is being built as a service-first database intelligence platform. Agents working in this repo must preserve that shape:

- normalized metadata core in the middle
- dialect enrichers on the edges
- CLI, TUI, MCP, LangChain, LangGraph, and dashboard surfaces on shared services

The goal is to keep implementation reusable, testable, and safe for agent-facing workflows.

## Source Of Truth

Use these files in order:

1. [README.md](/Users/will/Projects/sqldbagent/README.md)
2. [docs/\_internal/implementation-roadmap.md](/Users/will/Projects/sqldbagent/docs/_internal/implementation-roadmap.md)
3. [docs/\_internal/README.md](/Users/will/Projects/sqldbagent/docs/_internal/README.md)
4. [docs/\_internal/memory.md](/Users/will/Projects/sqldbagent/docs/_internal/memory.md)
5. [docs/\_internal/product-goal.md](/Users/will/Projects/sqldbagent/docs/_internal/product-goal.md)

If implementation pressure conflicts with the roadmap, fix the roadmap deliberately instead of bypassing it implicitly.

## Architecture Rules

- Put normalized contracts in `src/sqldbagent/core`.
- Put engine creation and connection policy in `src/sqldbagent/engines`.
- Put reflection orchestration in `src/sqldbagent/introspect`.
- Put statistics and sampling in `src/sqldbagent/profile`.
- Put bundle storage and diffing in `src/sqldbagent/snapshot`.
- Put SQL safety checks in `src/sqldbagent/safety`.
- Put dialect-specific SQL and enrichers in `src/sqldbagent/postgres` and `src/sqldbagent/mssql`.
- Keep CLI, TUI, dashboard, and adapters thin. They should call services, not reimplement them.

## Execution Rules

- Any execution of user-provided SQL must pass through the safety layer.
- Prefer read-only defaults for all database access paths.
- Do not couple exports, adapters, or UI code directly to live database handles when normalized models are sufficient.
- Prefer stable serialized artifacts and deterministic outputs where golden testing will matter later.
- Treat the product as a safe database intelligence core, not a generic SQL shell.
- Treat persisted snapshots as the reusable multi-server introspection store; prefer loading from stored artifacts when that satisfies the workflow instead of re-querying by default.
- Treat prompt bundles as durable agent-facing artifacts derived from stored snapshots; prompts, state seeds, and Markdown companions should be reloadable and reviewable.
- Treat LangChain v1 middleware as the agent policy layer. Prompting, state seeding, tool handling, HITL, and summarization should live there instead of being scattered across callers.
- Treat retrieval as an additive helper over stored snapshot documents, not a replacement for inspection, profiling, snapshots, or guarded SQL.
- Treat the LangGraph checkpoint Postgres as persistence infrastructure. Local demos may reuse the same Postgres service, but real deployments should generally separate checkpoint storage from inspected application databases.
- Prefer canonical datasource names in persisted artifacts and use settings-layer aliases only for CLI and agent ergonomics.

## Delivery Order

Build in this order unless there is a documented reason not to:

1. core config and models
2. engine factories and datasource registry
3. normalized inspection flows
4. profiling and snapshots
5. safety and exports
6. CLI
7. TUI and adapters
8. dashboard

## Internal Docs Convention

`docs/_internal/` is for working agreements, bootstrap instructions, setup notes, decision logs, and local integration guidance that supports maintainers and agents.

`docs/source/` is the public documentation surface. Product-facing setup, architecture, CLI, publishing, and API reference material should live there once it is stable enough for contributors and users.

Use it for:

- MCP setup and inventory
- skills setup and inventory
- local development workflows
- architecture decisions before they are promoted into public docs

Do not use it for:

- runtime code
- generated artifacts that belong in a proper output directory
- secrets, credentials, DSNs, or personal tokens

## MCP And Skills Policy

This repo may depend on local MCP servers and Codex skills for development workflows. Those are machine-local capabilities, not package runtime dependencies.

Rules:

- document them in `docs/_internal/`
- record why each MCP server or skill exists
- record the install/source method
- record whether it is required, recommended, or optional
- do not commit personal config files or tokens
- do not assume a contributor already has them installed

Recommended local baseline for this repo:

- MCPs:
  - Docs By LangChain for LangChain and LangGraph adapter research
  - OpenAI Docs for later OpenAI-facing integration work
- Skills:
  - `doc` for writing and tightening project docs
  - `security-best-practices` for reviewing security-sensitive design and implementation choices
  - `security-threat-model` for threat-oriented review of agent-facing SQL and adapter surfaces

These improve implementation quality, but the codebase must still remain usable without them.

## Memory Rules

Treat the following as stable repo memory:

- use `pdm` for project commands
- use `trunk check --fix` for formatting and linting
- use conventional commits via Commitizen
- group commits by coherent feature slices and push after green validation, not as one mixed catch-all commit
- keep adapter surfaces thin
- keep database safety constraints central
- keep retrieval grounded in stored snapshot documents and stable metadata filters
- keep prompt exports grounded in stored snapshots and reusable state seed helpers
- keep LangSmith tracing optional, `.env`-driven, and free of committed secrets

Record durable memory in `AGENTS.md`, the roadmap, or `docs/_internal/`. Do not treat transient terminal state as project memory.

## When Adding New Components

Before adding a new module or surface:

- identify the service contract it depends on
- identify whether the behavior is normalized or dialect-specific
- identify the tests that will lock the behavior
- update the roadmap or internal docs if the scope changes

## Minimum Standard For New Work

Each meaningful feature should leave behind:

- implementation in the correct layer
- tests at the right scope
- doc updates if the workflow or architecture changed
- a sensible commit boundary once the slice is green

If one of those is missing, the work is incomplete.

## Local Runtime Defaults

Use these repo entrypoints by default:

- `make up` to start the integration stack
- `make down` to stop it
- `make ps` to inspect service state
- `make logs-postgres` or `make logs-mssql` for service logs
- `make logs-qdrant` for retrieval service logs
- `make langgraph-dev` for local LangGraph CLI runs
- `make dashboard-demo` to run the persisted demo chat dashboard
- `make mcp-stdio` or `make mcp-http` to expose the local FastMCP server

Live integration and E2E work should load settings from `.env` through the repo
settings layer instead of assuming shell-exported variables only.
