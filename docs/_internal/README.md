# Internal Docs

This folder is the maintainer and agent working area for `sqldbagent`.

It exists to capture:

- bootstrap steps
- local setup conventions
- MCP server inventory
- Codex skill inventory
- architecture notes that are still stabilizing
- implementation checklists before they are promoted into public docs

## What Belongs Here

- setup instructions for local tools that are not part of normal package installation
- decision records that are still evolving
- contributor notes for internal workflows
- templates and inventories for local machine capabilities

## What Does Not Belong Here

- secrets or credentials
- personal machine paths that cannot be generalized
- generated outputs
- code that should live under `src/`

## Initial Structure

- [bootstrap.md](/Users/will/Projects/sqldbagent/docs/_internal/bootstrap.md): first-pass setup flow for maintainers
- [mcps.md](/Users/will/Projects/sqldbagent/docs/_internal/mcps.md): MCP inventory and setup policy
- [mcp-servers.md](/Users/will/Projects/sqldbagent/docs/_internal/mcp-servers.md): recommended MCP server rollout and local config shape
- [agent-architecture.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-architecture.md): LangChain v1 / LangGraph notes, agent boundaries, and checkpointing decisions
- [memory.md](/Users/will/Projects/sqldbagent/docs/_internal/memory.md): stable repo memory rules and what should be persisted
- [skills.md](/Users/will/Projects/sqldbagent/docs/_internal/skills.md): Codex skills inventory and setup policy
- [testing.md](/Users/will/Projects/sqldbagent/docs/_internal/testing.md): local DB targets and Compose-based integration guidance

Promote content into public docs once it becomes stable product behavior rather than maintainer-only process.
