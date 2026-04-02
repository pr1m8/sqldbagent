# Agent Docs

This folder is the internal home for agent-related architecture and operating
notes.

Use it to separate:

- general reusable agent-platform guidance
- `sqldbagent`-specific agent decisions
- repo-specific UI or surface notes that sit on top of the agent stack

## Reading Order

### General Reusable Platform Guidance

Start here when the work is about reusable LangChain v1 / LangGraph patterns
that could move into another repo or package:

- [agent-platform-kit/README.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/README.md)
- [agent-platform-foundations skill bundle](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md)

### `sqldbagent`-Specific Agent Guidance

Use these when the work is specific to this repo's SQL-safe agent surface:

- [agent-architecture.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-architecture.md)
- [implementation-roadmap.md](/Users/will/Projects/sqldbagent/docs/_internal/implementation-roadmap.md)
- [memory.md](/Users/will/Projects/sqldbagent/docs/_internal/memory.md)

### Dashboard Surface

Use the dashboard folder when the work is specifically about the Streamlit chat
surface rather than the reusable platform:

- [dashboard/README.md](/Users/will/Projects/sqldbagent/docs/_internal/dashboard/README.md)

## Boundary Rule

If a note would still make sense in a non-SQL agent repo, it probably belongs in
the general platform material.

If a note is about the current Streamlit surface, dashboard thread UX, prompt
review pane, retrieval controls, or schema rendering behavior, it belongs in
the dashboard folder.
