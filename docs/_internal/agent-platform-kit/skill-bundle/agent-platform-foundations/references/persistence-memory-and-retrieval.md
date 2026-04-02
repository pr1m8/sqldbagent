# Persistence, Memory, And Retrieval

## Three Different Systems

### Checkpointer

Use for:

- thread continuity
- resumability
- interrupts
- time travel

### Long-Term Store

Use for:

- user preferences
- remembered org facts
- reusable prompt instructions
- validated summaries worth keeping

### Retrieval

Use for:

- large searchable corpora
- semantic grounding
- snippet retrieval for prompts or tools

Do not collapse these into one thing.

## Good Defaults

- tests:
  - memory checkpointer
  - memory store
- durable local or prod:
  - Postgres checkpointer
  - Postgres store
- retrieval:
  - off until you actually need it
  - Qdrant once semantic retrieval becomes justified

## Postgres Patterns

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

## Namespace Pattern

Use structured namespaces, for example:

```python
("org", org_id, "user", user_id, "agent", "researcher")
```

That makes filtering, cleanup, and reuse much cleaner than flat keys.

## Qdrant Guidance

Prefer:

- deterministic collection names
- metadata-heavy payloads
- collections per app or domain family, not per thread

Useful payload fields:

- `tenant_id`
- `agent_family`
- `artifact_type`
- `document_id`
- `scope_id`
- `source`

## Memory Write Policy

Use narrow, explicit memory-write tools or middleware-controlled writes.

Avoid letting every tool mutate memory by default.

References:

- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)
- [Custom store](https://docs.langchain.com/langsmith/custom-store)
- [Qdrant docs](https://qdrant.tech/documentation/)
