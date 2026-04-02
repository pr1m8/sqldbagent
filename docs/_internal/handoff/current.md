# Current Handoff

## Snapshot

- date: 2026-04-02
- branch: `main`
- package release line: `0.1.4`
- repo mode: service-first database intelligence platform with reusable
  LangChain v1 / LangGraph agent surfaces

## Project Goal

`sqldbagent` is being built as a safe, dialect-extensible database intelligence
platform. The center of the system is a normalized metadata and artifact layer,
with Postgres and MSSQL enrichers on the edges and thin surfaces on top:
CLI, dashboard, MCP, LangChain, LangGraph, and later TUI.

The current implementation direction is not just "talk to a database". It is:

- inspect and normalize database structure
- persist snapshots and prompt artifacts
- enforce guarded read-only SQL by default
- support retrieval over stored artifacts
- expose that through agent-ready interfaces
- keep the reusable agent-platform ideas portable beyond this repo

## Done

- normalized inspection, profiling, sampling, snapshots, prompt artifacts, and
  guarded query execution are implemented
- dashboard supports persisted chat, prompt editing, retrieval controls, query
  execution, schema views, and thread selection
- LangChain and LangGraph adapter layers exist and are wired into the shared
  services
- Qdrant-backed retrieval is integrated as an additive helper over stored
  snapshot documents
- prompt enhancement and prompt token budgeting are persisted and visible
- reusable agent-platform guidance now exists in:
  - [docs/\_internal/agent-platform-kit/README.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/README.md)
  - [docs/\_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md)

## In Progress

- uncommitted docs work:
  - new internal handoff folder
  - moveable agent-platform blueprint
  - skill-style bundle for reusable agent-platform guidance
- uncommitted code fix:
  - LangChain tools now hide `ToolRuntime` from JSON schemas using
    `InjectedToolArg`
  - regression coverage added in
    [tests/unit/test_adapters.py](/Users/will/Projects/sqldbagent/tests/unit/test_adapters.py)

## Hot Files

- [AGENTS.md](/Users/will/Projects/sqldbagent/AGENTS.md)
- [docs/\_internal/memory.md](/Users/will/Projects/sqldbagent/docs/_internal/memory.md)
- [docs/\_internal/handoff/README.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/README.md)
- [docs/\_internal/handoff/current.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/current.md)
- [docs/\_internal/agent-platform-kit/README.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/README.md)
- [docs/\_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md)
- [src/sqldbagent/adapters/langchain/tools.py](/Users/will/Projects/sqldbagent/src/sqldbagent/adapters/langchain/tools.py)
- [tests/unit/test_adapters.py](/Users/will/Projects/sqldbagent/tests/unit/test_adapters.py)

## Commands To Know

```bash
make up
make dashboard-demo
make langgraph-dev-demo
pdm run pytest tests/unit tests/e2e tests/integration -q
trunk check --fix
```

## Validation Status

- `trunk check --fix` on the new blueprint, skill-bundle, and handoff docs:
  clean
- `pdm run pytest --no-cov tests/unit/test_adapters.py -q`: `5 passed`

## Known Caveats

- there are active uncommitted changes in the working tree
- dashboard restarts may still be needed when Streamlit is holding stale code
- MSSQL is not the strongest end-to-end path yet compared with Postgres and the
  demo flow

## Best Next Steps

1. commit the LangChain runtime-schema fix separately from the docs and handoff
   work
2. commit the agent-platform blueprint and skill bundle as a docs slice
3. commit the new handoff folder as a docs/process slice, or fold it into the
   blueprint docs commit if you want fewer commits
4. continue with either:
   - reusable `agentkit` extraction inside this repo, or
   - deeper MSSQL/live retrieval/runtime work

## Notes For The Next Chat

Start by trusting the repo-local handoff and memory files over trying to infer
everything from old chat history. If the task is generalized agent-platform
work, use the moveable skill bundle rather than scattering new notes across
random docs.
