# Agent Architecture Notes

## Current Stance

Use LangChain v1 for agent ergonomics, but keep the product architecture stricter than the default SQL-agent tutorials.

That means:

- use `langchain.agents.create_agent(...)` as the main LangChain v1 entry point
- treat LangGraph as the runtime and persistence layer under that agent
- expose only `sqldbagent` tools by default
- do not make LangChain's generic SQL toolkit the primary execution path
- prefer stored snapshot context before live querying

## Why We Differ From The Default SQL Agent Shape

LangChain's SQL agent docs are useful, but they optimize for getting an agent to query a database quickly.

`sqldbagent` is trying to optimize for:

- normalized metadata first
- durable artifacts first
- guarded SQL only
- one reusable service layer for CLI, MCP, LangChain, LangGraph, and later UI surfaces

So our LangChain/LangGraph integration should sit on top of:

- inspection tools
- profiling tools
- snapshot load/list/diff flows
- retrieval over stored snapshot documents
- `safe_query_sql`

not on top of unconstrained SQL execution helpers.

## LangChain v1 Notes

Relevant current LangChain guidance:

- LangChain v1 `create_agent` is built on LangGraph
- LangGraph is the runtime that brings durable execution, interrupts, and persistence
- MCP is a supported interoperability path
- SQL agent tutorials exist, but they are examples, not our core architecture

Links:

- [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [Agent runtimes like LangGraph](https://docs.langchain.com/oss/python/concepts/products#agent-runtimes-like-langgraph)
- [LangChain SQL agent tutorial](https://docs.langchain.com/oss/python/langchain/sql-agent)
- [LangGraph SQL agent tutorial](https://docs.langchain.com/oss/python/langgraph/sql-agent)
- [LangChain MCP docs](https://docs.langchain.com/oss/python/langchain/mcp)

## Middleware And Decorators

LangChain v1 middleware is not an optional afterthought for this repo. It is the
right place to encode the agent contract.

What we should take from LangChain v1:

- `@dynamic_prompt` for rich, snapshot-aware system prompts
- `@before_agent` for seeding repo state like datasource, schema, snapshot summary, and dashboard payload
- `@after_agent` for compressing tool-call history into reusable digest state
- `@wrap_tool_call` for structured tool error handling and repo-specific guidance
- built-in `TodoListMiddleware` for long, multi-step agent workflows
- built-in `HumanInTheLoopMiddleware` for guarded approval on `safe_query_sql`
- built-in `SummarizationMiddleware` when sessions approach the context ceiling

Repo decisions:

- prompts should be large, descriptive, and grounded in stored snapshot context
- prompt exports should be durable artifacts with JSON and Markdown forms so operators can review and reuse them outside a live agent run
- state should be dashboard-friendly and reusable for future UI surfaces
- the first chat UI should stay Python-first and thin, using Streamlit over the persisted LangGraph agent instead of a separate frontend stack
- tool-call digests should retain high-signal results without preserving every raw tool payload forever
- summarization should trigger around 90% of context when enabled
- HITL should be aimed first at `safe_query_sql`, not inspection tools
- linting and normalized SQL should stay visible in the `safe_query_sql` tool result
- retrieval should be exposed as an explicit helper tool on the agent, not hidden as a side effect
- retrieval should index stored snapshot documents into Qdrant with stable payload metadata for datasource, schema, snapshot, and object type filtering

## Checkpointing

Use Postgres as the standard persisted checkpointer target for local and integration work.

Package decisions:

- `langgraph`
- `langgraph-sdk`
- `langgraph-checkpoint-postgres`
- `psycopg`
- `psycopg-pool`

Implementation decisions:

- support both `PostgresSaver` and `AsyncPostgresSaver`
- auto-setup checkpoint tables by default
- allow memory checkpointers for tests and light local runs
- prefer standard `POSTGRES_*` env vars and synthesize checkpoint URLs when possible
- use `.env`-loaded settings as the source of truth for live integration and E2E tests
- keep `make up` as the standard way to raise the local integration stack
- treat the checkpoint Postgres as persistence infrastructure; it may share the demo compose stack with an inspected Postgres datasource locally, but should usually be separate in real deployments

## Retrieval

Current retrieval stance:

- export schema snapshots into stored document bundles first
- cache embeddings on disk so repeated indexing stays cheap
- index those documents into Qdrant with stable metadata filters
- expose retrieval as a helper tool for the agent, MCP, and CLI
- keep live SQL as a follow-up path when retrieval and metadata still leave gaps

Implementation decisions:

- default retrieval backend is Qdrant
- default document source is stored snapshot exports, not raw row dumps
- LangChain community `SQLDatabaseLoader` is a secondary helper for targeted row-to-document workflows, not the main architecture
- `langgraph.json` should point at the local project root and let `pyproject.toml` define dependencies
- FastMCP transport defaults should come from `.env` so stdio, SSE, HTTP, and streamable HTTP can be switched without code edits

## Next Agent Work

Completed agent milestones:

1. strict sqldbagent agent builder over our own tools
2. sync and async Postgres checkpoint factories
3. snapshot summary injection into system prompts
4. state schema and dashboard-oriented state payloads
5. approval / interrupt strategy for risky tool calls
6. context summarization and tool-call compression
7. LangSmith-aware dashboard tracing context and observability status plumbing

Current next agent milestones should be:

1. richer LangGraph workflow composition beyond the single-agent loop
2. live LangSmith trace validation against real model-backed turns
3. more dashboard affordances for artifacts, retrieval, and query review
