# Agent Platform Overview

## What We Are Actually Building

The reusable layer should not be "an agent".

It should be an agent platform with a few explicit parts:

- agent assembly
- middleware policy
- runtime context and dependency injection
- checkpoint persistence
- long-term memory storage
- prompt assembly
- tool registration
- observability
- optional retrieval
- deployment adapters

That lets one platform support many agent types without rewriting the
foundations each time.

## Core Principles

### 1. `create_agent(...)` Is The Main Entry Point

LangChain v1 made `create_agent(...)` the standard high-level entry point and
positioned middleware as the main customization surface.

Use that unless you truly need lower-level graph construction.

Reference:

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)

### 2. LangGraph Is The Runtime, Not Just "The Agent Package"

LangGraph is what gives you:

- checkpointing
- persistence
- interrupts
- streaming
- HITL
- deployment/runtime semantics

Treat LangGraph as the runtime substrate under the agent, not as an optional
extra.

Reference:

- [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)

### 3. Middleware Is The Policy Layer

Do not scatter prompting, model routing, tool filtering, or guardrails across
callers.

Middleware should own:

- dynamic prompt assembly
- state seeding
- tool error shaping
- model selection
- tool selection
- summarization
- HITL
- output validation
- usage tracking

Reference:

- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)

### 4. Checkpointer And Store Are Different Systems

This is one of the most important boundaries.

- Checkpointer:
  - thread state
  - resumability
  - time travel
  - workflow continuity

- Store:
  - long-term memory
  - reusable user or app facts
  - durable context across threads
  - optional semantic search depending on backend

Do not use the checkpointer as your long-term memory database.

References:

- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)
- [Custom store](https://docs.langchain.com/langsmith/custom-store)

### 5. Retrieval Is Additive

Qdrant or any vector store should help the agent find relevant context. It
should not replace:

- domain models
- prompt artifacts
- state
- long-term memory
- business-specific structured data

Use retrieval as one context source, not the only context source.

## Recommended Platform Layers

Use a package shape like this:

```text
src/agentkit/
  core/
  runtime/
  middleware/
  prompts/
  tools/
  persistence/
    checkpoint/
    store/
  retrieval/
  observability/
  skills/
  deploy/
```

Then domain packages sit on top:

```text
src/my_sql_agent/
src/my_research_agent/
src/my_ops_agent/
```

## The Main Abstractions

Start with a few durable abstractions.

### Skill Set

```python
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class AgentSkillSet:
    name: str
    tool_factories: list[Callable[..., list[Any]]]
    middleware_factories: list[Callable[..., list[Any]]]
    prompt_sections: list[str]
    memory_policy: str
    retrieval_policy: str | None = None
    hitl_policy: str | None = None
```

### Runtime Profile

```python
from dataclasses import dataclass


@dataclass
class AgentRuntimeProfile:
    name: str
    provider: str
    model: str
    reasoning_effort: str | None = None
    max_model_calls: int | None = None
    max_tool_calls: int | None = None
    streaming: bool = True
```

### Persistence Profile

```python
from dataclasses import dataclass


@dataclass
class AgentPersistenceProfile:
    name: str
    checkpoint_backend: str
    store_backend: str
    namespace_strategy: str
    durable_threads: bool = True
    durable_memory: bool = True
```

### Build Spec

```python
from dataclasses import dataclass


@dataclass
class AgentBuildSpec:
    name: str
    skillsets: list[str]
    runtime_profile: str
    persistence_profile: str
    prompt_profile: str
```

## Why This Is Better Than "One Agent Per File"

Without these layers, teams usually end up with:

- one agent builder per project
- duplicated middleware
- prompt strings baked into app files
- model choice mixed with domain policy
- persistence setup repeated everywhere

With these layers, you can build many agents by composition:

- `research_fast`
- `research_deep`
- `ops_assistant`
- `sql_analyst`
- `customer_support`

without rewriting the platform.

## Practical Presets To Ship First

If you extract a general platform, ship these first:

- `assistant`
  - generic helpful assistant
  - light memory
  - basic tool access

- `researcher`
  - retrieval-first
  - heavier reasoning
  - citation and summarization middleware

- `operator`
  - tighter guardrails
  - explicit approval points
  - strong audit logging and tracing

- `analyst`
  - structured evidence gathering
  - memory writes allowed only through narrow tools
  - retrieval plus domain tools

## Recommended Default Decisions

- use LangChain v1 `create_agent(...)`
- keep LangGraph checkpointers and stores behind factories
- prefer middleware over ad hoc wrappers
- keep state schema explicit
- keep context schema explicit
- make tool schemas JSON-serializable
- make runtime-only inputs injected
- prefer Postgres for durable local and production persistence
- use Qdrant only when semantic retrieval is actually needed

## References

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
