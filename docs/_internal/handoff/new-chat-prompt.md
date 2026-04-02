# New Chat Prompt

Use this as a starter when opening a fresh chat on the same repo.

```text
Please resume work on /Users/will/Projects/sqldbagent.

Start by reading:
1. /Users/will/Projects/sqldbagent/AGENTS.md
2. /Users/will/Projects/sqldbagent/docs/_internal/memory.md
3. /Users/will/Projects/sqldbagent/docs/_internal/handoff/current.md

Treat the handoff file as the current working context unless git or code
inspection shows something newer. Keep adapter surfaces thin, keep database
safety centralized, and prefer persisted artifacts over re-querying when they
already satisfy the workflow.

After reading, summarize:
- current project state
- active work in progress
- the best next implementation step

Then continue the work directly.
```

If the new chat is about reusable agent-platform work rather than only
`sqldbagent`, also add:

```text
For generalized LangChain v1 / LangGraph platform patterns, also read:
/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/README.md
/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md
```
