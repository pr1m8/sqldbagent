# Extraction Plan

## Goal

Extract the current agent stack into a reusable platform package without
breaking `sqldbagent`.

The reusable layer should be domain-agnostic.

`sqldbagent` should then become one domain application built on top of that
layer.

## Target Split

### Reusable Platform Package

Candidate names:

- `agentkit`
- `agentstack`
- `graphagentkit`

Responsibilities:

- build specs
- runtime profiles
- persistence profiles
- prompt composer
- middleware registries
- checkpointer/store factories
- LangSmith helpers
- LangGraph CLI/deploy helpers
- generic tool/memory/runtime conventions

### Domain Package

Responsibilities:

- domain tools
- domain prompt fragments
- domain retrieval indexing rules
- domain UI surfaces
- domain-safe write policies

## Suggested Migration Order

### Phase 1

Extract generic pieces first:

- model/runtime profile settings
- checkpointer/store factories
- LangSmith config helpers
- generic middleware patterns

### Phase 2

Extract the agent builder:

- skill-set registry
- build spec registry
- generic `create_registered_agent(...)`

### Phase 3

Extract prompt composition:

- layered prompt builder
- remembered context injection
- retrieval snippet injection
- token-budget helpers

### Phase 4

Extract generic deployment and SDK helpers:

- `langgraph.json` conventions
- SDK clients
- CLI commands

### Phase 5

Refit `sqldbagent` to consume the platform package:

- `sql_inspector` skill set
- `sql_analyst` skill set
- `sql_retriever` skill set
- `sql_operator` skill set

## Recommended Initial Platform API

```python
agent = create_registered_agent(
    spec_name="researcher_deep",
    services=services,
    settings=settings,
    context=AgentContext(
        org_id="acme",
        user_id="u123",
        environment="prod",
    ),
)
```

Then domain apps only need to register:

- skill sets
- prompt fragments
- retrieval policies
- narrow domain tools

## What Not To Extract Too Early

Do not try to generalize these too early:

- SQL safety logic
- SQL prompt fragments
- SQL-specific retrieval payloads
- dashboard-specific state payloads

Those belong in the domain app until another domain truly needs the same shape.

## Minimal First Presets

Ship these platform presets first:

- `assistant_fast`
- `assistant_balanced`
- `researcher_balanced`
- `researcher_deep`
- `operator_balanced`

Then let domain packages add:

- `sql_analyst`
- `docs_reviewer`
- `ops_triager`

## Quality Bar

Before extracting, make sure the platform layer has:

- explicit runtime context schema
- explicit state schema
- explicit persistence factories
- explicit tool schema rules
- tests for JSON-safe tool args
- tests for middleware ordering and state updates
- tests for store/checkpointer fallback behavior

## Practical Recommendation

If you do this soon, keep `sqldbagent` as the proving ground:

- build the generic package shape inside this repo first
- move one or two subsystems at a time
- only split into a separate package once the abstractions survive real use

That is usually safer than trying to extract everything at once.

## References

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
