# Deployment And Observability

## Standard Local Path

Keep these stable:

- `langgraph dev`
- `langgraph build`
- `langgraph up`

Back them with a shared `langgraph.json`.

## `langgraph.json` Shape

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

## LangSmith

Treat LangSmith as:

- deployment surface
- trace surface
- evaluation surface
- runtime hosting surface

Standardize:

- project naming
- tags
- environment labels
- agent family labels

## `langgraph-sdk`

Use it for:

- remote smoke tests
- integration tests
- streaming deployed runs
- client-side automation against deployed graphs

## Environment Conventions

Keep env var meaning stable across repos:

```text
AGENTKIT_ENV=dev
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=agentkit-dev
AGENTKIT_CHECKPOINT_BACKEND=postgres
AGENTKIT_CHECKPOINT_POSTGRES_URL=postgresql://...
AGENTKIT_STORE_BACKEND=postgres
AGENTKIT_STORE_POSTGRES_URL=postgresql://...
AGENTKIT_QDRANT_URL=http://127.0.0.1:6333
```

## Operational Checks

Automate checks for:

- checkpointer connectivity
- store connectivity
- graph import and startup
- one streamed SDK run
- tracing enabled on the expected project
- retrieval backend availability if configured

References:

- [LangSmith deployment](https://docs.langchain.com/oss/python/langchain/deploy)
- [Trace LangChain applications](https://docs.langchain.com/langsmith/trace-with-langchain)
