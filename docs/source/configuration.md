# Configuration

sqldbagent is configured with Pydantic Settings and `.env`, with nested settings exposed under the `SQLDBAGENT_` prefix.

## Core Areas

- Datasources: direct `datasources` config or convenience Postgres, Postgres demo, MSSQL, and SQLite fields.
- Agent orchestration: model selection, middleware controls, tool limits, checkpoint persistence, and long-term memory store behavior.
- Retrieval: Qdrant connection details, collection naming, and search defaults.
- LangSmith: tracing enablement, project naming, workspace selection, and default tags.
- Prompt/runtime ergonomics: prompt enhancement toggles, `tiktoken`-backed token estimation with deterministic fallback, and live explored context persisted under the artifact root.

## Datasource Convenience Fields

The standard local variables are:

```text
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD

POSTGRES_DEMO_HOST
POSTGRES_DEMO_PORT
POSTGRES_DEMO_DB
POSTGRES_DEMO_USER
POSTGRES_DEMO_PASSWORD

MSSQL_HOST
MSSQL_PORT
MSSQL_DATABASE
MSSQL_USER
MSSQL_PASSWORD

SQLITE_PATH
```

## LangGraph Checkpointing

Use Postgres checkpointing for durable agent threads across runs:

```text
SQLDBAGENT_AGENT_CHECKPOINT_BACKEND=postgres
SQLDBAGENT_AGENT_CHECKPOINT_AUTO_SETUP=true
SQLDBAGENT_AGENT_CHECKPOINT_PIPELINE=false
```

If an explicit checkpoint URL is not provided, sqldbagent synthesizes one from the standard `POSTGRES_*` fields.

## Query Safety Defaults

- Datasources default to read-only execution behavior.
- Writable execution is only available when the datasource safety policy enables it explicitly through `allow_writes=true` and the caller requests writable access.
- Postgres uses read-only transactions, SQLite uses `PRAGMA query_only`, and MSSQL requests `ApplicationIntent=ReadOnly` while still relying on the shared SQL guard as the hard boundary.

## Prompt Artifacts

- Prompt bundles and prompt enhancements are stored under the artifact root.
- Prompt exports cache token estimates for the base prompt, final prompt, enhancement text, and prompt delta.
- Prompt enhancement artifacts also cache per-layer estimates for generated context, live explored context, user context, business rules, direct effective-prompt instructions, and answer-style guidance.
- Live prompt exploration can save additional read-only discovered context back into the enhancement artifact for the same datasource/schema.

## LangSmith Tracing

LangSmith tracing is optional and local-key friendly:

```text
SQLDBAGENT_LANGSMITH__TRACING=true
SQLDBAGENT_LANGSMITH__PROJECT=sqldbagent-dev
SQLDBAGENT_LANGSMITH__TAGS=sqldbagent,local,dashboard
LANGSMITH_API_KEY=...
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_WORKSPACE_ID=...
```

When `langgraph.json` points at `.env`, the same tracing config is available to `langgraph dev` and dashboard turns without duplicating configuration.

## Example

See the repo-root `.env.example` for the supported local shape.
