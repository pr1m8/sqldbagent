# Operations And Adoption

Use this reference for:

- install patterns
- `langgraph.json`
- LangSmith and `langgraph-sdk`
- operational checks
- extraction plan

## Install Baseline

```bash
pdm add langchain langgraph langsmith
pdm add langchain-openai
pdm add langgraph-checkpoint-postgres psycopg
```

Add retrieval packages only when needed.

## Standard Local Path

- `langgraph dev`
- `langgraph build`
- `langgraph up`

## Standardize

- tracing tags
- environment-variable meaning
- deployment smoke checks
- CLI commands for persistence and retrieval diagnostics

## Final Integration Patterns

- website or product UI:
  - frontend calls your backend
  - backend owns auth, tenancy, and thread ids
  - backend calls the deployed graph through `RemoteGraph` or `langgraph-sdk`
- local tests:
  - use a compiled local graph
- production:
  - switch only the graph transport, not the app-facing gateway
- multi-agent:
  - use `RemoteGraph` across deployment boundaries
  - do not call the same deployment recursively

## Good Ownership Split

- frontend:
  - rendering and chat UX
- backend app:
  - auth and request shaping
- agent runtime:
  - prompts, middleware, tools, persistence, retrieval
- persistence systems:
  - checkpoints, store memory, vector backend

## Extraction Rule

Extract generic platform code first.

Leave domain-safe write policies, domain retrieval payloads, and domain UI
state in the domain app until a second domain truly needs them.

## References

- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
- [Trace LangChain applications](https://docs.langchain.com/langsmith/trace-with-langchain)
- [How to interact with a deployment using RemoteGraph](https://docs.langchain.com/langsmith/use-remote-graph)
