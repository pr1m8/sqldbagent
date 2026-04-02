# Development

## Install

```bash
pdm install -G :all
```

## Main Commands

```bash
trunk check --fix
make test
make test-integration
make test-e2e
make docs
make docs-live
```

## Repo Expectations

- keep public docs in `docs/source`
- keep internal notes and memory in `docs/_internal`
- prefer `rg` for codebase search
- use Commitizen-style conventional commits
- keep the shared service layer authoritative across CLI, MCP, dashboard, and LangGraph surfaces
