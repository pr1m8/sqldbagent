# Persistence, Retrieval, And Memory

Keep these as separate systems:

- checkpointer for thread continuity
- store for long-term reusable memory
- retrieval for searchable corpora built from durable artifacts

## Namespace Rule

Use structured namespaces, for example:

```python
("org", org_id, "user", user_id, "agent", agent_family, "scope", scope_id)
```

## Retrieval Rule

Treat vector indexes as reproducible derivatives, not the source of truth.

Good retrieval inputs:

- snapshot-derived documents
- prompt artifacts
- docs exports

## Cache Layers

Keep three cache layers:

- document fingerprints
- embedding cache
- retrieval manifest

## Operations

Keep these distinct:

- `ensure`
- `rebuild`
- `reset`

## References

- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)
- [Custom store](https://docs.langchain.com/langsmith/custom-store)
- [Retriever integrations](https://docs.langchain.com/oss/python/integrations/retrievers/index)
- [Qdrant docs](https://qdrant.tech/documentation/)
