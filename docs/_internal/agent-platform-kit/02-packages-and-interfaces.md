# Packages And Interfaces

## Baseline Package Set

These are the main packages worth standardizing around for a reusable Python
agent platform.

| Package                         | Role                                                                                     | Links                                                                                                             |
| ------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `langchain`                     | High-level agent API, middleware, tools, model init                                      | [Docs](https://docs.langchain.com/oss/python/releases/langchain-v1) · [PyPI](https://pypi.org/project/langchain/) |
| `langgraph`                     | Runtime, persistence model, low-level orchestration, CLI compatibility                   | [Docs](https://docs.langchain.com/oss/python/releases/langgraph-v1) · [PyPI](https://pypi.org/project/langgraph/) |
| `langgraph-sdk`                 | Remote client for deployed graphs and streaming runs                                     | [Docs](https://docs.langchain.com/oss/python/langchain/deploy) · [PyPI](https://pypi.org/project/langgraph-sdk/)  |
| `langgraph-checkpoint-postgres` | Durable Postgres checkpointer and Postgres store support                                 | [PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/)                                                   |
| `langsmith`                     | Tracing, evaluation, deployments, prompts, project observability                         | [Docs](https://docs.langchain.com/langsmith/home) · [PyPI](https://pypi.org/project/langsmith/)                   |
| `langchain-openai`              | OpenAI chat and embedding integrations                                                   | [PyPI](https://pypi.org/project/langchain-openai/)                                                                |
| `langchain-anthropic`           | Anthropic chat integrations                                                              | [PyPI](https://pypi.org/project/langchain-anthropic/)                                                             |
| `qdrant-client`                 | Qdrant database client                                                                   | [Docs](https://qdrant.tech/documentation/) · [PyPI](https://pypi.org/project/qdrant-client/)                      |
| `langchain-qdrant`              | LangChain vector store integration for Qdrant                                            | [PyPI](https://pypi.org/project/langchain-qdrant/)                                                                |
| `litellm`                       | Optional provider routing abstraction if you want multi-provider routing above LangChain | [PyPI](https://pypi.org/project/litellm/)                                                                         |

## What Each Layer Should Depend On

### Platform Core

Keep the core platform layer light:

- `langchain`
- `langgraph`
- `langsmith`

This layer should define:

- build specs
- runtime profiles
- persistence profiles
- prompt composer interfaces
- middleware registries
- skill-set registries

### Persistence Layer

Add:

- `langgraph-checkpoint-postgres`
- `psycopg`

Optional, depending on your deployment target:

- MongoDB-specific dependencies if you adopt Mongo-based checkpointers
- custom store/checkpointer packages for other infra

### Retrieval Layer

Add only if you actually need semantic retrieval:

- `qdrant-client`
- `langchain-qdrant`
- embedding integration packages

### Provider Layer

Keep model integrations separate from the platform core:

- `langchain-openai`
- `langchain-anthropic`
- `langchain-google-genai`
- `litellm` if you want a routing facade

That way the platform is not hard-bound to one provider.

## Recommended Interface Modules

Create stable registries instead of direct imports all over the app:

```text
agentkit/
  skills/registry.py
  runtime/registry.py
  persistence/registry.py
  prompts/registry.py
  observability/registry.py
```

### Runtime Registry

The runtime registry should define named profiles:

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
```

### Persistence Registry

```python
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

## Model Selection

Do not make skill sets choose the model directly.

Skill sets should say what capabilities they need:

- stronger reasoning
- broader tool budget
- retrieval-first
- structured output

Runtime profiles should decide:

- provider
- concrete model
- reasoning effort
- call limits
- streaming

That gives you a clean split between:

- domain behavior
- cost/performance policy

## Structured Output

If an agent has a stable output contract, model that separately rather than
hiding it inside the prompt.

LangChain v1 supports structured output directly in the main loop.

Reference:

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)

## Practical Example: Platform Builder

```python
def create_registered_agent(spec_name: str, *, services, settings, context=None):
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
        context_schema=context,
    )
```

## Recommended Extras Groups

If you publish the reusable layer as its own package, a practical extras layout
would be:

```toml
[project.optional-dependencies]
openai = ["langchain-openai"]
anthropic = ["langchain-anthropic"]
persistence = ["langgraph-checkpoint-postgres", "psycopg"]
retrieval = ["qdrant-client", "langchain-qdrant"]
deploy = ["langgraph-sdk", "langsmith"]
dev = ["pytest", "pytest-asyncio", "ruff"]
```

## References

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
- [How to use a custom store](https://docs.langchain.com/langsmith/custom-store)
