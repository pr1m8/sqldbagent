# Foundations And Interfaces

Use this reference for:

- package choices
- platform boundaries
- key abstractions
- runtime and persistence profiles

## Core Rule

Build a reusable agent platform, not one giant agent builder.

Keep separate:

- skill sets
- runtime profiles
- persistence profiles
- prompt composition
- middleware
- deployment wiring

## Package Baseline

- `langchain`
- `langgraph`
- `langsmith`
- `langgraph-sdk`
- `langgraph-checkpoint-postgres`
- provider integrations such as `langchain-openai`
- retrieval packages such as `qdrant-client` and `langchain-qdrant` only when needed

## Main Abstractions

- `AgentSkillSet`
- `AgentRuntimeProfile`
- `AgentPersistenceProfile`
- `AgentBuildSpec`

## Model Selection Rule

Skill sets should express capability needs.

Runtime profiles should decide:

- provider
- model
- reasoning effort
- call limits
- streaming

## Recommended Presets

- `assistant_fast`
- `assistant_balanced`
- `researcher_balanced`
- `researcher_deep`
- `operator_balanced`

## Design Examples

Use these as starting points:

- website copilot:
  - durable thread checkpoints
  - durable store memory for user and org notes
  - dynamic prompt sections for plan, entitlements, and escalation rules
  - safe action tools behind approval middleware
- research agent:
  - retrieval-heavy skill set
  - structured output and citation middleware
  - store memory for reusable findings, not raw transcripts
- coding agent:
  - repo tools plus docs lookup
  - write approval and patch summarization middleware
  - strong separation between repo conventions in store and live repo context
- workflow agent:
  - todo middleware
  - checkpointed interrupts and resume
  - narrow action tools with explicit approvals

## Integration Rule

Start with one graph unless you have a real product boundary.

Add multiple deployed graphs only when you truly need:

- separate ownership
- separate deployment cadence
- separate security boundaries
- specialized runtime profiles

## Multi-Agent Rule

Use multi-agent when the specialist boundary is real:

- researcher graph
- planner graph
- operator graph
- domain-expert graph

Do not use multi-agent to compensate for:

- weak prompt design
- too many tools in one uncurated surface
- muddled state boundaries

## References

- [LangChain v1 release notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [LangGraph v1 release notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [Runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [How to interact with a deployment using RemoteGraph](https://docs.langchain.com/langsmith/use-remote-graph)
