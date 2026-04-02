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
- [agents/README.md](/Users/will/Projects/sqldbagent/docs/_internal/agents/README.md): internal index for general agent-platform guidance and `sqldbagent`-specific agent notes
- [agent-architecture.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-architecture.md): `sqldbagent`-specific LangChain v1 / LangGraph notes, agent boundaries, and checkpointing decisions
- [agent-platform-kit/README.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/README.md): moveable blueprint for a reusable LangChain v1 / LangGraph / LangSmith agent platform
- [agent-platform-kit/07-pragmatic-recipes.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/07-pragmatic-recipes.md): copy-pastable setup patterns for runtime, middleware, persistence, retrieval, and deployment
- [agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md): self-contained moveable skill bundle for reusable agent-platform work
- [dashboard/README.md](/Users/will/Projects/sqldbagent/docs/_internal/dashboard/README.md): internal home for the Streamlit dashboard surface
- [dashboard/streamlit-dashboard.md](/Users/will/Projects/sqldbagent/docs/_internal/dashboard/streamlit-dashboard.md): dashboard behavior, boundaries, and debugging notes
- [handoff/README.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/README.md): repo-local handoff process for moving work between chats and agents
- [handoff/current.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/current.md): current cross-chat working context
- [memory.md](/Users/will/Projects/sqldbagent/docs/_internal/memory.md): stable repo memory rules and what should be persisted
- [skills.md](/Users/will/Projects/sqldbagent/docs/_internal/skills.md): Codex skills inventory and setup policy
- [testing.md](/Users/will/Projects/sqldbagent/docs/_internal/testing.md): local DB targets and Compose-based integration guidance

Promote content into public docs once it becomes stable product behavior rather than maintainer-only process.
