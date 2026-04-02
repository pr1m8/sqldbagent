# Testing Strategy

## Test Targets

Use three database targets with different purposes.

### PostgreSQL

This is a first-class target dialect.

Use it for:

- integration coverage
- reflection and enrichment
- profile queries
- snapshot creation and diffing
- safety enforcement against a real server

### MSSQL

This is also a first-class target dialect.

Use it for:

- integration coverage
- metadata normalization parity checks
- safety and read-only policy checks
- snapshot and export validation where SQL Server behavior differs from Postgres

### SQLite

SQLite is useful only as a fast smoke target.

Use it for:

- local E2E smoke tests of generic CLI flows
- very fast service wiring tests
- serializer and snapshot smoke paths

Do not use SQLite as proof that Postgres or MSSQL behavior works. It is not a substitute for dialect-specific integration coverage.

## Recommended Test Pyramid

### Unit

Run with no database:

- settings
- model validation
- normalization helpers
- graph building
- Mermaid generation
- markdown and prompt exports
- snapshot hashing and diff logic
- SQL safety decisions that do not require live execution

### Integration

Run against Docker Compose databases:

- Postgres
- MSSQL

These tests should validate real dialect behavior and normalized outputs.

### E2E

Use:

- SQLite for cheap smoke paths where the code path is dialect-agnostic
- Postgres for one or more real end-to-end flows before release

## Docker Compose

Use [infra/compose.integration.yaml](/Users/will/Projects/sqldbagent/infra/compose.integration.yaml) with `.env`.

Typical flow:

```bash
cp .env.example .env
make db-up
make db-ps
```

Stop when finished:

```bash
make db-down
```

## Environment File

Start from [.env.example](/Users/will/Projects/sqldbagent/.env.example).

Rules:

- `.env` is local-only
- `.env.example` is the documented baseline
- never commit secrets in `.env.example`

## Proposed Test Layout

```text
tests/
  unit/
  integration/
    postgres/
    mssql/
  e2e/
    sqlite/
    postgres/
  property/
  golden/
```

## Initial Recommendation

Build test support in this order:

1. unit tests for normalized models and safety rules
2. Postgres integration tests
3. MSSQL integration tests
4. SQLite smoke E2E tests for generic flows
5. release-gating Postgres E2E coverage

Default commands:

- `make test-unit`
- `make test-integration`
- `make test-e2e`
