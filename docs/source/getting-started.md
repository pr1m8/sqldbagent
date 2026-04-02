# Getting Started

## Install

With PDM:

```bash
pdm install -G :all
```

With pip:

```bash
pip install "sqldbagent[cli,postgres,langchain,langgraph,mcp,dashboard,docs,test]"
```

## Start Local Infra

```bash
make up
make demo-migrate
```

That raises the local integration stack declared in `infra/compose.integration.yaml`, including the demo Postgres database and Qdrant.

## Common First Commands

```bash
pdm run sqldbagent config validate
pdm run sqldbagent inspect tables postgres_demo --schema public
pdm run sqldbagent snapshot create postgres_demo public
pdm run sqldbagent profile unique-values postgres_demo customers segment --schema public
pdm run sqldbagent prompt export postgres_demo public
make dashboard-demo
```

The demo dashboard prefers durable Postgres checkpointing and durable Postgres-backed long-term memory when local persistence configuration is present, and it will tell you when it has to fall back to session-only memory.

The current dashboard flow gives you:

- chat over the persisted LangGraph-backed agent
- schema inspection through an interactive graph plus a generated image fallback
- prompt review with token-budget breakdowns
- live prompt exploration that saves additional database context back into the prompt artifact
- retrieval-index management for the active saved snapshot
- guarded query execution with read-only default behavior

## What to Expect

- Snapshots are stored under `var/sqldbagent/snapshots/<datasource>/<schema>/`.
- Document bundles are stored under `var/sqldbagent/documents/<datasource>/<schema>/`.
- Prompt bundles are stored under `var/sqldbagent/prompts/<datasource>/<schema>/`.
- Retrieval manifests are stored under `var/sqldbagent/vectorstores/<datasource>/<schema>/`.

## Recommended Local Flow

1. Inspect and snapshot a schema.
2. Export docs, diagrams, and prompt context from the stored snapshot.
3. Optionally build retrieval indexes for snapshot documents.
4. Use the dashboard, MCP server, or LangGraph runtime against those stored artifacts before hitting the live database again.
5. Use live prompt exploration only when you want to enrich the stored prompt with current high-signal categorical values or join hints from read-only profiling.
