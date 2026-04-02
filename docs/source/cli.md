# CLI

The CLI is the first-class operator surface for sqldbagent.

## Core Command Groups

- `sqldbagent config validate`
- `sqldbagent inspect ...`
- `sqldbagent profile ...`
- `sqldbagent profile unique-values ...`
- `sqldbagent query ...`
- `sqldbagent snapshot ...`
- `sqldbagent diagram ...`
- `sqldbagent docs ...`
- `sqldbagent prompt ...`
- `sqldbagent rag ...`
- `sqldbagent dashboard serve`
- `sqldbagent mcp serve`

## Demo Helpers

The repository `Makefile` exposes a local demo flow:

```bash
make demo-up
make demo-inspect
make demo-snapshot
make demo-prompt
make demo-rag-index
make demo-rag-query
make dashboard-demo
```

`make dashboard-demo` prefers durable Postgres checkpointing and durable Postgres-backed long-term memory for demo threads when the local persistence configuration is available.

## Query Posture

- `sqldbagent query run` and `sqldbagent query run-async` default to guarded read-only execution.
- Both query commands expose `--access-mode read_only|writable`.
- Writable execution is supported only when the datasource safety policy enables it and the caller requests it explicitly.
- The dashboard query tab follows the same shared query service and safety layer instead of bypassing it.

## Prompt And Retrieval Workflow

- `sqldbagent prompt export` writes durable JSON and Markdown prompt artifacts for the latest saved snapshot.
- `sqldbagent prompt enhancement show` and `sqldbagent prompt enhancement save` let you review or persist per-schema prompt context outside the dashboard.
- Prompt artifacts include cached token estimates so prompt size can be reviewed before agent use.
- `sqldbagent profile unique-values ...` is the fast operator surface for categorical-value inspection and the same profile signal used by prompt exploration.
- Retrieval indexes are built from saved snapshot documents, not from ad hoc live query results.
