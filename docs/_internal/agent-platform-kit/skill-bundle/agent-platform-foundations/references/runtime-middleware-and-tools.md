# Runtime, Middleware, And Tools

## Runtime Context

Use runtime context for request-scoped facts and injected dependencies.

Good examples:

- user or org identifiers
- environment
- runtime profile
- store access
- stream writer access

Avoid hiding those in globals.

## JSON-Safe Tool Schemas

Public tool arguments must be JSON-serializable.

Use:

- `str`
- `int`
- `float`
- `bool`
- `list`
- `dict`
- Pydantic models with JSON-compatible fields

Do not expose Python runtime objects directly in tool signatures.

## `ToolRuntime` Example

```python
from typing import Annotated

from langchain.tools import ToolRuntime
from langchain_core.tools import InjectedToolArg, tool


@tool
def load_memory_note(
    key: str,
    runtime: Annotated[ToolRuntime[AgentContext] | None, InjectedToolArg] = None,
) -> dict:
    if runtime is None or runtime.store is None:
        return {"key": key, "value": None}

    record = runtime.store.get(("org", runtime.context.org_id), key)
    return {"key": key, "value": record.value if record else None}
```

That keeps runtime injected at execution time without leaking into the published
schema.

## Decorator Middleware

Start here first.

Useful decorators:

- `@before_agent`
- `@before_model`
- `@after_model`
- `@after_agent`
- `@wrap_model_call`
- `@wrap_tool_call`
- `@dynamic_prompt`

## Recommended Middleware Layers

1. state seeding
2. dynamic prompt assembly
3. runtime model selection
4. tool selection or permissioning
5. built-in summarization or HITL middleware
6. tool error shaping
7. token and usage tracking
8. output validation

## Prompt Policy

Build prompts from layers:

- base prompt
- skill-set instructions
- remembered context
- retrieved context
- task-specific instructions

Do not let route handlers or UI callbacks own that logic.

Reference:

- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
