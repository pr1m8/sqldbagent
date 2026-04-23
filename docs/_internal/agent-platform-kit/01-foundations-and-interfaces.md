# Foundations And Interfaces

## Goal

This blueprint is for building a reusable agent platform on top of LangChain
v1, LangGraph, LangSmith, and optional retrieval systems such as Qdrant.

The platform should not be "one agent". It should be a composition layer that
can support many agents without rewriting the foundations each time.

## Core Principles

### `create_agent(...)` Is The Standard Entry Point

Use LangChain v1 `create_agent(...)` as the default high-level entry point.
Drop to lower-level LangGraph construction only when you truly need custom graph
topology.

### LangGraph Is The Runtime Substrate

Treat LangGraph as the runtime and persistence layer under the agent, not as an
optional extra. This is where thread persistence, interrupts, streaming, and
deployment semantics come from.

### Middleware Is The Policy Layer

Keep prompt assembly, model routing, tool error shaping, HITL, summarization,
and guardrails in middleware rather than scattering them across UI code or app
routes.

### Retrieval Is Additive

Retrieval should augment stored artifacts and memory. It should not replace:

- typed context
- graph state
- long-term store memory
- domain models

## Recommended Package Set

| Package                         | Role                                                | Links                                                                                                             |
| ------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `langchain`                     | high-level agent API, middleware, tools, model init | [Docs](https://docs.langchain.com/oss/python/releases/langchain-v1) · [PyPI](https://pypi.org/project/langchain/) |
| `langgraph`                     | runtime, persistence model, low-level orchestration | [Docs](https://docs.langchain.com/oss/python/releases/langgraph-v1) · [PyPI](https://pypi.org/project/langgraph/) |
| `langsmith`                     | tracing, evaluation, deployment ecosystem           | [Docs](https://docs.langchain.com/langsmith/home) · [PyPI](https://pypi.org/project/langsmith/)                   |
| `langgraph-sdk`                 | remote client for deployed graphs                   | [Docs](https://docs.langchain.com/oss/python/langchain/deploy) · [PyPI](https://pypi.org/project/langgraph-sdk/)  |
| `langgraph-checkpoint-postgres` | durable Postgres checkpointing and store support    | [PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/)                                                   |
| `langchain-openai`              | OpenAI chat and embedding integrations              | [PyPI](https://pypi.org/project/langchain-openai/)                                                                |
| `langchain-anthropic`           | Anthropic chat integrations                         | [PyPI](https://pypi.org/project/langchain-anthropic/)                                                             |
| `qdrant-client`                 | Qdrant client                                       | [Docs](https://qdrant.tech/documentation/) · [PyPI](https://pypi.org/project/qdrant-client/)                      |
| `langchain-qdrant`              | Qdrant vector store integration                     | [PyPI](https://pypi.org/project/langchain-qdrant/)                                                                |
| `litellm`                       | optional provider-routing abstraction               | [PyPI](https://pypi.org/project/litellm/)                                                                         |
| `tiktoken`                      | token counting and prompt budget estimation         | [PyPI](https://pypi.org/project/tiktoken/)                                                                        |

## Layering

### Platform Core

Keep this layer light:

- `langchain`
- `langgraph`
- `langsmith`

It should define:

- build specs
- runtime profiles
- persistence profiles
- prompt-composer interfaces
- middleware registries
- skill-set registries

### Persistence Layer

Add:

- `langgraph-checkpoint-postgres`
- `psycopg`

### Retrieval Layer

Add only when semantic retrieval is justified:

- `qdrant-client`
- `langchain-qdrant`
- embedding provider integrations

### Provider Layer

Keep provider integrations outside the platform core:

- `langchain-openai`
- `langchain-anthropic`
- other provider packages as needed

## Recommended Package Layout

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

## Main Abstractions

### `AgentSkillSet`

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

### `AgentRuntimeProfile`

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

### `AgentPersistenceProfile`

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

### `AgentBuildSpec`

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

## Runtime And Persistence Registries

```python
RUNTIME_PROFILES = {
    "fast": AgentRuntimeProfile(
        name="fast",
        provider="openai",
        model="gpt-5-mini",
        reasoning_effort="low",
        max_model_calls=8,
        max_tool_calls=12,
    ),
    "balanced": AgentRuntimeProfile(
        name="balanced",
        provider="openai",
        model="gpt-5",
        reasoning_effort="medium",
        max_model_calls=12,
        max_tool_calls=20,
    ),
    "deep": AgentRuntimeProfile(
        name="deep",
        provider="openai",
        model="gpt-5",
        reasoning_effort="high",
        max_model_calls=20,
        max_tool_calls=30,
    ),
}

PERSISTENCE_PROFILES = {
    "ephemeral": AgentPersistenceProfile(
        name="ephemeral",
        checkpoint_backend="memory",
        store_backend="memory",
        namespace_strategy="thread_local",
    ),
    "durable": AgentPersistenceProfile(
        name="durable",
        checkpoint_backend="postgres",
        store_backend="postgres",
        namespace_strategy="org_user_agent_scope",
    ),
}
```

## Model Selection Rule

Do not make skill sets choose concrete models directly.

Skill sets should express capability needs:

- stronger reasoning
- broader tool budget
- retrieval-first behavior
- structured output

Runtime profiles should decide:

- provider
- concrete model
- reasoning effort
- call limits
- streaming

## Platform Builder Example

```python
def create_registered_agent(spec_name: str, *, services, settings):
    spec = AGENT_SPECS[spec_name]
    runtime_profile = RUNTIME_PROFILES[spec.runtime_profile]
    persistence_profile = PERSISTENCE_PROFILES[spec.persistence_profile]
    skillsets = [SKILLSETS[name] for name in spec.skillsets]

    model = resolve_model(runtime_profile, settings=settings)
    tools = build_tools(skillsets, services=services)
    middleware = build_middleware(
        skillsets,
        runtime_profile=runtime_profile,
        services=services,
        settings=settings,
    )
    checkpointer = build_checkpointer(persistence_profile, settings=settings)
    store = build_store(persistence_profile, settings=settings)

    return create_agent(
        model=model,
        tools=tools,
        middleware=middleware,
        checkpointer=checkpointer,
        store=store,
        context_schema=AgentContext,
    )
```

## Recommended Extras

```toml
[project.optional-dependencies]
openai = ["langchain-openai"]
anthropic = ["langchain-anthropic"]
persistence = ["langgraph-checkpoint-postgres", "psycopg"]
retrieval = ["qdrant-client", "langchain-qdrant"]
deploy = ["langgraph-sdk", "langsmith"]
dev = ["pytest", "pytest-asyncio", "ruff"]
```

## Recommended First Presets

Start with a small matrix:

- `assistant_fast`
- `assistant_balanced`
- `researcher_balanced`
- `researcher_deep`
- `operator_balanced`

Then let domain packages add:

- `sql_analyst`
- `docs_reviewer`
- `ops_triager`

## Reference Agent Designs

These are intentionally product-shaped examples, not toy abstractions.

### 1. Website Copilot

Use this when a web app needs a customer-facing or internal assistant behind a
chat panel.

Recommended shape:

- skill sets:
  - `faq_retrieval`
  - `account_context`
  - `safe_actions`
- runtime profile:
  - `assistant_balanced`
- persistence profile:
  - durable thread checkpoints
  - durable user and org store memory
- prompt profile:
  - product voice
  - support boundaries
  - escalation rules

Key runtime context:

- authenticated user id
- org or tenant id
- product tier
- enabled actions
- locale or timezone

Important middleware:

- dynamic prompt that injects account tier and enabled features
- tool error shaping so backend failures become user-safe responses
- HITL or approval middleware before state-changing tools
- summarization middleware once the transcript gets long

Good tools:

- `search_docs`
- `load_account_summary`
- `list_recent_orders`
- `create_support_ticket`

Keep writes narrow:

- read-only tools are available by default
- state-changing tools are opt-in and clearly labeled
- durable store memory keeps preferences and validated notes, not raw chat logs

### 2. Research Or Policy Agent

Use this when the agent needs to gather, compare, and synthesize sources.

Recommended shape:

- skill sets:
  - `search_and_fetch`
  - `citation_grounding`
  - `retrieval_memory`
- runtime profile:
  - `researcher_deep`
- persistence profile:
  - durable thread checkpoints
  - durable store for reusable notes

Important middleware:

- source-ranking middleware
- citation formatting middleware
- answer validation or structured output middleware
- context-window summarization

Recommended retrieval:

- index internal notes, prior research briefs, and policy docs
- use metadata filters aggressively
- keep retrieved snippets separate from durable memory

### 3. Coding Or Repo Agent

Use this when the agent is embedded into a code review or implementation
workflow.

Recommended shape:

- skill sets:
  - `repo_search`
  - `test_and_build`
  - `patch_proposal`
  - `docs_lookup`
- runtime profile:
  - `operator_balanced` or a stronger reasoning preset
- persistence profile:
  - durable thread checkpoints
  - store memory for repo conventions and reusable review rules

Important middleware:

- tool budget control
- write-action approval
- patch or diff summarization
- prompt injection of repo conventions from store memory

Recommended store contents:

- preferred code style notes
- deployment caveats
- repo-specific review checklists
- stable architecture decisions

### 4. Internal Workflow Agent

Use this when the agent coordinates business processes across systems.

Recommended shape:

- skill sets:
  - `task_planning`
  - `system_lookup`
  - `approval_actions`
- runtime profile:
  - `assistant_balanced`
- persistence profile:
  - durable checkpoints
  - durable store per user, org, and workflow family

Important middleware:

- todo or plan middleware
- HITL for risky transitions
- interrupt and resume support through checkpointed threads
- audit-oriented prompt sections that keep the agent explicit about what it did

## Integration Rule Of Thumb

Use the simplest shape that satisfies the product:

- single website assistant:
  - one graph, one store, one checkpointer, optional retrieval
- specialist backend agent:
  - one graph plus narrow tools and strong runtime context
- multi-agent system:
  - multiple deployed graphs with `RemoteGraph` boundaries between them

Do not start with the multi-agent shape unless there is a real product boundary
that justifies it.

## Multi-Agent Topologies

Multi-agent is a good pattern when the boundary is real and valuable.

Good reasons to split:

- a specialist needs a different runtime profile
- a specialist has a narrower security boundary
- different teams own different graphs
- one workflow benefits from explicit handoff and reuse
- one agent should be reused by another product through a deployment boundary

Bad reasons:

- weak prompt design in the single-agent shape
- too many tools with no curation
- unclear state design that delegation is being asked to hide

Recommended topologies:

### Router Plus Specialists

- a parent graph routes
- specialist graphs do focused work such as research, planning, or actions
- each specialist can own its own tools, middleware, and persistence profile

### Orchestrator Plus Worker Graphs

- the orchestrator owns user interaction, plan state, and approvals
- worker graphs do focused execution
- this fits longer-running workflows and HITL checkpoints well

### Shared Product Copilot Plus Domain Experts

- one website or app assistant owns the conversation
- domain experts sit behind deployment boundaries
- the parent graph calls them through `RemoteGraph` only when necessary

Rule of thumb:

- start single-agent
- move to router plus specialists second
- add deeper orchestration only when the workflow really needs it

## References

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
- [Custom store](https://docs.langchain.com/langsmith/custom-store)
- [Runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [How to interact with a deployment using RemoteGraph](https://docs.langchain.com/langsmith/use-remote-graph)
