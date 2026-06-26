# Platform Audit And Replan - 2026-06-26

## Scope

This audit covers the current agent, dashboard, retrieval, prompt, profiling,
MSSQL, and observability surfaces with an eye toward:

- cost monitoring
- custom LLM support
- better custom notes and prompt context
- auditability of database exploration and profiling
- MSSQL confidence
- dashboard tables and charts
- avoiding negative side effects while extending the system

This is an internal planning document. It should guide implementation slices,
not become public product documentation yet.

## Current State

### What Is Solid

- SQL execution is centralized through the safety layer.
- The dashboard query tab uses the same guarded query service as CLI and agent
  tools.
- Prompt bundles and prompt enhancements already cache token estimates.
- LangSmith tracing is first-class settings-driven infrastructure.
- LangGraph checkpointing and store memory are wired for memory and Postgres
  backends.
- Retrieval is artifact-based and uses snapshot-derived documents, manifests,
  and Qdrant.
- Plotly is already included in the dashboard extra and used for schema graph
  rendering.
- Prompt exploration can already do read-only unique-value discovery and merge
  that into prompt enhancement artifacts.

### Main Gaps

1. Cost monitoring is mostly external or estimated.

   The repo has prompt token estimates and LangSmith tracing, but no local
   usage ledger, no per-run cost summary, no model pricing registry, and no
   budget enforcement middleware.

2. Custom LLM support is too thin.

   `create_runtime_chat_model` supports OpenAI, Anthropic, or a provider
   string. That is useful, but it is not a provider registry with custom model
   metadata, custom costs, feature flags, context windows, or standard
   LangSmith `ls_*` metadata.

3. Custom notes need provenance and injection policy.

   Current notes are useful but too flat. They should know who wrote them, what
   scope they apply to, whether they are active, how they enter the prompt, and
   how many tokens they add.

4. Audit trails are not yet first-class.

   Guard results, query results, prompt exploration, retrieval indexing,
   profiling, and model/tool activity are not persisted into one coherent audit
   stream.

5. Database exploration needs explicit safety phases.

   Snapshot/profile/explore flows are read-only in practice, but the product
   should expose what happened: which tables were inspected, what limits were
   used, how long it took, and whether any step was skipped or truncated.

6. MSSQL support exists but is not deep enough.

   MSSQL has config, container wiring, read-intent URL policy, SQLAlchemy
   reflection, and one live integration test. There is no `src/sqldbagent/mssql`
   package yet, despite the roadmap naming one. There is also no deep MSSQL
   profiling, storage metadata, index enrichment, grant/permission audit, or
   broader E2E coverage.

7. Dashboard data presentation is basic.

   Query rows use `st.dataframe`, schema graphs use Plotly/Graphviz/Mermaid
   fallbacks, and thread lists are table-like. There is no reusable result
   viewer for query/profile/audit data, no chart suggestions, and no audit/cost
   dashboard.

## Design Principles For The Next Work

- Keep read-only as the default for all database and agent paths.
- Add writable behavior only behind existing `allow_writes` and explicit
  `access_mode="writable"` controls.
- Treat cost, audit, notes, and prompt context as durable artifacts, not just
  Streamlit state.
- Put model-provider details behind a registry and keep the agent builder
  provider-neutral.
- Prefer Plotly and Streamlit native dataframes first; add `streamlit-aggrid`
  only if native interaction is insufficient.
- Build MSSQL-specific enrichers under a real dialect package instead of
  adding SQL Server conditionals throughout shared services.

## Proposed Workstreams

### 1. Usage And Cost Monitoring

Add local usage models:

- `ModelUsageEventModel`
- `ToolUsageEventModel`
- `RunUsageSummaryModel`
- `CostEstimateModel`
- `UsageBudgetPolicyModel`

Recommended fields:

- run id
- thread id
- datasource and schema
- surface: CLI, dashboard, MCP, LangGraph runtime
- provider and model
- input tokens, output tokens, total tokens
- cache-read tokens and cache-write tokens when available
- tool name and duration
- estimated cost
- pricing source
- LangSmith run id when available

Implementation shape:

- Add `src/sqldbagent/observability/usage.py`.
- Add a model-call middleware that reads `AIMessage.usage_metadata` after model
  calls.
- Add a tool middleware that records tool name, latency, status, and compressed
  output size.
- Persist a JSONL artifact under `var/sqldbagent/audit/usage/` first.
- Later add Postgres persistence if the artifact model proves stable.

