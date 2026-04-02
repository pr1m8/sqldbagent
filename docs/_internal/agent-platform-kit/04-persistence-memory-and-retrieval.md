# Persistence, Memory, And Retrieval

## The Three Persistence Systems

A reusable agent platform should model these as different systems:

### 1. Checkpointer

Purpose:

- persist thread state
- resume long-running agents
- support interrupts and time travel

Good defaults:

- memory for tests
- Postgres for durable local/prod
- Mongo only if you already run it and want checkpoint data there

Reference:

- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)

### 2. Long-Term Store

Purpose:

- remember user or org preferences
- remember domain facts worth keeping across threads
- support semantic search if the backend provides it

Good defaults:

- memory for tests
- Postgres store for durable use
- custom store only when you need a different storage/search model

Reference:

- [How to use a custom store](https://docs.langchain.com/langsmith/custom-store)

### 3. Retrieval System

Purpose:

- search large corpora or document collections
- ground responses in indexed material
- augment prompts with relevant snippets

Good defaults:

- off by default
- Qdrant when semantic retrieval is actually needed

Retrieval should not replace:

- the checkpointer
- the long-term store
- structured domain state

## Recommended Persistence Profiles

### `ephemeral`

- checkpointer: memory
- store: memory
- retrieval: optional local/dev only

Best for:

- tests
- throwaway experiments
- local demos that do not need durability

### `thread_durable`

- checkpointer: Postgres
- store: memory

Best for:

- durable threads
- cheap setup
- apps where you do not need cross-thread memory yet

### `fully_durable`

- checkpointer: Postgres
- store: Postgres
- retrieval: Qdrant or another store if needed

Best for:

- production assistants
- internal copilots
- org knowledge workflows

## Namespace Design For Long-Term Memory

Do not use a flat namespace.

Use something like:

```python
("org", org_id, "user", user_id, "agent", agent_family, "scope", scope_id)
```

Examples:

- `("org", "acme", "user", "u123", "agent", "researcher")`
- `("org", "acme", "agent", "ops", "env", "prod")`
- `("org", "acme", "user", "u123", "agent", "sql", "datasource", "warehouse")`

This gives you:

- isolation
- reuse
- targeted cleanup
- better semantic search boundaries

## What Belongs In The Store

Good store content:

- user preferences
- org conventions
- remembered glossary/business terms
- validated summaries
- prompt instructions worth reusing
- preferred tools or preferred domains

Bad store content:

- every raw conversation turn
- giant prompt blobs
- large corpora that belong in retrieval
- transient execution state

## Postgres Checkpointer Example

```python
from contextlib import contextmanager
from langgraph.checkpoint.postgres import PostgresSaver


@contextmanager
def create_sync_checkpointer(dsn: str):
    with PostgresSaver.from_conn_string(dsn) as saver:
        saver.setup()
        yield saver
```

## Postgres Store Example

```python
from contextlib import contextmanager
from langgraph.store.postgres import PostgresStore


@contextmanager
def create_sync_store(dsn: str):
    with PostgresStore.from_conn_string(dsn) as store:
        store.setup()
        yield store
```

## LangSmith Deployment Reality

One important detail from the current LangSmith docs:

- LangSmith may let you switch the checkpoint backend
- but PostgreSQL is still required for other deployment data
- and the built-in long-term memory store is still Postgres-backed unless you
  replace it with a custom store

That means:

- "custom checkpointer" does not mean "no Postgres anywhere"
- "custom store" is an explicit replacement step

References:

- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)
- [How to use a custom store](https://docs.langchain.com/langsmith/custom-store)

## Qdrant Guidance

Qdrant is a good retrieval backend when you need:

- metadata filters
- semantic search
- MMR or similarity retrieval
- explicit collection management

Recommended practice:

- do not create collections per thread
- prefer collections per app, domain, or datasource family
- use payload metadata heavily

Payload fields worth standardizing:

- `namespace`
- `tenant_id`
- `agent_family`
- `datasource`
- `schema`
- `artifact_type`
- `snapshot_id`
- `document_id`

## Retrieval Profiles

### `none`

- no retrieval

### `local_docs`

- embed prompt/docs artifacts
- small local collection
- low top-k

### `knowledge_base`

- shared Qdrant collection
- tenant-aware filters
- MMR
- larger fetch-k

### `domain_plus_memory`

- retrieval over docs plus long-term store summaries
- only for agents that benefit from both

## Example Qdrant Setup

```python
from langchain_qdrant import QdrantVectorStore


def build_vector_store(client, embeddings, collection_name: str):
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
```

Then keep collection naming deterministic:

```python
collection_name = f"agentkit__{tenant_id}__{domain}__{embedding_model_slug}"
```

## Memory Write Policy

Do not let every tool write to memory.

Prefer one narrow memory-write tool or middleware-controlled writes.

Examples:

- `remember_user_preference`
- `save_research_summary`
- `sync_domain_context`

This keeps memory useful instead of noisy.

## Practical Recommendation

For a reusable platform:

- default to Postgres for both checkpoint and store
- keep retrieval optional
- use namespace strategies, not flat keys
- separate thread continuity from reusable memory
- add memory writes through narrow, explicit paths

## References

- [LangChain runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)
- [How to use a custom checkpointer](https://docs.langchain.com/langsmith/custom-checkpointer)
- [How to use a custom store](https://docs.langchain.com/langsmith/custom-store)
