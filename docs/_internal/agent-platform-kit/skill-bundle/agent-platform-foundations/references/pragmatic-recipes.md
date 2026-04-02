# Pragmatic Recipes

## Install Baseline

```bash
pdm add langchain langgraph langsmith
pdm add langchain-openai
pdm add langgraph-checkpoint-postgres psycopg
```

Optional:

```bash
pdm add qdrant-client langchain-qdrant
pdm add litellm tiktoken
pdm add langgraph-sdk
```

## Build A Small Agent

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI


def build_agent(*, tools, middleware, checkpointer=None, store=None):
    model = ChatOpenAI(model="gpt-5", reasoning={"effort": "high"})
    return create_agent(
        model=model,
        tools=tools,
        middleware=middleware,
        checkpointer=checkpointer,
        store=store,
        context_schema=AgentContext,
    )
```

## Add Retrieval Later

```python
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


def build_retriever(qdrant_url: str, collection_name: str):
    client = QdrantClient(url=qdrant_url)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
    )
    return store.as_retriever(search_type="mmr", search_kwargs={"k": 6, "fetch_k": 20})
```

## First Presets

Start with:

- `assistant_fast`
- `assistant_balanced`
- `researcher_balanced`
- `researcher_deep`
- `operator_balanced`

Do not build a giant preset matrix on day one.
