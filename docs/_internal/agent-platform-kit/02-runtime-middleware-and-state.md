# Runtime, Middleware, And State

## Core Boundary

Keep these concepts separate:

- `context`: immutable typed per-run business context
- `Runtime`: injected into nodes and node-style middleware
- `ToolRuntime`: injected into tools and includes tool-specific fields
- `RunnableConfig`: execution and tracing config
- `state`: mutable short-term graph or thread state
- `store`: long-term reusable memory
- `checkpointer`: thread persistence and resumability

If you blur these together, the rest of the architecture gets hard to reason
about quickly.

## `context`

Use `context_schema` to define typed per-run context passed to `create_agent`.

Good examples:

- user id
- org id
- tenant id
- request environment
- authenticated capabilities
- feature flags
- request-scoped adapters or service handles

Bad examples:

- message history
- tracing tags
- callback handlers
- long-term memory
- mutable execution counters

If the model or tools should reason over it semantically and it should not
change mid-run, it is a good `context` candidate.

## `Runtime` Versus `ToolRuntime`

### `Runtime`

Use `Runtime` in:

- graph nodes
- node-style middleware hooks such as `before_model` and `after_model`

It exposes:

- `context`
- `store`
- `stream_writer`

### `ToolRuntime`

Use `ToolRuntime` in tools.

It exposes everything above plus:

- `state`
- `config`
- `tool_call_id`

That extra surface is why tools should use `ToolRuntime` rather than trying to
infer execution details indirectly.

## `RunnableConfig`

`RunnableConfig` is not the same thing as runtime context.

Treat it as per-execution operational config:

- tracing tags
- metadata
- callbacks
- run name
- recursion limit
- concurrency controls
- `configurable` values for configurable runnables

Good uses:

- tagging a run as `env:prod` or `surface:dashboard`
- attaching request metadata for tracing
- setting `run_name` for diagnostics
- passing runtime overrides for configurable runnables

Bad uses:

- user identity
- domain context tools must reason over
- large business payloads
- durable memory

## `context` Versus `RunnableConfig`

A practical rule:

- use `context` for typed domain-aware immutable per-run data
- use `RunnableConfig` for tracing, callbacks, limits, and runnable-level
  configuration

## Tool Schema Rule

Public tool arguments must stay JSON-serializable.

Use:

- `str`
- `int`
- `float`
- `bool`
- `list`
- `dict`
- Pydantic models with JSON-compatible fields

Do not expose Python runtime objects directly in tool schemas.

## `ToolRuntime` Pattern

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

The official docs show the simpler `runtime: ToolRuntime[...]` pattern, and
that should stay your default. The explicit `InjectedToolArg` form is a good
defensive choice when tools are exported through additional schema-producing
adapter layers.

## `state` Versus `store`

### `state`

Use state for short-term memory:

- messages
- counters
- active plan or todo data
- per-thread UI payload
- per-run summaries

### `store`

Use store for long-term reusable memory:

- durable preferences
- validated org notes
- reusable summaries
- remembered context across threads

Do not use the store as a transcript bucket.

When a tool needs to update state, prefer returning `Command(update=...)`.

## Middleware Roles

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

## Dynamic Prompt Is First-Class

Do not treat the system prompt as a static string owned by UI code or route
handlers.

Use middleware to assemble the effective prompt from explicit layers:

1. stable base instructions
2. skill-set or domain instructions
3. runtime-context overlays
4. durable store-memory overlays
5. retrieval overlays
6. current-task overlays

This keeps prompt construction:

- testable
- shared across website, CLI, dashboard, and API surfaces
- separate from transport or presentation code

The prompt should be assembled, not hand-concatenated across random callers.

## Middleware Hook Model

LangChain custom middleware has two broad styles.

### Node-Style State Updates

These run at fixed points in the agent lifecycle.

Available hooks:

- `before_agent`
- `before_model`
- `after_model`
- `after_agent`

Use node-style hooks for:

- logging
- validation
- state seeding
- state counters
- jump conditions

They return a `dict` of state updates or `None`.

### Wrap-Style State Updates

These run around each model or tool call.

Available hooks:

- `wrap_model_call`
- `wrap_tool_call`

Use wrap-style hooks for:

- retries
- short-circuiting
- fallback behavior
- tool monitoring
- tool error shaping
- model overrides
- dynamic tool filtering

They control if the wrapped handler is called zero, one, or multiple times.

### Decorator Middleware

Best when:

