# Product Goal

## What We Are Building

`sqldbagent` should become a safe database intelligence core for relational systems.

The center of the product is not the CLI, not MCP, and not LangChain. The center is:

- normalized metadata
- guarded query analysis
- reusable services
- durable exports and snapshots

Everything else is a surface over that core.

## Core Thesis

The product should answer this need:

> "Give me one safe, dialect-aware backend that can explain a database, guard read-only SQL, and package the result for humans and agents."

That means:

- engineers can inspect and document a database from the CLI
- local interactive surfaces can explore the same service layer
- MCP and LangChain adapters can expose the same trusted contracts
- future RAG and self-query workflows can consume stable exported artifacts

## Product Boundary

The product boundary is important.

`sqldbagent` should do:

- database inspection
- normalized metadata modeling
- guarded read-only SQL analysis
- profiling and sampling
- snapshotting and diffing
- artifact export for docs, diagrams, and prompt context

`sqldbagent` should not do:

- unguarded arbitrary SQL execution for agents
- broad admin and mutation workflows as a default behavior
- surface-specific logic that bypasses the shared service layer

## Implementation Consequence

If a feature does not strengthen one of these pillars, it is probably not the next right thing to build:

1. normalized metadata
2. safe query boundary
3. reusable service contracts
4. durable artifacts and exports
5. thin surfaces over the same core
