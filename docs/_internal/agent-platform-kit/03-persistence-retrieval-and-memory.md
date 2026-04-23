# Persistence, Retrieval, And Memory

## The Three Persistence Systems

Model these as different systems.

### Checkpointer

Purpose:

- persist thread state
- resume long-running agents
- support interrupts and time travel

Good defaults:

- memory for tests
- Postgres for durable local and production setups

### Long-Term Store

Purpose:

- remember user or org preferences
- remember durable reusable facts
- keep long-term memory across threads

Good defaults:

- memory for tests
- Postgres store for durable use

### Retrieval System

Purpose:

- search large corpora or document collections
- ground responses in indexed material
- augment prompts with relevant snippets

Good default:

- off by default
- Qdrant when semantic retrieval is actually needed

Retrieval should not replace:

- the checkpointer
- the store
- typed context
- durable exported artifacts

## Namespace Design

Do not use flat namespaces.

Use something like:

```python
("org", org_id, "user", user_id, "agent", agent_family, "scope", scope_id)
```

This gives you:

- isolation
- targeted cleanup
- reuse
- better semantic-search boundaries

## What Belongs In The Store

Good store content:

- user preferences
- org conventions
- validated summaries
- reusable prompt instructions
- preferred tools or domains

Bad store content:

- every raw conversation turn
- large corpora that belong in retrieval
- transient execution state

## Retrieval Is Downstream Of Durable Artifacts

For this platform shape, the order of trust should usually be:

1. typed `context`
2. short-term `state`
3. durable `store`
4. durable snapshot or prompt artifacts
5. retrieval over those artifacts
6. live external queries when the above still leave a gap

That means vector indexes should be treated as reproducible derivatives.

## What To Index

Good sources to index:

- snapshot-derived object documents
- schema summaries
- prompt artifacts
- durable docs exports
- validated long-term memory summaries when intentional

Usually avoid indexing:

- raw transcripts by default
- large row dumps
- every intermediate tool payload
- mutable in-flight UI state

## Embedding Model Selection

Choose one embedding profile per retrieval profile.

Good criteria:

- dimensionality and cost
- provider availability
- latency budget
- cross-tenant consistency
- whether you need local or hosted embeddings

Keep the embedding model part of the deterministic collection identity.

## Collection Identity And Metadata

Use deterministic collection names:

```python
collection_name = (
    f"agentkit__{tenant_id}__{scope_slug}__{embedding_model_slug}"
)
```

Prefer rich payload metadata and narrow retrieval over giant undifferentiated
collections.

Useful payload fields:

- `tenant_id`
- `agent_family`
- `datasource`
- `schema`
- `artifact_type`
- `snapshot_id`
- `document_id`
- `document_hash`
- `embedding_model`

## Recommended Cache Layers

Treat retrieval as three separate cacheable layers.

### 1. Document Fingerprint Layer

Key ingredients:

- canonical source id
- source version or snapshot id
- normalized content hash
- embedding model slug

Purpose:

- detect unchanged inputs
- skip unnecessary re-embedding
- keep rebuilds deterministic

### 2. Embedding Cache Layer

Cache the embedding vector keyed by:

- `document_hash`
- `embedding_model`

This cache should live under the artifact root or another app-controlled path,
not in random temp directories.

### 3. Index Manifest Layer

Persist a manifest with:

- collection name
- embedding model
- snapshot or scope id
- document count
- document hashes
- build timestamp
- build version

Purpose:

- prove what is currently indexed
- detect stale collections
- support `ensure`, `rebuild`, and `reset` behavior cleanly

## Directory Layout

```text
var/agentkit/
  retrieval/
    manifests/
      <scope>.json
    embeddings/
      <embedding-model>/
        <document-hash>.json
    exports/
      <scope>/
        <document-id>.json
```

## `ensure` Versus `rebuild` Versus `reset`

These should be different operations.

### `ensure`

- if a valid manifest exists and the indexed document set matches, do nothing
- if the index is missing or stale, build what is needed

Best for:

- normal runtime flows
- dashboards
- local development

### `rebuild`

- recompute the manifest against the current source documents
- re-embed only documents whose hashes changed if the embedding cache is valid
- reconcile the vector store to the intended current set

Best for:

- after snapshot refresh
- after prompt or doc export changes
- after payload-shape or chunking changes

### `reset`

- explicitly clear some or all retrieval state
- may include manifest deletion, embedding-cache invalidation, and vector
  collection deletion depending on scope

Best for:

- broken collection state
- embedding model migration
- major schema or payload-shape changes
- clean-room rebuild testing

Use the narrowest reset that solves the actual problem.

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

## Practical Qdrant Setup

```python
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


def build_retriever(
    *,
    qdrant_url: str,
    collection_name: str,
    embedding_model: str,
):
    client = QdrantClient(url=qdrant_url)
    embeddings = OpenAIEmbeddings(model=embedding_model)
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
    return vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 6, "fetch_k": 20},
    )
```

## Memory Write Policy

Do not let every tool write to memory.

Prefer one narrow memory-write tool or middleware-controlled writes.

Examples:

- `remember_user_preference`
- `save_research_summary`
- `sync_domain_context`

## Practical Recommendation

For a reusable platform:

- default to Postgres for both checkpoint and store
- keep retrieval optional
- keep manifests and embedding caches explicit
- prefer `ensure` for normal flows
- use `rebuild` after source changes
- reserve `reset` for explicit maintenance or migration

## References

- [Configure checkpointer backend](https://docs.langchain.com/langsmith/configure-checkpointer)
- [Custom store](https://docs.langchain.com/langsmith/custom-store)
- [Vector store integrations](https://docs.langchain.com/oss/python/integrations/vectorstores/index)
- [Retriever integrations](https://docs.langchain.com/oss/python/integrations/retrievers/index)
- [OpenAI integrations](https://docs.langchain.com/oss/python/integrations/providers/openai)
- [Qdrant docs](https://qdrant.tech/documentation/)
