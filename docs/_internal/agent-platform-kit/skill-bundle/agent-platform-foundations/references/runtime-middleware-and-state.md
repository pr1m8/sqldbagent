# Runtime, Middleware, And State

Keep these boundaries clear:

- `context`: immutable typed per-run business context
- `Runtime`: node and node-style middleware injection surface
- `ToolRuntime`: tool injection surface with `state`, `config`, and `tool_call_id`
- `RunnableConfig`: tracing and execution config
- `state`: short-term mutable graph or thread state
- `store`: long-term reusable memory

## Tool Schema Rule

Public tool arguments must be JSON-safe.

Prefer plain `ToolRuntime[...]` for normal tool injection.

If tools are exported through extra schema-generating layers, a safer interop
pattern can be:

```python
runtime: Annotated[ToolRuntime[AgentContext] | None, InjectedToolArg] = None
```

## Middleware Hook Types

Node-style hooks:

- `before_agent`
- `before_model`
- `after_model`
- `after_agent`

Wrap-style hooks:

- `wrap_model_call`
- `wrap_tool_call`

Use node-style hooks for:

- validation
- state seeding
- counters
- jump logic

Use wrap-style hooks for:

- retries
- short-circuiting
- error shaping
- model overrides
- tool monitoring
- tool filtering

## Middleware Role

Middleware should own:

- prompt assembly
- state seeding
- model routing
- tool error shaping
- HITL
- summarization
- usage tracking

## Dynamic Prompt

Treat dynamic prompt assembly as the default instruction path.

Build the effective prompt from:

- stable base instructions
- skill or domain fragments
- runtime context
- durable store memory
- retrieval overlays
- current-task guidance

Do not let frontend code or route handlers own prompt construction.

## Decorator Examples

### `before_model`

```python
@before_model(can_jump_to=["end"])
def check_limit(state: AgentState, runtime: Runtime) -> dict | None:
    if len(state["messages"]) > 50:
        return {"jump_to": "end"}
    return None
```

### `wrap_model_call`

```python
@wrap_model_call
def retry_model(request, handler):
    for attempt in range(3):
        try:
            return handler(request)
        except Exception:
            if attempt == 2:
                raise
```

### `wrap_tool_call`

```python
@wrap_tool_call
def monitor_tool(request, handler):
    print(request.tool_call["name"])
    return handler(request)
```

## Class-Based Middleware

Use a class when:

- several hooks belong together
- config should live on the middleware object
- sync and async implementations should live together

## State Updates

- node-style hooks return a plain `dict`
- wrap-style model hooks return `ExtendedModelResponse` with a `Command`
- tool state updates should prefer explicit `Command(update=...)`

## Built-In Middleware

Prefer built-ins when they fit:

- `HumanInTheLoopMiddleware`
- `SummarizationMiddleware`
- `TodoListMiddleware`

## Prompt Caching

If a provider supports prompt caching, keep that logic in middleware at the
system-message or content-block layer rather than in UI code.

## Multi-Agent Prompt Rule

In multi-agent systems:

- each graph should assemble its own prompt
- parent graphs should pass typed context, not giant prompt blobs
- specialist graphs should own their own instructions and tool policy

## Async And Streaming

Use async when the work is I/O-bound:

- remote tools
- retrieval backends
- document loaders
- multi-service fan-out

Use streaming when the product needs progressive updates instead of one final
response.

Good pattern:

- async tools for remote work
- `runtime.stream_writer` for tool progress
- graph streaming for workflow-level updates

## References

- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)
- [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
