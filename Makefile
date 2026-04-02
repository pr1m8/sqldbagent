PDM ?= pdm
DOCKER_COMPOSE ?= docker compose
ENV_FILE ?= .env
COMPOSE_FILE ?= infra/compose.integration.yaml
DEMO_HOST ?= 127.0.0.1
DEMO_PORT ?= 5433
DEMO_DB ?= sqldbagent_demo
DEMO_USER ?= sqldbagent
DEMO_PASSWORD ?= sqldbagent
DEMO_SCHEMA ?= public
DEMO_QUERY ?= Which tables model customers, orders, and support tickets?
DEMO_ENV = POSTGRES_DEMO_HOST=$(DEMO_HOST) POSTGRES_DEMO_PORT=$(DEMO_PORT) POSTGRES_DEMO_DB=$(DEMO_DB) POSTGRES_DEMO_USER=$(DEMO_USER) POSTGRES_DEMO_PASSWORD=$(DEMO_PASSWORD) SQLDBAGENT_DEFAULT_DATASOURCE=postgres_demo

.PHONY: install install-all fix check test test-unit test-integration test-e2e test-e2e-postgres test-integration-postgres test-integration-agent test-integration-retrieval up up-advanced down ps logs-postgres logs-postgres-demo logs-mssql logs-qdrant db-up db-up-postgres db-up-postgres-demo db-up-mssql db-up-qdrant db-down db-ps db-logs-postgres db-logs-postgres-demo db-logs-mssql db-logs-qdrant langgraph-dev demo-up demo-migrate demo-current demo-history demo-inspect demo-snapshot demo-diagram demo-rag-index demo-rag-query

install:
	$(PDM) install -G test -G lint -G typecheck

install-all:
	$(PDM) install -G :all

fix:
	trunk check --fix

check:
	trunk check

test: test-unit

test-unit:
	$(PDM) run pytest tests/unit

test-integration:
	$(PDM) run pytest tests/integration

test-integration-postgres:
	$(PDM) run pytest tests/integration -k postgres

test-integration-agent:
	$(PDM) run pytest tests/integration -k checkpoint

test-integration-retrieval:
	$(PDM) run pytest tests/integration -k retrieval

test-e2e:
	$(PDM) run pytest tests/e2e

test-e2e-postgres:
	$(PDM) run pytest tests/e2e -k postgres

up: db-up

up-advanced: db-up

down: db-down

ps: db-ps

logs-postgres: db-logs-postgres

logs-postgres-demo: db-logs-postgres-demo

logs-mssql: db-logs-mssql

logs-qdrant: db-logs-qdrant

db-up:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d

db-up-postgres:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d postgres

db-up-postgres-demo:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d postgres_demo

db-up-mssql:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d mssql

db-up-qdrant:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d qdrant

db-down:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) down

db-ps:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) ps

db-logs-postgres:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) logs --tail=100 postgres

db-logs-postgres-demo:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) logs --tail=100 postgres_demo

db-logs-mssql:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) logs --tail=100 mssql

db-logs-qdrant:
	$(DOCKER_COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) logs --tail=100 qdrant

langgraph-dev:
	$(PDM) run langgraph dev

demo-up: db-up-postgres-demo demo-migrate

demo-migrate:
	$(DEMO_ENV) $(PDM) run alembic -c alembic.ini upgrade head

demo-current:
	$(DEMO_ENV) $(PDM) run alembic -c alembic.ini current

demo-history:
	$(DEMO_ENV) $(PDM) run alembic -c alembic.ini history

demo-inspect:
	$(DEMO_ENV) $(PDM) run sqldbagent inspect tables postgres_demo --schema $(DEMO_SCHEMA)

demo-snapshot:
	$(DEMO_ENV) $(PDM) run sqldbagent snapshot create postgres_demo $(DEMO_SCHEMA)

demo-diagram:
	$(DEMO_ENV) $(PDM) run sqldbagent diagram schema postgres_demo $(DEMO_SCHEMA)

demo-rag-index:
	$(DEMO_ENV) SQLDBAGENT_EMBEDDINGS_PROVIDER=hash SQLDBAGENT_EMBEDDINGS_DIMENSIONS=64 $(PDM) run sqldbagent rag index postgres_demo $(DEMO_SCHEMA) --recreate-collection

demo-rag-query:
	$(DEMO_ENV) SQLDBAGENT_EMBEDDINGS_PROVIDER=hash SQLDBAGENT_EMBEDDINGS_DIMENSIONS=64 $(PDM) run sqldbagent rag query postgres_demo "$(DEMO_QUERY)" --schema $(DEMO_SCHEMA)
