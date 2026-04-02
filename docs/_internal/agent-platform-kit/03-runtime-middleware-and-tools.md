# Runtime, Middleware, And Tools

## Runtime Context Is The Right Injection Surface

LangChain v1 and LangGraph expect runtime dependencies to flow through the
runtime object, not through globals.

Runtime gives you access to:

- static invocation context
- long-term store
- stream writer

That is the correct home for:

- user/org ids
- environment flags
- database handles or service clients
- memory store access
- deployment configuration

Reference:

- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)

## Recommended Context Schema

Keep context explicit.

```python
from dataclasses import dataclass


@dataclass
class AgentContext:
    org_id: str
    user_id: str
    session_id: str | None = None
    environment: str = "dev"
    agent_mode: str = "balanced"
```

Then pass it at invoke time instead of hiding it in env vars.

## Tool Schema Rule

Public tool args must stay JSON-serializable.

That means:

- use `str`, `int`, `float`, `bool`, `list`, `dict`
- use Pydantic models for structured public input
- do not expose Python runtime objects in tool signatures

This matters for:

- agent tool schema generation
- MCP exposure
- LangSmith/LangGraph tooling
- deployment compatibility

## `ToolRuntime` Pattern

For runtime-aware tools, use `ToolRuntime` for execution-time dependencies.

Simple form:

```python
from langchain.tools import tool, ToolRuntime


@tool
def load_preferences(runtime: ToolRuntime[AgentContext]) -> dict:
    if runtime.store:
        record = runtime.store.get(("users",), runtime.context.user_id)
        if record:
            return record.value
    return {}
```

## Important Practical Edge Case

If you need optional runtime parameters or more complex type annotations, be
careful not to leak the runtime object into JSON schema generation.

A robust pattern is:

```python
from typing import Annotated
from langchain.tools import ToolRuntime
from langchain_core.tools import InjectedToolArg


def my_tool(
    query: str,
    runtime: Annotated[ToolRuntime[AgentContext] | None, InjectedToolArg] = None,
) -> dict:
    ...
```

Use that when you want runtime injection to stay available but absent from the
public tool schema.

## Middleware Style Choices

LangChain supports two good styles.

### Decorator-Based Middleware

Best when:

- one hook is enough
- you want a focused behavior
- you are prototyping

Useful decorators:

- `@before_agent`
- `@before_model`
- `@after_model`
- `@after_agent`
- `@wrap_model_call`
- `@wrap_tool_call`
- `@dynamic_prompt`

Reference:

- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)

### Class-Based Middleware

Best when:

- you need multiple hooks together
- you need config/state on the middleware object
- you need both sync and async implementations
- you want reusable packaged middleware

## Middleware You Should Standardize Globally

### 1. State Seeding Middleware

Use `@before_agent` or `before_agent(...)` to load:

- remembered context
- latest prompt artifact
- latest snapshot summary
- dashboard or UI payload
- org/user metadata

### 2. Dynamic Prompt Middleware

Use `@dynamic_prompt` or `wrap_model_call(...)` to assemble:

- base system prompt
- skill-set prompt fragments
- remembered context
- retrieval snippets
- per-run instructions

### 3. Tool Error Middleware

Use `@wrap_tool_call` to convert exceptions into predictable agent-facing
payloads.

Good pattern:

```python
from collections.abc import Callable
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.types import Command


@wrap_tool_call
def safe_tool_errors(
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

### 4. Dynamic Model Selection Middleware

Use `wrap_model_call(...)` when:

- long context should trigger a bigger model
- deep reasoning mode should swap models
- tool-heavy tasks should use a stronger model

This is cleaner than hardcoding model selection in domain code.

### 5. Tool Selection Middleware

Filter tools at runtime instead of showing the model every registered tool.

That improves:

- prompt size
- tool accuracy
- permissions
- domain focus

Reference:

- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)

## Custom State Schema

If middleware needs durable per-run state, define it explicitly:

```python
from langchain.agents import AgentState
from typing_extensions import NotRequired


class PlatformState(AgentState):
    model_call_count: NotRequired[int]
    tool_call_count: NotRequired[int]
    active_skillsets: NotRequired[list[str]]
    remembered_context_summary: NotRequired[str]
    prompt_budget_tokens: NotRequired[int]
```

Use that when you want middleware to coordinate with other middleware or with a
UI surface.

## A Good Middleware Stack Order

A practical default order:

1. state seeding
2. dynamic prompt assembly
3. runtime model selection
4. tool selection
5. built-in todo/HITL/summarization middleware
6. tool error middleware
7. token/usage tracking
8. output validation

Remember the execution rules:

- `before_*`: first to last
- `after_*`: last to first
- `wrap_*`: nested in list order

## Streaming

Runtime also exposes a stream writer.

That is the right place to emit:

- progress updates
- phase transitions
- retrieval progress
- tool summaries

Use this instead of inventing a UI-only side channel.

Reference:

- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Stream writer](https://docs.langchain.com/oss/python/langchain/tools#stream-writer)

## Prompt Caching

If you use Anthropic or another provider with prompt-caching semantics, keep
that in middleware at the system-message/content-block layer, not in app code.

This lets one runtime profile opt into cached prompt sections without changing
domain agents.

Reference:

- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)

## Practical Recommendation

For a reusable package:

- prefer decorator middleware for very small hooks
- prefer class-based middleware for shared, configurable behaviors
- always keep public tool args JSON-safe
- treat runtime injection as the dependency boundary
- keep tool error shaping and prompt assembly out of domain code

## References

- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
