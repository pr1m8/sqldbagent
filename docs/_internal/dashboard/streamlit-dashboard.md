# Streamlit Dashboard

## Purpose

The dashboard is the current human-facing chat surface over the persisted
LangGraph-backed `sqldbagent` agent.

It is intentionally a thin surface over shared services rather than a separate
frontend architecture.

## Current Role

The dashboard is where operators can:

- chat against a datasource and schema context
- reuse and rename saved threads
- inspect prompt and effective-prompt state
- edit prompt enhancement context
- ensure or rebuild retrieval for the active snapshot
- inspect schema diagrams and fallback images
- run guarded read-only SQL through the shared query layer
- inspect local usage and audit artifacts for recent agent turns and guarded
  queries

## Important Rules

- the dashboard must not bypass the shared safety/query services
- the dashboard must report the effective checkpoint backend, not just the
  configured one
- the dashboard should prefer persisted artifacts over re-querying when those
  artifacts already satisfy the workflow
- prompt composition logic should stay in shared prompt services and middleware,
  not in Streamlit callbacks
- dashboard thread state should remain reloadable through shared services, not
  transient UI-only storage

## Current UX Expectations

- chat turns should stream meaningful progress instead of showing one long
  blocking spinner
- example questions should disappear once a real user turn is underway
- saved threads should support optional human-friendly names
- new datasource or schema contexts should offer a lightweight onboarding or
  annotation path
- schema rendering should have a reliable server-rendered image fallback when
  Mermaid rendering is flaky
- retrieval controls should resolve the active snapshot from persisted artifacts
  when the thread state is sparse
- usage and audit views should read from append-only local artifacts so they
  still work when LangSmith is disabled or unavailable

## Usage And Audit Tab

The dashboard exposes local observability in a `Usage` tab backed by
`sqldbagent.observability`.

Current artifact layout:

- `var/sqldbagent/audit/events/YYYY-MM-DD.jsonl` for audit events
- `var/sqldbagent/audit/usage/YYYY-MM-DD.jsonl` for model and tool usage events

Current coverage:

- dashboard agent turns record `agent.run_turn` audit events
- dashboard guarded queries record `query.execute` audit events
- LangChain message `usage_metadata` is extracted into model usage events when
  providers expose token counts
- tool messages are recorded with tool name, status, and output size
- the UI shows summary cards, usage/audit tables, and a small Plotly event-kind
  chart

Important limitations:

- cost fields are present but pricing is currently marked `not_configured`
- custom model pricing belongs in the later LLM registry slice
- artifact recording is best-effort and must never change SQL execution
  semantics
- local artifacts complement LangSmith; they do not replace trace debugging

## Persistence Expectations

Preferred order:

1. Postgres checkpoint backend
2. Postgres-backed long-term store
3. session-scoped in-memory fallback only when durable persistence is not
   available

The UI should explain when it is using a fallback.

## Local Commands

```bash
make dashboard-demo
pdm run sqldbagent dashboard serve --datasource postgres_demo --schema public
trunk check --fix
pdm run pytest tests/unit tests/e2e tests/integration -q
```

## Common Debugging Notes

- if the dashboard still shows old behavior, restart the Streamlit process
- stale Streamlit processes can make new code look broken when the code is
  already fixed on disk
- schema rendering issues should degrade to the server-rendered image path, not
  leave the dashboard unusable
- retrieval status should come from persisted artifacts or manifests, not only
  the live thread state
- usage tab rows come from local JSONL artifacts; if they are missing, run an
  agent turn or guarded query first

## Boundary With General Agent Docs

If the note is about:

- `ToolRuntime`
- middleware design
- checkpointer vs store
- deployment via LangGraph CLI
- skill-set or runtime-profile abstractions

it belongs in the general agent-platform material instead:

- [agent-platform-kit/README.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/README.md)
- [agent-platform-foundations skill bundle](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md)