- one hook is enough
- the behavior is focused
- you are prototyping

Useful decorators:

- `@before_agent`
- `@before_model`
- `@after_model`
- `@after_agent`
- `@wrap_model_call`
- `@wrap_tool_call`
- `@dynamic_prompt`

### Example: `@dynamic_prompt`

```python
from langchain.agents.middleware import ModelRequest, dynamic_prompt


@dynamic_prompt
def build_system_prompt(request: ModelRequest) -> str:
    context = request.runtime.context

    sections = [
        "You are a precise internal operations assistant.",
        f"ACTIVE TENANT: {context.org_id}",
        f"USER ROLE: {context.user_role}",
    ]

    if request.runtime.store:
        if note := request.runtime.store.get(("org", context.org_id), "style_guide"):
            sections.append(f"ORG STYLE GUIDE:\\n{note.value['text']}")

    return "\\n\\n".join(sections)
```

This is usually better than trying to inject prompt text from:

- frontend state
- endpoint handlers
- environment wrappers
- ad hoc tool output plumbing

### Example: Node-Style `before_model`

```python
from typing import Any

from langchain.agents.middleware import AgentState, before_model
from langchain.messages import AIMessage
from langgraph.runtime import Runtime


@before_model(can_jump_to=["end"])
def check_message_limit(
    state: AgentState,
    runtime: Runtime[AgentContext],
) -> dict[str, Any] | None:
    if len(state["messages"]) >= 50:
        return {
            "messages": [AIMessage(content="Conversation limit reached.")],
            "jump_to": "end",
        }
    return None
```

Use this style when you want predictable state inspection before the model runs.

### Example: Wrap-Style `wrap_model_call`

```python
from collections.abc import Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call


@wrap_model_call
def retry_model(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    for attempt in range(3):
        try:
            return handler(request)
        except Exception:
            if attempt == 2:
                raise
    raise RuntimeError("Unreachable")
```

Use this style when control flow around the call matters.

### Example: Wrap-Style `wrap_tool_call`

```python
from collections.abc import Callable

from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.types import Command


@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    print(f"Executing tool: {request.tool_call['name']}")
    return handler(request)
```

Use this for monitoring, retries, error shaping, or permission checks.

### Class-Based Middleware

Best when:

- multiple hooks belong together
- config or state lives on the middleware object
- both sync and async implementations are needed

### Example: Class-Based Middleware

```python
from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.runtime import Runtime


class LoggingMiddleware(AgentMiddleware):
    def before_model(
        self,
        state: AgentState,
        runtime: Runtime[AgentContext],
    ) -> dict | None:
        print(f"Calling model with {len(state['messages'])} messages")
        return None

    async def abefore_model(
        self,
        state: AgentState,
        runtime: Runtime[AgentContext],
    ) -> dict | None:
        print(f"Calling model with {len(state['messages'])} messages")
        return None
```

Use class-based middleware when:

- one object should own several hooks
- sync and async variants should live together
- a reusable configurable behavior needs init-time settings

## Custom State Schema

If middleware needs durable per-run custom fields, define them explicitly.

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

This is the right way to support cross-hook coordination without inventing
implicit side channels.

## State Updates From Middleware

Node-style and wrap-style hooks update state differently.

### Node-Style Hooks

Return a plain `dict`.

```python
from typing import Any

from langchain.agents.middleware import after_model


@after_model(state_schema=PlatformState)
def increment_model_calls(
    state: PlatformState,
    runtime: Runtime[AgentContext],
) -> dict[str, Any] | None:
    return {"model_call_count": state.get("model_call_count", 0) + 1}
```

### Wrap-Style Hooks

Return an `ExtendedModelResponse` with a `Command`.

```python
from collections.abc import Callable

from langchain.agents.middleware import (
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
    wrap_model_call,
)
from langgraph.types import Command


@wrap_model_call(state_schema=PlatformState)
def track_usage(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ExtendedModelResponse:
    response = handler(request)
    return ExtendedModelResponse(
        model_response=response,
        command=Command(update={"last_model_call_tokens": 150}),
    )
```

Use node-style updates when you are just merging state around a known lifecycle
point. Use wrap-style updates when the update depends on the wrapped model-call
response or retry logic.

## Execution Order

When multiple middleware are installed:

- `before_*` hooks run first to last
- `after_*` hooks run last to first
- `wrap_*` hooks nest in list order

That means the first wrap middleware is the outermost wrapper.

Be intentional about order:

