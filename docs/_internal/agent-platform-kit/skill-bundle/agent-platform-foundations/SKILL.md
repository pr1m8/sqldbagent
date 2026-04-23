---
name: agent-platform-foundations
description: Use when building or refactoring reusable agent platforms on top of LangChain v1, LangGraph, LangSmith, checkpointing, long-term store memory, middleware, ToolRuntime-aware tools, retrieval backends such as Qdrant, or LangGraph SDK and CLI deployment paths. Also use when extracting domain-specific agents into a general agent framework with skill sets, runtime profiles, persistence profiles, prompt composition, and deployment conventions.
---

# Agent Platform Foundations

Use this skill when the work is about reusable agent infrastructure rather than
one specific domain app.

The design goal is:

- `create_agent(...)` as the standard entry point
- middleware as the policy layer
- dynamic prompt assembly as the shared instruction path
- runtime context for request-scoped injection
- checkpointer for thread continuity
- store for long-term memory
- retrieval as an additive context source
- LangGraph CLI and LangSmith for runtime and deployment

## Workflow

1. Decide whether the task is platform-level or domain-level.
2. Keep platform code separate from domain tools and prompt fragments.
3. Use runtime context and middleware instead of globals or UI glue.
4. Keep public tool schemas JSON-safe.
5. Keep checkpointer, store, and retrieval as separate systems.
6. Standardize deployment and tracing conventions early.

## Read These References As Needed

- For package choices, abstractions, and profile boundaries, read [references/foundations-and-interfaces.md](references/foundations-and-interfaces.md).
- For `ToolRuntime`, `RunnableConfig`, middleware, and state boundaries, read [references/runtime-middleware-and-state.md](references/runtime-middleware-and-state.md).
- For Postgres checkpointing, long-term memory, Qdrant retrieval, embeddings, caching, and `ensure` versus `rebuild` versus `reset`, read [references/persistence-retrieval-and-memory.md](references/persistence-retrieval-and-memory.md).
- For install patterns, `langgraph.json`, website and backend integration, LangSmith, SDK usage, and extraction planning, read [references/operations-and-adoption.md](references/operations-and-adoption.md).

## Non-Negotiable Rules

- Do not treat the checkpointer as global memory.
- Do not expose runtime objects directly in public tool schemas.
- Do not make retrieval the source of truth when structured state or stored
  artifacts already exist.
- Do not hardcode provider or model choice inside skill sets.
- Do not let UI code own prompt assembly or persistence policy.
- Do not split into multi-agent topology unless there is a real system
  boundary.

## Practical Defaults

- Start with Postgres for durable checkpoints and long-term store.
- Add Qdrant only when semantic retrieval is actually needed.
- Use decorator middleware first, then move to class-based middleware when you
  need multiple coordinated hooks.
- Use one narrow memory-write path instead of letting every tool write to the
  store.
- Standardize `langgraph.json`, tracing tags, and runtime profile names across
  repos.

## Official References

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)
- [Custom store](https://docs.langchain.com/langsmith/custom-store)
