# sqldbagent Implementation Roadmap

## Positioning

`sqldbagent` should be built as a service-first database intelligence platform with one normalized metadata core and multiple surfaces on top of it. The first production targets are Postgres and MSSQL. Everything else should hang off stable service contracts rather than dialect-specific or UI-specific code paths.

## Core Rule

Normalized metadata in the middle, dialect enrichers on the edges.

That means:

- dialect packages gather raw metadata and execution details
- core models normalize the result into one internal graph
- services operate on normalized models
- CLI, TUI, MCP, LangChain, and dashboard surfaces call the same services

## Target Package Layout

```text
src/sqldbagent/
  __init__.py
  core/
    config.py
    enums.py
    errors.py
    ids.py
    models/
      catalog.py
      graph.py
      profile.py
      snapshot.py
    serialization.py
  engines/
    base.py
    factory.py
    sync.py
    async_.py
    session.py
  safety/
    models.py
    policies.py
    guard.py
    audit.py
  introspect/
    base.py
    service.py
    normalize.py
  profile/
    base.py
    service.py
    samplers.py
  snapshot/
    bundle.py
    hashing.py
    diff.py
    storage.py
  diagrams/
    mermaid.py
    graph_json.py
  docs/
    markdown.py
    prompt_export.py
    langchain_export.py
  adapters/
    mcp/
    langchain/
    langgraph/
  cli/
    app.py
    inspect.py
    profile.py
    snapshot.py
    query.py
    export.py
  tui/
  dashboard/
  postgres/
    engine.py
    introspect.py
    profile.py
    queries.py
  mssql/
    engine.py
    introspect.py
    profile.py
    queries.py
tests/
  unit/
  integration/
  e2e/
  property/
  golden/
```

## Module Boundaries

### `core`

Owns the normalized internal contract.

- settings and validated config
- canonical metadata models
- shared enums and error types
- JSON and hash-stable serialization helpers

Do not put SQLAlchemy engines, dialect reflection, or CLI logic here.

### `engines`

Owns connection and execution primitives.

- sync and async engine factories
- pool configuration
- read-only connection setup
- chunked and streaming reader helpers
- execution wrappers with timeout and retry hooks

This layer should expose small protocol-oriented contracts that dialect packages can plug into.

### `introspect`

Owns reflection orchestration and normalization.

- raw metadata collection contracts
- normalized metadata assembly
- relationship graph construction
- service entry points such as `inspect_server`, `inspect_schema`, and `describe_table`

Dialect packages should return raw facts; this layer translates them into core models.

### `profile`

Owns statistics, samples, and semantic hints.

- cheap profile: counts, keys, indexes, row estimates, sample rows
- standard profile: null ratios, distinct estimates, top values, min/max
- deep profile: joinability hints, weak keys, anomaly flags, likely PII signals

Keep deep heuristics isolated so they can evolve without destabilizing cheap/standard flows.

### `snapshot`

Owns durable bundles and comparisons.

- snapshot manifest and provenance
- stable hashing
- artifact layout for raw metadata, profiles, samples, docs, diagrams, prompts
- diffing between snapshots

Snapshots should be a first-class product artifact, not an afterthought.

### `safety`

Owns every agent-facing SQL control.

- SQL parsing and AST checks
- single-statement enforcement
- read-only policy
- allow/deny rules
- row-limit injection or enforcement
- timeout policy
- execution audit metadata

Any path that executes user-supplied SQL must pass through this layer.

### `diagrams` and `docs`

Own rich exports from normalized metadata.

- Mermaid ERD generation
- graph JSON export
- markdown schema docs
- prompt-ready context blocks
- LangChain `Document` exports

These modules should consume normalized models only, never live database handles.

### `postgres` and `mssql`

Own dialect-specific enrichers and queries.

- engine-specific setup
- reflection queries
- storage metadata queries
- dialect capability flags
- profile optimizations where the database can do the work cheaply

Keep SQL text and metadata peculiarities here.

### `adapters`

Own integration surfaces over shared services.

- FastMCP tools
- LangChain tool wrappers
- LangGraph nodes and workflow helpers

Adapters should be thin and stateless.

### `cli`, `tui`, `dashboard`

Own presentation only.

- argument parsing and output formatting
- interactive navigation
- visualization workflows

These modules should assemble service calls, not implement business logic.

## Dependency and Extras Strategy

The existing extras are close to the right shape. Tighten them as follows:

- base package: `pydantic`, `pydantic-settings`, `sqlalchemy`, `orjson`, `tenacity`, `networkx`, `jinja2`, `pyyaml`
- `postgres`: `psycopg`
- `mssql`: `pyodbc`, `aioodbc`
- `cli`: `typer`, `rich`
- `tui`: `textual`, `rich`
- `dashboard`: keep Python-first; current `streamlit` stack is acceptable for an internal dashboard
- `langchain`: `langchain`, `langchain-core`, `langchain-community`
- `langgraph`: `langgraph`, `langgraph-sdk`, `langgraph-checkpoint-postgres`
- `mcp`: `fastmcp`
- `lint`: `ruff`, `sqlfluff`, `pre-commit`
- `test`: `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-xdist`, `hypothesis`
- add Commitizen to the maintainer toolchain for conventional commits

