# Operations And Adoption

## Install Baseline

Minimal baseline:

```bash
pdm add langchain langgraph langsmith
```

Add provider support:

```bash
pdm add langchain-openai
pdm add langchain-anthropic
```

Add durable Postgres-backed checkpointing and store:

```bash
pdm add langgraph-checkpoint-postgres psycopg
```

Add retrieval only if needed:

```bash
pdm add qdrant-client langchain-qdrant
```

Add optional provider routing and token counting:

```bash
pdm add litellm tiktoken
```

## Local Development Path

For LangGraph-compatible apps, standardize around:

- `langgraph dev`
- `langgraph build`
- `langgraph up`

Keep configuration in `langgraph.json` so local dev, CI, and hosted deployment
share the same graph entrypoints and environment shape.

## Recommended `langgraph.json`

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

If you use a custom store or custom checkpointer, keep lifecycle managed
through async context managers owned by the runtime.

## LangSmith

Treat LangSmith as:

- deployment surface
- trace surface
- evaluation surface
- runtime hosting surface

Standardize:

- project name
- tags
- environment labels
- agent family labels
- runtime profile labels

Good default tags:

- `agentkit`
- `env:dev`
- `agent:researcher`
- `runtime:balanced`

## `langgraph-sdk`

Use `langgraph-sdk` for:

- remote client usage
- streaming deployed runs
- integration tests against deployed graphs
- deployment smoke tests

Example:

```python
from langgraph_sdk import get_sync_client


client = get_sync_client(
    url="https://my-deployment.example.com",
    api_key="...",
)

for chunk in client.runs.stream(
    None,
    "agent",
    input={
        "messages": [
            {"role": "human", "content": "Summarize the deployment plan."}
        ]
    },
    stream_mode="updates",
):
    print(chunk.event, chunk.data)
```

## Environment Conventions

Keep these meanings stable across repos:

```text
AGENTKIT_ENV=dev
AGENTKIT_LOG_LEVEL=INFO

LANGSMITH_API_KEY=...
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=agentkit-dev

AGENTKIT_CHECKPOINT_BACKEND=postgres
AGENTKIT_CHECKPOINT_POSTGRES_URL=postgresql://...

AGENTKIT_STORE_BACKEND=postgres
AGENTKIT_STORE_POSTGRES_URL=postgresql://...

AGENTKIT_QDRANT_URL=http://127.0.0.1:6333
AGENTKIT_QDRANT_API_KEY=
```

## CLI Conventions

If the reusable layer ships a CLI, keep it focused on:

- local run
- local dev server
- deployment smoke tests
- trace configuration checks
- store and checkpointer diagnostics
- retrieval diagnostics

Examples:

```bash
agentkit config validate
agentkit dev
agentkit run
agentkit trace ping
agentkit persistence check
agentkit retrieval ensure
agentkit retrieval rebuild
agentkit retrieval reset
agentkit sdk smoke
```

## Website And App Integration Patterns

The cleanest production shape is usually:

- browser or app client owns presentation
- your backend owns auth and request shaping
- the deployed graph owns agent execution and persistence

### Pattern 1. Backend Route Talking To A Deployed Graph

Use this when a web app, admin panel, or internal dashboard needs an agent
behind a normal backend route.

```python
from dataclasses import dataclass

from fastapi import APIRouter
from langgraph.pregel.remote import RemoteGraph


@dataclass
class AppContext:
    user_id: str
    org_id: str
    plan: str


router = APIRouter()
remote_graph = RemoteGraph(
    "agent",
    url="https://agent.example.com",
    api_key="...",
)


@router.post("/api/agent/chat")
def chat(payload: dict) -> dict:
    config = {
        "configurable": {"thread_id": payload["thread_id"]},
        "tags": ["surface:web", "env:prod"],
        "metadata": {"route": "/api/agent/chat"},
    }

    result = remote_graph.invoke(
        {"messages": payload["messages"]},
        context=AppContext(
            user_id=payload["user_id"],
            org_id=payload["org_id"],
            plan=payload["plan"],
        ),
        config=config,
    )
    return result
```

Why this works well:

- auth stays in your backend
- the frontend stays thin
- the thread id stays explicit
- context is typed and reviewable
- LangSmith and LangGraph keep traces and persistence aligned

### Pattern 2. Local Graph In Tests, Remote Graph In Production

