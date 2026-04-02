# Skills Inventory And Setup

## Policy

Codex skills used with this repo should be deliberate and documented. Skills are workflow accelerators, not substitutes for architecture decisions in the codebase.

Track each skill with:

- name
- status: required, recommended, or optional
- purpose
- source or install method
- when it should be used
- any constraints or caveats

## Current Known Skills

### `doc`

- status: recommended
- purpose: writing and tightening internal and public project documentation
- install method: installed from curated OpenAI skills
- when to use: roadmap updates, docs cleanup, public/internal documentation passes
- notes: useful immediately while architecture and bootstrap docs are still moving

### `openai-docs`

- status: optional
- purpose: official OpenAI product and API documentation lookup
- when to use: only when `sqldbagent` work touches OpenAI product integration or API usage
- notes: not a foundation dependency for this repo

### `skill-creator`

- status: optional
- purpose: creating a new reusable skill if repo workflows become repetitive enough to justify one
- when to use: after a workflow is stable and repeated, not during initial exploration

### `skill-installer`

- status: optional
- purpose: installing curated or external skills
- when to use: when there is a documented workflow gap that a skill clearly fills

### `security-best-practices`

- status: recommended
- purpose: security review support for design and implementation decisions
- install method: installed from curated OpenAI skills
- when to use: reviewing execution safety, secrets handling, connection policy, and adapter exposure
- notes: directly relevant because this repo will expose agent-facing query flows

### `security-threat-model`

- status: recommended
- purpose: threat-oriented review of architecture and data access surfaces
- install method: installed from curated OpenAI skills
- when to use: before or during work on SQL guardrails, MCP tools, and agent adapters
- notes: especially useful once query execution and safety policies are implemented

## Candidate Future Repo Skill

One likely future internal skill is a `sqldbagent-arch` skill that helps enforce:

- layer placement rules
- snapshot bundle conventions
- safety-first SQL execution rules
- adapter thinness

Do not build that until the architecture is real enough to encode without churn.

## Install Template

When adding a real skill dependency to contributor workflows, append an entry using this format:

```text
Name:
Status:
Purpose:
Install method:
When used:
Constraints:
Notes:
```

## Initialization Rule

Adding a skill is not complete until:

1. it is listed here
2. its use case is concrete
3. the workflow is not dependent on undocumented local context