- permission and tool-filtering wrappers should usually be early
- low-level telemetry or logging wrappers can be later
- outer retry middleware may discard inner failed attempts

## Agent Jumps

Node-style hooks can jump to another part of the graph by returning `jump_to`.

Useful jump targets include:

- `"end"`
- `"tools"`
- `"model"`

Use jumps sparingly. They are powerful, but they make the control flow less
obvious if overused.

## Dynamic Prompt Patterns

There are two practical prompt patterns.

### `@dynamic_prompt`

Good when you are assembling a prompt from current state and runtime context in
a straightforward way.

### `wrap_model_call`

Good when you need to modify the `SystemMessage` content blocks directly,
preserve structure, or inject cache-control metadata.

Example:

```python
from collections.abc import Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain.messages import SystemMessage


@wrap_model_call
def add_context(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    new_content = list(request.system_message.content_blocks) + [
        {"type": "text", "text": "Additional context."}
    ]
    new_system_message = SystemMessage(content=new_content)
    return handler(request.override(system_message=new_system_message))
```

## Dynamic Model And Tool Selection

`wrap_model_call` is also the right place for:

- model upgrades on harder turns
- tool filtering based on state or permissions
- request-scoped cost controls

Example tool filtering pattern:

```python
from collections.abc import Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call


@wrap_model_call
def select_tools(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    relevant_tools = select_relevant_tools(request.state, request.runtime)
    return handler(request.override(tools=relevant_tools))
```

This keeps the registered tool set broad while keeping the per-turn prompt
surface narrow.

## Built-In Middleware

Prefer built-ins when they match the problem well.

Good examples from the current LangChain v1 surface:

- `HumanInTheLoopMiddleware`
- `SummarizationMiddleware`
- `TodoListMiddleware`

Use them where they fit instead of rebuilding every cross-cutting behavior
yourself.

## Prompt Caching

If you use Anthropic or another provider with prompt-caching semantics, keep
that in middleware at the `SystemMessage` content-block layer, not in route
code or UI code.

That lets one runtime profile opt into cached prompt sections without changing
domain-agent code.

## Best Practices

- keep each middleware focused
- prefer decorators for small single-hook behaviors
- prefer classes for configurable multi-hook behaviors
- document custom state fields explicitly
- test middleware in isolation
- be deliberate about middleware order
- use built-in middleware when it solves the real problem well

## Recommended Middleware Stack

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

Do not let UI callbacks or route handlers own this logic.

## Dynamic Prompt In Multi-Agent Systems

If you adopt a multi-agent topology:

- let each graph assemble its own prompt
- pass typed context across graph boundaries
- keep parent graphs responsible for orchestration context
- keep child graphs responsible for specialist instructions and tool policy
- do not forward one giant preassembled system prompt from parent to child by
  default

That keeps specialist graphs reusable instead of turning them into echoes of a
single parent agent.

## LangGraph Node Signature

```python
from dataclasses import dataclass
from typing_extensions import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime


class State(TypedDict):
    input: str
    results: str


@dataclass
class Context:
    user_id: str


def my_node(
    state: State,
    config: RunnableConfig,
    runtime: Runtime[Context],
) -> dict:
    ...
```

This keeps the mental model clear:

- `state` is mutable graph data
- `config` is execution config and tracing data
- `runtime` carries context, store, and streaming helpers

## Streaming

Use `runtime.stream_writer` for tool-level progress updates.

Use LangGraph graph streaming for graph-level or workflow-level updates.

Keep custom updates high-signal:

- progress updates
- phase transitions
- retrieval progress
- tool summaries

## Async And Streaming Rule Of Thumb

Async is usually worth it when:

- tools perform network I/O
- retrieval or document loading is remote
- one request fans out to several services
- you want responsive token or progress streaming in a web app

Good practical split:

- use sync tools and sync graph invocation for simple local workflows
- use async tools when the real work is I/O-bound
- stream updates as they happen instead of waiting for one final payload

In product integrations, this usually means:

- backend route streams partial updates to the UI
- tool code emits progress through `runtime.stream_writer`
- graph-level streaming exposes model, tool, and workflow updates

Do not make everything async by default. Use it where it improves concurrency,
latency, or user experience.

## References

- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)
- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [RunnableConfig reference](https://reference.langchain.com/python/langchain-core/runnables/config/RunnableConfig)
- [ToolRuntime reference](https://reference.langchain.com/python/langgraph.prebuilt/tool_node/ToolRuntime)
