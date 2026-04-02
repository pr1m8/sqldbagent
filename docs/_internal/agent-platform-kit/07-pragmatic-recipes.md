# Pragmatic Recipes

This file is the most copy-pastable part of the blueprint.

Use it when you want to stand up a reusable agent stack quickly, then refine
the abstractions later.

## 1. Install The Core Packages

Minimal baseline:

```bash
pdm add langchain langgraph langsmith
```

Add OpenAI support:

```bash
pdm add langchain-openai
```

Add Anthropic support:

```bash
pdm add langchain-anthropic
```

Add durable Postgres-backed checkpointing and store:

```bash
pdm add langgraph-checkpoint-postgres psycopg
```

Add Qdrant retrieval:

```bash
pdm add qdrant-client langchain-qdrant
```

Add optional provider routing and token counting:

```bash
pdm add litellm tiktoken
```

References:

- [LangChain PyPI](https://pypi.org/project/langchain/)
- [LangGraph PyPI](https://pypi.org/project/langgraph/)
- [LangGraph Postgres checkpoint package](https://pypi.org/project/langgraph-checkpoint-postgres/)
- [LangSmith PyPI](https://pypi.org/project/langsmith/)
- [Qdrant client PyPI](https://pypi.org/project/qdrant-client/)

## 2. Define A Small Context Schema

Keep the context object explicit and boring.

```python
from dataclasses import dataclass


@dataclass
class AgentContext:
    org_id: str
    user_id: str
    environment: str = "dev"
    runtime_profile: str = "balanced"
    tenant_id: str | None = None
```

This should hold request-scoped facts, not giant dependency graphs.

## 3. Build Runtime-Aware Tools Safely

Keep public tool args JSON-safe. Inject runtime for execution-time access.

```python
from typing import Annotated

from langchain.tools import ToolRuntime
from langchain_core.tools import InjectedToolArg, tool


@tool
def load_org_preferences(
    namespace: str,
    runtime: Annotated[ToolRuntime[AgentContext] | None, InjectedToolArg] = None,
) -> dict:
    if runtime is None or runtime.store is None:
        return {"namespace": namespace, "preferences": {}}

    record = runtime.store.get(("org", runtime.context.org_id), namespace)
    return {
        "namespace": namespace,
        "preferences": record.value if record else {},
    }
```

That pattern keeps runtime available while hiding it from the published tool
schema.

References:

- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)

## 4. Add Decorator-Based Middleware First

Decorator middleware is the fastest path when you are still discovering the
right abstractions.

### Dynamic Prompt Middleware

```python
from langchain.agents.middleware import dynamic_prompt


@dynamic_prompt
def build_system_prompt(request) -> str:
    context = request.runtime.context
    return (
        "You are a careful internal operations assistant.\n"
        f"Environment: {context.environment}\n"
        f"Runtime profile: {context.runtime_profile}\n"
        "Prefer grounded answers and use tools when facts are missing."
    )
```

### Tool Error Middleware

```python
from collections.abc import Callable

from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.types import Command


@wrap_tool_call
def convert_tool_errors(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    try:
        return handler(request)
    except Exception as exc:
        return ToolMessage(
            content=f"Tool `{request.tool_call['name']}` failed: {exc}",
            tool_call_id=request.tool_call["id"],
        )
```

### Before-Agent State Seeding

```python
from langchain.agents.middleware import before_agent


@before_agent
def seed_state(state, runtime):
    state["active_org_id"] = runtime.context.org_id
    return state
```

Use class-based middleware later when you need multiple coordinated hooks or
configuration on the middleware object.

## 5. Assemble The Agent With `create_agent`

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI


def build_agent(*, tools, middleware, checkpointer=None, store=None):
    model = ChatOpenAI(model="gpt-5", reasoning={"effort": "high"})
    return create_agent(
        model=model,
        tools=tools,
        middleware=middleware,
        checkpointer=checkpointer,
        store=store,
        context_schema=AgentContext,
    )
```

The important part is not the exact model call. It is the builder boundary:

- model resolution
- tools
- middleware
- persistence
- context schema

should all be assembled in one place.

## 6. Add Postgres Checkpointing And Store

Use the checkpointer for thread state. Use the store for reusable memory.

```python
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore


@contextmanager
def open_checkpointer(dsn: str):
    with PostgresSaver.from_conn_string(dsn) as saver:
        saver.setup()
        yield saver


@contextmanager
def open_store(dsn: str):
    with PostgresStore.from_conn_string(dsn) as store:
        store.setup()
        yield store
```

Then:

```python
with open_checkpointer(checkpoint_dsn) as checkpointer:
    with open_store(store_dsn) as store:
        agent = build_agent(
            tools=tools,
            middleware=middleware,
            checkpointer=checkpointer,
            store=store,
        )
```

Good default namespace shape:

```python
("org", org_id, "user", user_id, "agent", "researcher")
```

## 7. Add Retrieval Without Making It Foundational

Treat retrieval as one more context source, not the core system of record.

```python
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


def build_retriever(qdrant_url: str, collection_name: str):
    client = QdrantClient(url=qdrant_url)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
    return store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 6, "fetch_k": 20},
    )
```

Recommended payload fields:

- `tenant_id`
- `agent_family`
- `artifact_type`
- `document_id`
- `source`
- `scope_id`

Use retrieval to add grounded snippets into the dynamic prompt or tool results.

## 8. Add A Memory-Sync Tool

It is usually better to write a narrow memory tool than to let every tool write
to the store.

```python
from langchain_core.tools import tool


@tool
def remember_preference(
    key: str,
    value: str,
    runtime: Annotated[ToolRuntime[AgentContext] | None, InjectedToolArg] = None,
) -> dict:
    if runtime is None or runtime.store is None:
        return {"saved": False, "reason": "No store configured."}

    namespace = ("org", runtime.context.org_id, "user", runtime.context.user_id)
    runtime.store.put(namespace, key, {"value": value})
    return {"saved": True, "key": key}
```

This is much easier to review than hidden auto-writes scattered across tools.

## 9. Add A Simple Prompt Composer

Do not keep prompt construction as random string concatenation in route handlers
or UI code.

```python
def compose_prompt(
    *,
    base_prompt: str,
    remembered_context: str | None,
    retrieved_context: str | None,
    task_instructions: str | None,
) -> str:
    sections = [base_prompt]
    if remembered_context:
        sections.append("REMEMBERED CONTEXT:\n" + remembered_context)
    if retrieved_context:
        sections.append("RETRIEVED CONTEXT:\n" + retrieved_context)
    if task_instructions:
        sections.append("TASK:\n" + task_instructions)
    return "\n\n".join(sections)
```

Later, make this a real service with:

- token budgeting
- section priorities
- truncation rules
- source annotations

## 10. Standardize `langgraph.json`

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./src/my_app/graph.py:graph"
  },
  "env": ".env",
  "store": {
    "path": "./src/my_app/store.py:generate_store"
  }
}
```

That makes local dev, CI, and hosted deployment line up.

Reference:

- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)

## 11. Add LangGraph SDK Smoke Tests

This is a good pattern for deployed integration checks.

```python
from langgraph_sdk import get_sync_client


client = get_sync_client(
    url="https://my-agent.example.com",
    api_key="...",
)

chunks = list(
    client.runs.stream(
        None,
        "agent",
        input={
            "messages": [
                {"role": "human", "content": "Summarize the latest org context."}
            ]
        },
        stream_mode="updates",
    )
)
assert chunks
```

## 12. Suggested Directory Layout

```text
src/my_app/
  agent/
    builder.py
    context.py
    state.py
    skillsets.py
    middleware.py
    prompts.py
    persistence.py
    retrieval.py
    observability.py
  domain/
    tools.py
    services.py
    models.py
  cli/
  dashboard/
```

This keeps:

- generic agent plumbing in one place
- domain logic in another
- surfaces thin

## 13. Recommended First Presets

Start with a very small preset matrix:

- `assistant_fast`
- `assistant_balanced`
- `researcher_balanced`
- `researcher_deep`
- `operator_balanced`

Only add more once you have a real reason to.

## 14. Practical Rule Of Thumb

When deciding where something belongs:

- if it is about thread continuity, it belongs in the checkpointer
- if it is reusable across threads, it belongs in the store
- if it is large searchable content, it belongs in retrieval
- if it is a policy, it belongs in middleware
- if it is a capability, it belongs in a skill set
- if it is request-scoped, it belongs in runtime context

## References

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)
- [Custom store](https://docs.langchain.com/langsmith/custom-store)
