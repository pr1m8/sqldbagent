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