Budget controls:

- warn at configurable per-run token/cost thresholds
- hard-stop at optional per-run budget
- show budget and usage in dashboard observability
- include usage summaries in thread registry entries

LangSmith alignment:

- pass `ls_provider`, `ls_model_name`, and model metadata when constructing or
  configuring models
- attach usage metadata to model runs when a custom provider does not report
  it natively
- keep LangSmith as the trace surface, but keep a local ledger for offline
  review and dashboards

### 2. Custom LLM Registry

Replace the current provider switch with a registry:

- `LLMProviderSpec`
- `LLMModelSpec`
- `RuntimeModelProfile`
- `ModelFeatureFlags`
- `ModelPricingSpec`

Support:

- OpenAI
- Anthropic
- provider-qualified LangChain model strings
- OpenAI-compatible base URLs
- custom factory import path for local or hosted models
- explicit context window
- tool-calling support flag
- structured-output support flag
- streaming support flag
- custom LangChain model profile data when provider capability detection is not
  enough
- reasoning-effort mapping
- cost metadata

Settings shape:

```text
SQLDBAGENT_LLM__DEFAULT_PROFILE=balanced
SQLDBAGENT_LLM__PROFILES__BALANCED__PROVIDER=openai
SQLDBAGENT_LLM__PROFILES__BALANCED__MODEL=gpt-...
SQLDBAGENT_LLM__PROFILES__BALANCED__CONTEXT_WINDOW=...
SQLDBAGENT_LLM__PROFILES__BALANCED__INPUT_COST_PER_MILLION=...
SQLDBAGENT_LLM__PROFILES__BALANCED__OUTPUT_COST_PER_MILLION=...
```

Keep the old `LLMSettings` fields as compatibility aliases while the registry
settles.

### 3. Custom Notes And Prompt Context

Promote notes into typed records:

- `PromptNoteModel`
- `PromptInstructionModel`
- `MemoryNoteModel`

Recommended fields:

- id
- scope: global, datasource, schema, thread
- source: user, agent, exploration, import
- title
- body
- active
- injection_policy: never, prompt_context, system_instruction, retrieval_only
- token_estimate
- created_at and updated_at
- created_by when available
- provenance: snapshot id, thread id, tool call id, or manual

Behavior:

- dashboard edits notes in a dedicated Notes or Context tab
- notes can be activated/deactivated without deletion
- prompt assembly displays exactly which notes entered the effective prompt
- runtime context and LangChain middleware own note injection, so CLI,
  dashboard, MCP, and LangGraph SDK paths behave consistently
- notes can sync into LangGraph store memory when durable memory is enabled
- notes remain separate from generated snapshot context and live exploration

This prevents the current flat-note model from becoming hard to reason about as
the system grows.

### 4. Audit Trail For Database Exploration

Add an audit service:

- `AuditEventModel`
- `AuditRunModel`
- `AuditStore`

Initial event types:

- `snapshot.create`
- `profile.table`
- `profile.unique_values`
- `prompt.explore`
- `retrieval.ensure`
- `retrieval.rebuild`
- `query.guard`
- `query.execute`
- `agent.model_call`
- `agent.tool_call`
- `memory.write`

Every event should capture:

- datasource and schema
- dialect
- access mode
- read-only policy state
- input limits
- tables and columns touched
- started and completed timestamps
- duration
- status
- warning and error text
- artifact paths created

Safety rule:

Audit recording must not make live database operations more permissive. It is a
side-channel describing what happened, not a new execution path.

### 5. Database Exploration And Scraping Plan

Treat "scraping" as controlled read-only exploration.

Phases:

1. catalog read
2. cheap profile
3. focused unique values
4. selected samples
5. relationship and index hints
6. optional deep profile

Controls:

- max tables per run
- max columns per table
- max unique values per column
- max sample rows
- max wall-clock duration
- schema allowlist
- PII-like column warning
- audit event for every step

Avoid:

- unbounded `COUNT(DISTINCT ...)` on large tables by default
- sampling every column on every table
- scanning binary, JSON, XML, geography, or other expensive types by default
- hiding skipped work from the user

### 6. MSSQL Hardening

Create `src/sqldbagent/mssql/` for dialect-specific enrichment.

Initial modules:

- `introspection.py`
- `profile.py`
- `storage.py`
- `indexes.py`
- `permissions.py`
- `safety.py`

Near-term capabilities:

- table and index size from SQL Server catalog views
- row-count estimates from partition/catalog metadata
- index key/include columns
- foreign key and unique constraint details
- schema and object permissions
- MSSQL-specific type skip list for deep profiling
- T-SQL rendering tests through `sqlglot` where possible

Test plan:

- unit tests for URL read-intent policy
- live MSSQL inspect/profile/unique-values/query tests
- dashboard query E2E against MSSQL if local driver is available
- snapshot and prompt exploration tests against MSSQL
- safety regression tests for T-SQL DML/DDL, batches, `EXEC`, `USE`,
  temp tables, and multi-statement input

Risk:

MSSQL `ApplicationIntent=ReadOnly` is driver/server-routing intent, not a full
permission system. The central SQL guard remains the hard boundary.

### 7. Dashboard Tables And Graphs

Use native Streamlit and Plotly first:

- `st.dataframe` for structured query/profile/audit tables
- `st.plotly_chart` for distributions and time series
- `st.download_button` for CSV/JSON export

Add reusable renderers:

- `render_result_table`
- `render_profile_charts`
- `render_usage_summary`
- `render_audit_timeline`
- `render_query_distribution`

Recommended charts:

- token and cost over time
- tool-call counts by tool
- query duration histogram
- row counts by table
- null ratios by column
- top values for categorical columns
- snapshot diff summary
- retrieval document counts by artifact type

`streamlit-aggrid` can be considered later if we need richer filtering,
pinning, column grouping, or editable tables. It should stay an optional
dashboard extra because it adds dependency and compatibility surface.

### 8. No-Adverse-Effects Guardrails

Before merging each slice:

- prove read-only remains default
- add regression tests around safety guard behavior
- add tool-call limits for expensive exploration, retrieval, and query tools
  before exposing new agent-facing loops
- record audit events without changing execution semantics
- keep new stores append-only or versioned where possible
- preserve existing artifact formats or add versioned migrations
- do not make LangSmith required for local operation
- do not make Qdrant required unless retrieval is invoked
- do not make custom LLM config required for CLI inspection/query workflows

## Recommended Implementation Order

1. Add local audit and usage models with JSONL artifact storage.
2. Add model/tool usage middleware and dashboard usage summary.
3. Add LLM registry while preserving current settings compatibility.
4. Add typed note records and prompt-injection provenance.
5. Add audit events around query, prompt exploration, retrieval indexing, and
   profiling.
6. Add reusable dashboard table/chart renderers using native Streamlit and
   Plotly.
7. Add MSSQL dialect package and expand live MSSQL coverage.
8. Add optional `streamlit-aggrid` only if native tables prove insufficient.

## First Concrete Slice

Implemented first:

- create `src/sqldbagent/observability/`
- add usage/audit Pydantic models
- persist local JSONL audit events under artifact root
- instrument dashboard `run_turn` and `run_safe_query`
- render a small dashboard `Usage` tab
- add unit tests for event serialization and budget summarization

This gives us immediate cost and audit visibility without changing database
execution behavior.

Follow-on work:

- add provider pricing to the LLM registry so cost estimates become real values
- add LangChain middleware-level model/tool usage capture for non-dashboard
  agent entrypoints
- expand audit events around prompt exploration, retrieval indexing, profiling,
  and snapshot creation

## References

- [LangSmith cost tracking](https://docs.langchain.com/langsmith/cost-tracking)
- [LangSmith log LLM traces](https://docs.langchain.com/langsmith/log-llm-trace)
- [LangSmith metadata parameters](https://docs.langchain.com/langsmith/ls-metadata-parameters)
- [LangSmith trace with LangChain](https://docs.langchain.com/langsmith/trace-with-langchain)
- [LangChain models](https://docs.langchain.com/oss/python/langchain/models)
- [LangChain chat model integrations](https://docs.langchain.com/oss/python/integrations/chat)
- [LangChain custom integration guide](https://docs.langchain.com/oss/python/contributing/implement-langchain)
- [LangChain middleware overview](https://docs.langchain.com/oss/python/langchain/middleware/overview)
- [LangChain prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain runtime context](https://docs.langchain.com/oss/python/langchain/runtime)
- [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangGraph agentic RAG](https://docs.langchain.com/oss/python/langgraph/agentic-rag)
- [Streamlit data elements](https://docs.streamlit.io/develop/api-reference/data)
- [Streamlit chart elements](https://docs.streamlit.io/develop/api-reference/charts)
- [Streamlit caching](https://docs.streamlit.io/develop/concepts/architecture/caching)
