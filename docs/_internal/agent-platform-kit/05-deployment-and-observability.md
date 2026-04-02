# Deployment, LangSmith, And The SDK/CLI

## Local Development

The local development path should be standardized.

For LangGraph-compatible apps, use:

- `langgraph dev`
- `langgraph build`
- `langgraph up`

Keep the configuration in `langgraph.json` so local dev, CI, and hosted
deployment all use the same graph entrypoints and environment shape.

Reference:

- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)

## Recommended `langgraph.json` Shape

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

If you use a custom store or custom checkpointer, the app should still expose
async context managers so the runtime owns lifecycle cleanly.

## LangSmith Deployment

LangSmith deployment is a very good default when you want:

- managed hosting for LangGraph-compatible apps
- stateful agent execution
- deployment from GitHub
- Studio access
- remote run APIs

The main point is not "just deploy the app". It is:

- deployment
- traces
- thread/runs
- runtime hosting
- testing/evaluation

all in one ecosystem.

Reference:

- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)

## LangSmith Tracing

Treat tracing as a first-class platform feature.

Standardize:

- project name
- tags
- environment label
- agent family
- runtime profile
- tenant or org metadata where allowed

That makes traces queryable across many agents.

Good default tags:

- `agentkit`
- `env:dev`
- `agent:researcher`
- `runtime:balanced`

Reference:

- [Trace LangChain applications](https://docs.langchain.com/langsmith/trace-with-langchain)

## LangGraph SDK

Use `langgraph-sdk` for:

- remote client usage
- streaming deployed runs
- threadless or threaded runs
- integration tests against deployed graphs

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

Reference:

- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)

## Standard Deployment Modules

A reusable platform should have:

```text
agentkit/
  deploy/
    config.py
    langgraph.py
    langsmith.py
    sdk.py
```

Suggested responsibilities:

- `config.py`
  - env loading
  - deployment settings
  - defaults for tracing and tags

- `langgraph.py`
  - local graph entrypoint wiring
  - `langgraph.json` conventions

- `langsmith.py`
  - trace config helpers
  - project/tag naming
  - deployment metadata helpers

- `sdk.py`
  - sync/async remote client factories

## Environment Variables To Standardize

Keep these stable across repos:

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

If you later wrap these in repo-specific settings, keep the semantic meaning
unchanged.

## CLI Conventions

If the reusable layer ships a CLI, keep it focused on:

- local run
- local dev server
- deployment smoke tests
- trace configuration checks
- store/checkpointer diagnostics

Examples:

```bash
agentkit config validate
agentkit dev
agentkit run
agentkit trace ping
agentkit persistence check
agentkit sdk smoke
```

## Operational Checks Worth Automating

- can the checkpointer connect
- can the store connect
- does the runtime load the graph entrypoint
- does the deployment client stream one run successfully
- is tracing enabled and pointed at the intended project
- is the retrieval backend reachable if configured

## Practical Recommendation

For a reusable platform:

- standardize `langgraph.json`
- standardize tracing tags and naming
- keep a small deployment CLI
- use `langgraph-sdk` for remote smoke tests and app integration
- keep deployment config separate from domain skill sets

## References

- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
- [LangSmith deployment components](https://docs.langchain.com/langsmith/components)
- [Trace LangChain applications](https://docs.langchain.com/langsmith/trace-with-langchain)
