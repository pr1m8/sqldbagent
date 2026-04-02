# MCP Server Setup

## Purpose

This document tracks the MCP servers that are actually useful for `sqldbagent` work and how they should be introduced.

At the moment, no repo-specific MCP server registrations are committed from this repository. Contributor machines may have local MCP servers configured, but they must not be assumed unless documented here.

## Recommended Order

### 1. Docs By LangChain

- status: recommended
- why: useful while building `src/sqldbagent/adapters/langchain` and `src/sqldbagent/adapters/langgraph`
- risk: low
- notes: documentation lookup only

### 2. OpenAI Docs

- status: optional
- why: useful later if this repo gains OpenAI-facing integrations
- risk: low
- notes: documentation lookup only

### 3. GitHub or CI-focused MCPs

- status: optional
- why: useful once CI, release, and issue workflows become more active
- risk: medium
- notes: should not become a substitute for local test discipline

### 4. Database-facing MCPs

- status: deferred
- why: could help later with richer exploration workflows
- risk: high
- notes: do not introduce database-facing MCP servers until the SQL safety layer exists and is the only execution path

## Config Template

Use a local-only MCP config based on this shape:

```json
{
  "servers": {
    "docs-by-langchain": {
      "command": "..."
    },
    "openai-docs": {
      "command": "..."
    }
  }
}
```

Do not commit personal command paths, secrets, or tokens.

## Rule

An MCP server is part of the `sqldbagent` workflow only when:

1. it is documented here
2. its purpose is tied to a repo workflow
3. any required local configuration is documented
4. it does not bypass package safety guarantees
