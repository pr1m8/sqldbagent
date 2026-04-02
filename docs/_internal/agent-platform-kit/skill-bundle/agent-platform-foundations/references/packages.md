# Packages

## Core Platform Packages

| Package     | Why It Exists                                                      | Links                                                                                                             |
| ----------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `langchain` | high-level `create_agent`, tools, middleware, model init           | [Docs](https://docs.langchain.com/oss/python/releases/langchain-v1) · [PyPI](https://pypi.org/project/langchain/) |
| `langgraph` | runtime, state machine, persistence integration, CLI compatibility | [Docs](https://docs.langchain.com/oss/python/releases/langgraph-v1) · [PyPI](https://pypi.org/project/langgraph/) |
| `langsmith` | tracing, evaluation, deployment ecosystem                          | [Docs](https://docs.langchain.com/langsmith/home) · [PyPI](https://pypi.org/project/langsmith/)                   |

## Persistence And Deployment

| Package                         | Why It Exists                                                 | Links                                                           |
| ------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------- |
| `langgraph-checkpoint-postgres` | durable Postgres-backed checkpointing and store support       | [PyPI](https://pypi.org/project/langgraph-checkpoint-postgres/) |
| `psycopg`                       | Postgres driver for persistence infrastructure                | [PyPI](https://pypi.org/project/psycopg/)                       |
| `langgraph-sdk`                 | remote client for deployed graphs and integration smoke tests | [PyPI](https://pypi.org/project/langgraph-sdk/)                 |

## Provider And Retrieval Packages

| Package               | Why It Exists                                    | Links                                                                                        |
| --------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `langchain-openai`    | OpenAI chat and embeddings                       | [PyPI](https://pypi.org/project/langchain-openai/)                                           |
| `langchain-anthropic` | Anthropic chat models                            | [PyPI](https://pypi.org/project/langchain-anthropic/)                                        |
| `qdrant-client`       | Qdrant database client                           | [Docs](https://qdrant.tech/documentation/) · [PyPI](https://pypi.org/project/qdrant-client/) |
| `langchain-qdrant`    | LangChain vector store integration for Qdrant    | [PyPI](https://pypi.org/project/langchain-qdrant/)                                           |
| `litellm`             | optional routing layer for multi-provider setups | [PyPI](https://pypi.org/project/litellm/)                                                    |
| `tiktoken`            | token counting and prompt budget estimation      | [PyPI](https://pypi.org/project/tiktoken/)                                                   |

## Recommended Layering

- platform core:
  - `langchain`
  - `langgraph`
  - `langsmith`
- persistence extras:
  - `langgraph-checkpoint-postgres`
  - `psycopg`
- retrieval extras:
  - `qdrant-client`
  - `langchain-qdrant`
- provider extras:
  - `langchain-openai`
  - `langchain-anthropic`
  - `litellm`

## Interface Boundaries

Keep stable registries for:

- runtime profiles
- persistence profiles
- prompt profiles
- skill sets
- observability settings

That reduces import sprawl and makes agent assembly deterministic.
