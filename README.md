# sqldbagent

`sqldbagent` is a service-first database intelligence platform for safe inspection, profiling, snapshotting, guarded querying, and agent-ready export of relational databases.

## Product Goal

`sqldbagent` is not just a thin SQL wrapper and not just a schema dumper.

The product goal is to become the safe backend that an engineer, CLI workflow, MCP server, or LLM agent can rely on to:

- understand a relational database through normalized metadata
- inspect schemas and tables without dialect-specific branching in every surface
- guard SQL before execution so agent access does not become arbitrary database access
- produce durable artifacts like snapshots, docs, diagrams, and prompt context

## Core Thesis

Build a safe database intelligence core first, then expose it through multiple surfaces.

Non-goals for the current phase:

- not a general database admin console
- not a write-capable agent
- not a dashboard-first product
- not a loose collection of LangChain helpers without a stable service layer

The architecture target is:

- normalized metadata core in the middle
- Postgres and MSSQL dialect enrichers on the edges
- CLI, TUI, MCP, LangChain, LangGraph, and dashboard surfaces on top of the same services

The first implementation priorities are:

- datasource config and engine factories
- normalized catalog metadata models
- read-only inspection for Postgres and MSSQL
- SQL safety guardrails and query analysis
- snapshot and profile services
- export pipelines for docs, diagrams, and prompt context

Development hygiene should default to `trunk check --fix`, with conventional commits managed through Commitizen.

Current bootstrap surface includes:

- Pydantic Settings-based config loading
- datasource registry and sync SQLAlchemy engine factory
- normalized server/schema/table/view inspection service with summaries
- profiling with row counts, distinct/null stats, samples, storage hints, and entity heuristics
- SQL guard service for read-only query analysis and row-limit enforcement
- guarded sync and async query execution
- snapshot persistence with content hashes, relationship edges, inventory indexing, and diffing
- prompt persistence with descriptive system prompts, state seeds, and Markdown companions
- document export from stored snapshots into retrieval-ready bundles
- diagram export from stored snapshots into Mermaid and graph bundles
- Qdrant-backed retrieval over stored snapshot documents with cached embeddings
- LangChain, LangGraph, and FastMCP adapter factories
- LangGraph agent builders with memory or Postgres-backed checkpointing
- LangChain v1 middleware for dynamic prompting, todo tracking, tool handling, state seeding, and optional HITL / summarization
- CLI commands:
  - `sqldbagent config validate`
  - `sqldbagent inspect server`
  - `sqldbagent inspect databases`
  - `sqldbagent inspect schemas`
  - `sqldbagent inspect tables`
  - `sqldbagent inspect table`
  - `sqldbagent profile table`
  - `sqldbagent profile sample`
  - `sqldbagent query lint`
  - `sqldbagent query guard`
  - `sqldbagent query run`
  - `sqldbagent query run-async`
  - `sqldbagent snapshot create`
  - `sqldbagent snapshot list`
  - `sqldbagent snapshot latest`
  - `sqldbagent snapshot diff`
  - `sqldbagent diagram schema`
  - `sqldbagent diagram from-snapshot`
  - `sqldbagent docs export`
  - `sqldbagent docs export-from-snapshot`
  - `sqldbagent prompt export`
  - `sqldbagent prompt export-from-snapshot`
  - `sqldbagent rag index`
  - `sqldbagent rag query`
  - `sqldbagent mcp serve`
- `Makefile` targets for unit, integration, and E2E workflows

Local integration services are intended to be raised with `make up` and stopped
with `make down`.

Saved snapshots now live under `var/sqldbagent/snapshots/<datasource>/<schema>/` with an
`index.json` inventory, so multiple server/schema contexts can be stored and reloaded
without re-introspecting immediately.

Saved document exports now live under `var/sqldbagent/documents/<datasource>/<schema>/`,
and retrieval manifests live under `var/sqldbagent/vectorstores/<datasource>/<schema>/`.
That keeps snapshot documents, cached embeddings, and vector indexing durable and reloadable.

Saved prompt bundles now live under `var/sqldbagent/prompts/<datasource>/<schema>/`.
Each prompt export persists both a JSON bundle and a Markdown companion so prompt
context, state seeding, and system-prompt text can be reviewed or reused later.

Retrieval is intentionally an additive helper, not the primary product shape. The core
workflow is still inspect -> profile -> snapshot -> safe query. Qdrant-backed retrieval
sits beside that so agents and operators can reuse stored schema context before hitting
the live database again.

When agent persistence is enabled, local Postgres is the default LangGraph checkpoint
target for demos and local development. In real deployments, the checkpoint database
should usually be a separate Postgres instance or database from the inspected datasource.

`langgraph.json` now points at the local package root, so `langgraph dev` can use
`pyproject.toml` as the dependency source instead of repeating package names in the
LangGraph config.

FastMCP serving is also settings-driven now. `sqldbagent mcp serve` defaults to the
transport and host/port/path values in `.env`, with CLI flags available for overrides.

Datasource aliases can be provided with `SQLDBAGENT_DATASOURCE_ALIASES` as JSON,
for example `{"demo":"postgres_demo","pg":"postgres"}`. This keeps CLI and
agent-facing names short without changing canonical datasource IDs on disk.

Implementation details, module boundaries, and milestone deliverables live in [docs/implementation-roadmap.md](/Users/will/Projects/sqldbagent/docs/implementation-roadmap.md).

Maintainer and agent operating notes live in [AGENTS.md](/Users/will/Projects/sqldbagent/AGENTS.md) and [docs/\_internal/README.md](/Users/will/Projects/sqldbagent/docs/_internal/README.md).
