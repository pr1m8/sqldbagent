# sqldbagent

[![CI](https://github.com/pr1m8/sqldbagent/actions/workflows/ci.yml/badge.svg)](https://github.com/pr1m8/sqldbagent/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sqldbagent.svg)](https://pypi.org/project/sqldbagent/)
[![Docs](https://readthedocs.org/projects/sqldbagent/badge/?version=latest)](https://sqldbagent.readthedocs.io/en/latest/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-0f766e.svg)](https://www.python.org/downloads/)
[![PDM](https://img.shields.io/badge/deps-pdm-334155.svg)](https://pdm-project.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-115e59.svg)](LICENSE)

Safe database intelligence for agents, operators, and automation.

sqldbagent is a service-first platform for understanding relational databases through normalized metadata, durable artifacts, guarded querying, and agent-ready surfaces. It starts with Postgres and MSSQL, uses SQLite as a lightweight smoke/E2E target, and keeps the shared service layer authoritative across every interface.

## Why This Exists

Most database tooling gives you one of two extremes:

- a thin SQL shell with no meaningful safety boundary
- a one-off schema export with no reusable runtime context

sqldbagent is trying to sit in the middle:

- inspect and normalize database structure once
- store snapshots, profiles, docs, diagrams, prompts, and retrieval indexes durably
- let CLI workflows, dashboards, MCP tools, and LangGraph agents reuse that context
- keep all agent-facing SQL behind an explicit read-only safety layer

## Core Shape

The architecture rule is:

### Normalized Metadata Core In The Middle, Dialect Enrichers On The Edges

That means:

- shared models for databases, schemas, tables, views, columns, relationships, profiles, and snapshots
- Postgres and MSSQL adapters for dialect-specific introspection and execution details
- thin surfaces on top: CLI, dashboard, MCP, LangChain, and LangGraph

## Current Capabilities

- datasource config and engine factories through Pydantic Settings and `.env`
- normalized inspection of servers, schemas, tables, and views
- profiling with row counts, distinct/null stats, samples, storage hints, and entity heuristics
- distinct-value lookup as a first-class profile surface for categorical columns
- guarded sync and async SQL execution with a read-only default and explicit opt-in writable mode when datasource policy allows it
- snapshot persistence with per-datasource and per-schema storage
- snapshot diffing, docs export, Mermaid ER export, and prompt export
- prompt-enhancement artifacts that merge DB-aware guidance, saved user context, live explored context, and cached token budgets
- Qdrant-backed retrieval over stored snapshot documents
- LangChain tools and LangGraph agent builders with dialect-aware runtime context, middleware, checkpointing, long-term store memory, and optional LangSmith tracing
- FastMCP server surface
- Streamlit dashboard chat surface with chat, schema diagram, prompt review, retrieval management, query execution, token budgets, and saved-thread reuse over the same persisted agent stack
- streamed dashboard turn progress, optional thread naming, and first-run annotation capture for new datasource/schema contexts

## Install

With PDM:

```bash
pdm install -G :all
```

With pip:

```bash
pip install "sqldbagent[cli,postgres,langchain,langgraph,mcp,dashboard,docs,test]"
```

## Local Demo

Bring up the local integration stack and migrate the demo database:

```bash
make up
make demo-migrate
```

Run the common workflow:

```bash
pdm run sqldbagent inspect tables postgres_demo --schema public
pdm run sqldbagent snapshot create postgres_demo public
pdm run sqldbagent profile unique-values postgres_demo customers segment --schema public
pdm run sqldbagent prompt export postgres_demo public
make langgraph-dev-demo
make dashboard-demo
```

The dashboard includes:

- a persisted chat tab over the guarded agent stack
- streamed progress updates while the agent is planning, calling tools, and finalizing the answer
- snapshot-aware example questions to help start a useful conversation quickly
- a schema tab with an interactive graph, a generated PNG/SVG schema-image fallback, Mermaid source, and Graphviz structural view
- a prompt tab for reviewing the base/effective prompt, saving prompt context, regenerating schema-aware prompt guidance on demand, and running live prompt exploration against the active database
- the prompt tab can also inject additional effective-prompt instructions that are stored per datasource/schema and merged into the final system prompt
- a token-budget view for the base prompt, final prompt, enhancement layers, and live explored context
- a retrieval tab for loading or rebuilding the active snapshot's vector index when you want retrieval ready before first use, using the latest saved snapshot even when the thread state is still sparse
- a query tab for guarded sync/async SQL with explicit access-mode selection and a read-only default
- a threads tab plus sidebar selector for reopening saved conversations
- optional saved thread names so important conversations are easier to reopen later
- a sidebar onboarding form for initial datasource/schema annotations when the context is still new

## Agent Stack

sqldbagent uses LangChain v1's `create_agent(...)` surface on top of LangGraph runtime primitives.

- state is seeded from stored snapshots
- middleware owns prompt injection, stored prompt-enhancement merging, tool handling, summarization, HITL, and limits
- prompt bundles and prompt enhancements cache token estimates so prompt size can be reviewed before agent runs
- Postgres checkpointing is the durable thread path
- Postgres-backed LangGraph store memory can persist datasource/schema context, remembered notes, and prompt instructions across threads
- `make dashboard-demo` and `make langgraph-dev-demo` prefer the Postgres checkpoint plus Postgres store path for durable demo memory and fall back to a session store only when store config is unavailable
- the dashboard still uses the guarded read-only database path while it streams turn progress in the UI
- Postgres gets connection-level read-only sessions; MSSQL uses guarded SQL plus `ApplicationIntent=ReadOnly` on ODBC-style connections when datasource safety is read-only
- writable SQL is still exceptional: it must be requested explicitly and only works when datasource policy enables writes
- LangSmith tracing is optional and `.env`-driven

`langgraph.json` points at the local project root and `.env`, so `langgraph dev` uses the same package and tracing configuration as the rest of the repo.

Useful LangGraph make targets:

- `make langgraph-dev` for the local API server with repo defaults
- `make langgraph-dev-demo` to run the API server against `postgres_demo`
- `make langgraph-debug` to wait for a debugger client before startup
- `make langgraph-up` for the Dockerized LangGraph API server
- `make langgraph-build` to build the LangGraph API image
- `make langgraph-test` for the runtime and checkpoint integration tests

## Documentation

Public docs live at [sqldbagent.readthedocs.io](https://sqldbagent.readthedocs.io/en/latest/), internal repo memory lives in [`docs/_internal`](docs/_internal), and the main contributor rules live in [`AGENTS.md`](AGENTS.md).

Useful entrypoints:

- [Getting Started](https://sqldbagent.readthedocs.io/en/latest/getting-started.html)
- [Configuration](https://sqldbagent.readthedocs.io/en/latest/configuration.html)
- [Agent Stack](https://sqldbagent.readthedocs.io/en/latest/agent-stack.html)
- [Publishing](https://sqldbagent.readthedocs.io/en/latest/publishing.html)

Build docs locally:

```bash
make docs
make docs-live
```

## Development

```bash
trunk check --fix
make test
make test-integration
make test-e2e
```

## Publishing

```bash
make build
make publish-check
make publish-testpypi
make publish-pypi
```

The repo also includes GitHub Actions workflows for CI, docs builds, and trusted-publisher PyPI releases on version tags.