Recommended additions:

- base or safety extra: `sqlglot`
- optional packaging convenience extras:
  - `all`: all runtime surfaces
  - `dev`: `test + lint + typecheck + docs + cli + tui`

## Service Contracts

Build around a small set of stable services.

- `DatasourceRegistry`: resolves datasource config by name
- `EngineManager`: creates sync/async engines and guarded execution contexts
- `InspectionService`: server/database/schema/table introspection entry points
- `ProfilingService`: cheap/standard/deep profiling entry points
- `SnapshotService`: create/load/diff snapshot bundles
- `ExportService`: markdown, prompt, Mermaid, graph JSON, LangChain documents
- `QueryGuardService`: lint, validate, rewrite limits, audit execution metadata

If these contracts stay clean, the surfaces remain cheap to build.

## Milestones

### Milestone 0: project bootstrap

Deliver:

- real package metadata and README
- base directory structure
- settings skeleton
- error model
- shared typing and serialization helpers
- CI hooks for lint, typecheck, and tests

Exit criteria:

- package installs with selected extras
- test and lint entry points are wired
- docs explain architecture and phases

### Milestone 1: connection and inspection foundation

Deliver:

- datasource config and factories
- sync engine support for Postgres and MSSQL
- read-only session policy
- normalized catalog models
- server/database/schema/table inspection services
- CLI commands:
  - `config validate`
  - `inspect server`
  - `inspect databases`
  - `inspect schemas`
  - `inspect table`

Exit criteria:

- can connect to both dialects
- can inspect tables into normalized models
- can export raw inspection payloads as JSON

### Milestone 2: profiling and snapshots

Deliver:

- sample and profile services
- snapshot bundle format
- relationship graph generation
- snapshot storage and diffing
- CLI commands:
  - `profile table`
  - `sample table`
  - `snapshot create`
  - `snapshot diff`

Exit criteria:

- a schema can be captured as a reproducible snapshot bundle
- repeated snapshots generate stable hashes where metadata is unchanged
- diff output is readable and testable

### Milestone 3: safety and exports

Deliver:

- SQL guard service with AST inspection
- single-statement and read-only enforcement
- row limit and timeout policy
- markdown docs export
- Mermaid ERD export
- prompt export
- LangChain `Document` export
- CLI commands:
  - `query lint`
  - `query guard`
  - `query run`
  - `diagram schema`
  - `docs export`
  - `prompt export`

Exit criteria:

- agent-facing SQL cannot bypass guardrails through the supported surfaces
- schema artifacts are retrieval-ready

### Milestone 4: interactive and integration surfaces

Deliver:

- Textual TUI
- FastMCP server and tool set
- LangChain tool wrappers
- LangGraph workflow nodes

Exit criteria:

- same inspection/profile/snapshot/query services are reachable from CLI and at least one adapter surface without duplicate logic

### Milestone 5: dashboard and advanced intelligence

Deliver:

- internal Python dashboard
- semantic annotations
- join suggestions
- drift detection
- documentation coverage scoring
- retrieval-prep helpers for self-query workflows

Exit criteria:

- advanced intelligence features operate over stable snapshots and normalized metadata rather than raw live queries

## Test Strategy by Phase

### Unit

Prioritize early:

- settings validation
- URL/DSN assembly
- normalized model validation
- metadata graph invariants
- Mermaid and markdown export determinism
- snapshot hashing and diff stability
- safety policy decisions

### Integration

Run against real Postgres and MSSQL containers:

- reflection and enrichment
- read-only enforcement
- profile queries
- snapshot creation and diffing
- dialect capability flags

SQLite may be used for narrow smoke coverage of generic service and CLI wiring, but it is not a target dialect and should not be used to validate dialect-specific normalization or safety behavior.

### E2E

Add once the surface exists:

- CLI command flows
- TUI smoke paths
- MCP tool calls
- later dashboard API flows

### Property and fuzz

Use for:

- SQL safety normalization
- graph invariants
- snapshot diff stability

### Golden

Snapshot outputs for:

- markdown exports
- Mermaid diagrams
- prompt blocks
- LangChain document payloads
- CLI output rendering

## Sequencing Rules

Use these rules to avoid architectural drift:

- normalize metadata before building exports
- ship CLI before TUI or dashboard
- ship safety before agent adapters expose query execution
- keep dialect logic out of surface modules
- make snapshot bundles stable before adding advanced intelligence
- prefer Python-first dashboarding until contracts and UX stabilize

## Immediate Next Tasks

The highest-value implementation sequence from the current repo state is:

1. Replace the placeholder package metadata and README copy with architecture-aware project docs.
2. Create the package directories and minimal `__init__.py` files for the target module layout.
3. Implement `core.config`, `core.errors`, and canonical metadata models.
4. Implement engine factories and datasource registry.
5. Add Postgres and MSSQL inspection adapters with one normalized `describe_table` flow.
6. Expose those flows through a Typer CLI before building any higher-level UI.

This keeps the first code path narrow, testable, and reusable by every later surface.
