# Bootstrap

## Intent

Bootstrap the repo in a predictable order so local tooling and agent workflows do not drift before the core package exists.

## Step 1: install Python and package dependencies

Use the project-managed environment and install the dependency groups or extras needed for the task at hand.

Suggested baseline for maintainers:

```bash
pdm install -G test -G lint -G typecheck
```

Runtime extras should normally be installed from the package definition rather than ad hoc:

```bash
pdm install
```

Then install the optional runtime groups you need for current work, for example CLI, TUI, or a dialect driver.

Default hygiene command:

```bash
trunk check --fix
```

Default conventional commit flow:

```bash
cz commit
```

Common repo entry points:

```bash
make test-unit
make db-up
make test-integration
make test-e2e
sqldbagent config validate
```

If you plan to run integration tests, also initialize local environment variables from [.env.example](/Users/will/Projects/sqldbagent/.env.example).

## Step 2: initialize internal docs tracking

Before adding local machine integrations, update:

- [mcps.md](/Users/will/Projects/sqldbagent/docs/_internal/mcps.md)
- [skills.md](/Users/will/Projects/sqldbagent/docs/_internal/skills.md)

Record:

- name
- why it is needed
- source or install method
- required or optional status
- any repo-facing setup instructions

## Step 3: install MCP servers intentionally

MCP servers are local tooling dependencies, not Python package runtime modules in this repo by default.

Install them only when they support an actual workflow such as:

- docs lookup
- database-safe tooling
- repository automation
- local visualization or export workflows

For each server:

1. record it in `mcps.md`
2. document the install method
3. document how `sqldbagent` uses it
4. avoid committing personal config or credentials

## Step 4: install Codex skills intentionally

Skills should be treated the same way:

- only add skills with a clear repo workflow benefit
- record source and purpose
- document whether the skill is expected in normal contributor flows or only for maintainers

## Step 5: initialize database test targets

For local database-backed tests:

1. copy `.env.example` to `.env`
2. start [infra/compose.integration.yaml](/Users/will/Projects/sqldbagent/infra/compose.integration.yaml)
3. use PostgreSQL and MSSQL for integration coverage
4. use SQLite only for cheap smoke tests where the workflow is dialect-agnostic

Detailed guidance lives in [testing.md](/Users/will/Projects/sqldbagent/docs/_internal/testing.md).

## Step 6: promote stable process into code or public docs

If a setup step becomes routine or product-facing, it should stop living only in `_internal` docs.

Promote it into one of:

- `pyproject.toml`
- package code under `src/`
- public docs under `docs/`
- automation scripts once the workflow is stable

## Current Priority

Do not over-invest in MCP or skill sprawl before the base service contracts exist. The current order remains:

1. core models and config
2. engine factories
3. inspection services
4. profiling and snapshots
5. safety and exports
6. adapters and higher-level surfaces
