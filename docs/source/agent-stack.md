# Agent Stack

sqldbagent uses LangChain v1's `create_agent(...)` interface over LangGraph runtime primitives, with sqldbagent-owned tools, prompts, middleware, and persistence boundaries.

## Design Rules

- Use sqldbagent's service layer, not raw SQL toolkit calls, as the primary execution path.
- Seed agent state from stored snapshots so agents start with durable schema context.
- Keep safe SQL and retrieval as explicit tools.
- Keep prompt size observable through cached token estimates on prompt bundles and enhancements.
- Treat live prompt exploration as additive context layered on top of stored snapshots, not as a replacement for them.
- Use Postgres checkpointing for durable threads and in-session memory fallback for lightweight dashboard runs.
- Let LangSmith observe the same surfaces instead of adding a second tracing model.

## Middleware

The default middleware stack currently covers:

- state seeding from stored snapshot context
- dynamic prompts
- long-term remembered datasource/schema context injection
- tool error shaping
- tool digest compression
- optional todo middleware
- optional HITL middleware
- optional summarization middleware
- model and tool call limits

## Surfaces

- `langgraph dev` via `langgraph.json`
- Streamlit dashboard via `sqldbagent dashboard serve`
- FastMCP via `sqldbagent mcp serve`
- direct Python runtime usage through `sqldbagent.adapters.langgraph`

## Prompting And Context

- The base system prompt is always dialect-aware.
- Saved prompt enhancements can merge generated schema guidance, user context, business rules, direct effective-prompt instructions, and live explored context.
- LangChain and LangGraph surfaces receive the same effective prompt contract rather than each surface inventing its own prompt shape.
- Token estimates are cached on prompt artifacts so operator and dashboard surfaces can see prompt budget before running a model.

## LangSmith

Dashboard turns are wrapped in a LangSmith tracing context when tracing is enabled. LangGraph runtime usage can inherit the same `.env`-driven LangSmith configuration because `langgraph.json` points at the repo `.env`.