Keep your application code depending on a graph-like interface instead of
hardcoding a single runtime.

```python
class AgentGateway:
    def __init__(self, graph):
        self.graph = graph

    def run(self, messages, *, thread_id, context, config=None):
        merged_config = {
            "configurable": {"thread_id": thread_id},
            **(config or {}),
        }
        return self.graph.invoke(
            {"messages": messages},
            context=context,
            config=merged_config,
        )
```

Use:

- a compiled local graph in unit and integration tests
- `RemoteGraph` in staging and production

This keeps app code stable while the deployment target changes.

### Pattern 3. Specialist Graphs Behind A Parent Agent

If one agent should call another, use a separate deployment boundary.

Good use cases:

- a web assistant that calls a specialist researcher
- an operator agent that calls a document-analysis graph
- a workflow coordinator that delegates to domain-specific agents

The official `RemoteGraph` guidance is important here:

- use remote graphs from another deployment
- do not call the same deployment recursively
- keep thread ids explicit
- use UUIDs when combining remote graphs and checkpointed subgraphs

### Pattern 4. Retrieval As A Service Behind The Agent

For website or product integrations, do not let the frontend decide retrieval
policy.

Keep retrieval decisions in the agent layer:

- backend passes user and product context
- agent middleware decides whether retrieval is needed
- retriever tools fetch from the indexed corpora
- answer generation stays grounded in returned snippets

This keeps retrieval behavior consistent across:

- website chat
- internal dashboard chat
- API calls
- batch runs

## End-To-End Delivery Path

For a productized agent integration, the simplest complete path is:

1. define `context_schema`
2. build local graph with middleware, tools, checkpointer, and optional store
3. add retrieval only when static context and store memory are not enough
4. test locally with a compiled graph
5. standardize `langgraph.json`
6. deploy through LangSmith or a LangGraph-compatible server path
7. integrate through `langgraph-sdk` or `RemoteGraph`
8. keep frontend or product code talking to a stable backend interface

## Good Final Integration Boundaries

Keep these ownership lines clean:

- frontend:
  - rendering, input controls, optimistic UX
- backend app:
  - auth, tenancy, request shaping, rate limits
- agent runtime:
  - middleware, prompts, tools, retrieval policy, persistence
- persistence systems:
  - checkpoints, store memory, vector retrieval backend

If these layers blur together, debugging gets expensive very quickly.

## Operational Checks Worth Automating

- can the checkpointer connect
- can the store connect
- does the runtime load the graph entrypoint
- does the deployment client stream one run successfully
- is tracing enabled and pointed at the intended project
- is the retrieval backend reachable if configured
- do retrieval manifests match the current source documents

## Extraction Plan

### Goal

Extract the current agent stack into a reusable platform package without
breaking the proving-ground domain app.

### Target Split

#### Reusable Platform Package

Owns:

- build specs
- runtime profiles
- persistence profiles
- prompt composer
- middleware registries
- checkpointer and store factories
- LangSmith helpers
- LangGraph CLI and deploy helpers
- generic tool and runtime conventions

#### Domain Package

Owns:

- domain tools
- domain prompt fragments
- domain retrieval indexing rules
- domain UI surfaces
- domain-safe write policies

### Suggested Migration Order

1. extract persistence and tracing helpers
2. extract runtime profiles and builder
3. extract prompt composition and middleware
4. extract deployment and SDK helpers
5. refit the domain app to consume the platform package

### What Not To Extract Too Early

Do not generalize too early:

- SQL safety logic
- SQL prompt fragments
- SQL-specific retrieval payloads
- dashboard-specific state payloads

## Quality Bar

Before extracting, make sure the platform layer has:

- explicit runtime context schema
- explicit state schema
- explicit persistence factories
- explicit tool schema rules
- tests for JSON-safe tool args
- tests for middleware ordering and state updates
- tests for store and checkpointer fallback behavior

## Practical Recommendation

Keep the reusable package shape inside the domain repo first. Split it into a
separate package only after the abstractions survive real use.

## References

- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
- [LangSmith deployment components](https://docs.langchain.com/langsmith/components)
- [Trace LangChain applications](https://docs.langchain.com/langsmith/trace-with-langchain)
- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [How to interact with a deployment using RemoteGraph](https://docs.langchain.com/langsmith/use-remote-graph)
