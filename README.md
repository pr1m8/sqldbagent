# sqldbagent

[![CI](https://github.com/pr1m8/sqldbagent/actions/workflows/ci.yml/badge.svg)](https://github.com/pr1m8/sqldbagent/actions/workflows/ci.yml)
[![Docs](https://github.com/pr1m8/sqldbagent/actions/workflows/docs.yml/badge.svg)](https://github.com/pr1m8/sqldbagent/actions/workflows/docs.yml)
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
- guarded sync and async SQL execution
- snapshot persistence with per-datasource and per-schema storage
- snapshot diffing, docs export, Mermaid ER export, and prompt export
- Qdrant-backed retrieval over stored snapshot documents
- LangChain tools and LangGraph agent builders with middleware, checkpointing, and optional LangSmith tracing
- FastMCP server surface
- Streamlit dashboard chat surface over the same persisted agent stack

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
pdm run sqldbagent prompt export postgres_demo public
make dashboard-demo
```

## Agent Stack

sqldbagent uses LangChain v1's `create_agent(...)` surface on top of LangGraph runtime primitives.

- state is seeded from stored snapshots
- middleware owns prompt injection, tool handling, summarization, HITL, and limits
- Postgres checkpointing is the durable thread path
- the dashboard uses a session-scoped memory saver when Postgres checkpointing is not enabled
- LangSmith tracing is optional and `.env`-driven

`langgraph.json` points at the local project root and `.env`, so `langgraph dev` uses the same package and tracing configuration as the rest of the repo.

## Documentation

Public docs live in [`docs/source`](docs/source), internal repo memory lives in [`docs/_internal`](docs/_internal), and the main contributor rules live in [`AGENTS.md`](AGENTS.md).

Useful entrypoints:

- [Getting Started](docs/source/getting-started.md)
- [Configuration](docs/source/configuration.md)
- [Agent Stack](docs/source/agent-stack.md)
- [Publishing](docs/source/publishing.md)

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
