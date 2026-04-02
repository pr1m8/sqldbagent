# MCP Inventory And Setup

## Policy

MCP servers used with this repo must be tracked here before they become assumed parts of the workflow.

Track each server with:

- name
- status: required, recommended, or optional
- purpose
- install/source method
- repo workflow supported
- config location if relevant
- notes on secrets or credentials

Do not commit personal tokens, machine-specific secrets, or private endpoint values.

## Recommended MCP Baseline

### Docs By LangChain

- status: recommended
- purpose: documentation lookup for LangChain and LangGraph adapter work
- workflow: research while implementing `src/sqldbagent/adapters/langchain` and `src/sqldbagent/adapters/langgraph`
- notes: the most useful MCP once adapter implementation begins

### OpenAI Docs

- status: optional
- purpose: documentation lookup when MCP, agent, or OpenAI-facing integrations are added later
- workflow: only relevant once OpenAI-specific adapter work exists
- notes: not required for current foundation milestones

### Future database-focused MCPs

- status: undecided
- purpose: safe DB-facing exploration or admin workflows if a real need appears
- workflow: should only be added after safety contracts and inspection services exist
- notes: do not introduce direct DB mutation paths through convenience tooling

## Install Template

When adding a real MCP server, append an entry using this format:

```text
Name:
Status:
Purpose:
Install method:
Config location:
Repo workflow:
Secrets needed:
Notes:
```

## Initialization Rule

Adding an MCP server is not complete until:

1. it is listed here
2. its purpose is tied to a repo workflow
3. any required local setup is documented
4. the repo does not silently depend on private local state
