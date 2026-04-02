# sqldbagent

Service-first database intelligence for safe inspection, profiling, snapshotting, guarded querying, retrieval preparation, and agent-facing execution over relational databases.

```{note}
The public docs focus on the product and operator surface. Working notes, experiments, and repo memory stay in `docs/_internal/`.
```

````{grid} 2
:gutter: 2

```{grid-item-card} Safe by Default
Every agent-facing query goes through guardrails, row limits, and read-only enforcement before execution.
```

```{grid-item-card} One Core, Many Surfaces
CLI, dashboard, MCP, LangChain, and LangGraph all sit on top of the same normalized metadata and service layer.
```

```{grid-item-card} Durable Artifacts
Snapshots, docs, diagrams, prompts, and retrieval indexes are stored so context can be reloaded without re-introspection.
```

```{grid-item-card} Built for Real Databases
The initial target is Postgres and MSSQL, with SQLite used as a lightweight smoke and local E2E target.
```
````

## Architecture

```{mermaid}
flowchart LR
    A["Datasources<br/>Postgres, MSSQL, SQLite"] --> B["Engines + Safety"]
    B --> C["Normalized Metadata Core"]
    C --> D["Snapshot + Profile + Diagram + Docs"]
    D --> E["CLI"]
    D --> F["Dashboard"]
    D --> G[MCP]
    D --> H["LangChain / LangGraph"]
    H --> I["LangSmith Tracing"]
```

```{toctree}
:maxdepth: 2
:caption: Guide

getting-started
configuration
agent-stack
cli
development
publishing
reference/index
```
