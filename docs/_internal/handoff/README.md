# Handoff Docs

This folder is the repo-local handoff surface for moving work between chats,
threads, or projects.

Use it when:

- starting a new Codex or ChatGPT conversation on the same repo
- handing work to another agent or teammate
- freezing current state before a risky refactor
- preserving current implementation status outside transient chat history

## What Belongs Here

- the current repo handoff
- a reusable handoff template
- a paste-ready new-chat prompt
- short decision summaries when they matter for continuity

## What Does Not Belong Here

- secrets or tokens
- raw terminal transcripts
- stale status files that nobody maintains
- large generated artifacts

## Working Rule

Keep one actively maintained current handoff file:

- [current.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/current.md)

Use these helpers:

- [template.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/template.md)
- [new-chat-prompt.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/new-chat-prompt.md)

## Practical Flow

1. Update [current.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/current.md) before switching chats if the repo state changed materially.
2. Start the new chat in the same ChatGPT Project when possible.
3. Point the new chat at:
   - [AGENTS.md](/Users/will/Projects/sqldbagent/AGENTS.md)
   - [docs/\_internal/memory.md](/Users/will/Projects/sqldbagent/docs/_internal/memory.md)
   - [current.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/current.md)
4. If needed, paste the starter text from [new-chat-prompt.md](/Users/will/Projects/sqldbagent/docs/_internal/handoff/new-chat-prompt.md).

## Maintenance Rule

If a new feature or architectural change would take more than a few minutes to
reconstruct from git and public docs, update the handoff folder.
