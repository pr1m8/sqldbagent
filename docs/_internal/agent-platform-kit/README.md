# Agent Platform Kit

This folder is a moveable internal blueprint for building reusable agent
platforms on top of LangChain v1, LangGraph, LangSmith, and optional retrieval
systems such as Qdrant.

It is intentionally broader than `sqldbagent`.

Use it when you want to extract the current agent stack into a more general
package that can be reused across:

- SQL and data products
- research agents
- ops and workflow agents
- internal assistants
- domain-specific copilots with long-term memory

## Design Goal

Build one reusable agent platform layer with:

- `create_agent(...)` as the standard high-level entry point
- middleware as the main policy surface
- runtime context for dependency injection
- a clear separation between checkpointing and long-term memory
- deployment support through LangGraph CLI and LangSmith
- optional retrieval systems that are additive instead of foundational

## Recommended Reading Order

1. [01-overview.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/01-overview.md)
2. [02-packages-and-interfaces.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/02-packages-and-interfaces.md)
3. [03-runtime-middleware-and-tools.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/03-runtime-middleware-and-tools.md)
4. [04-persistence-memory-and-retrieval.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/04-persistence-memory-and-retrieval.md)
5. [05-deployment-and-observability.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/05-deployment-and-observability.md)
6. [06-extraction-plan.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/06-extraction-plan.md)
7. [07-pragmatic-recipes.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/07-pragmatic-recipes.md)
8. [skill-bundle/agent-platform-foundations/SKILL.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md)

## Reference Sources

This blueprint is grounded primarily in the current official docs for:

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)
- [Custom store](https://docs.langchain.com/langsmith/custom-store)

## Portability Rule

If you lift this folder into another repo, try to preserve the separation
between:

- platform code
- domain skill sets
- deployment/runtime wiring
- retrieval integrations

That separation is what makes the patterns reusable.

## Portable Skill Bundle

If you want this material in Codex skill format, use:

- [skill-bundle/agent-platform-foundations/SKILL.md](/Users/will/Projects/sqldbagent/docs/_internal/agent-platform-kit/skill-bundle/agent-platform-foundations/SKILL.md)

That folder is intentionally self-contained so you can copy it into another
repo or into a local skills directory and keep the progressive-disclosure shape:

- `SKILL.md` for the entrypoint
- `references/` for deeper material loaded only when needed
