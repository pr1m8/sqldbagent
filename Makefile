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
DOCS_LOCALE ?= en_US.UTF-8
LANGGRAPH_CONFIG ?= langgraph.json
LANGGRAPH_HOST ?= 127.0.0.1
LANGGRAPH_PORT ?= 8123
LANGGRAPH_DEBUG_PORT ?= 5678
LANGGRAPH_IMAGE ?= sqldbagent-langgraph:dev
LANGGRAPH_LOG_LEVEL ?= info
DEMO_ENV = POSTGRES_DEMO_HOST=$(DEMO_HOST) POSTGRES_DEMO_PORT=$(DEMO_PORT) POSTGRES_DEMO_DB=$(DEMO_DB) POSTGRES_DEMO_USER=$(DEMO_USER) POSTGRES_DEMO_PASSWORD=$(DEMO_PASSWORD) SQLDBAGENT_DEFAULT_DATASOURCE=postgres_demo SQLDBAGENT_DEFAULT_SCHEMA=$(DEMO_SCHEMA)
LANGGRAPH_DEV_ARGS = --config $(LANGGRAPH_CONFIG) --host $(LANGGRAPH_HOST) --port $(LANGGRAPH_PORT) --server-log-level $(LANGGRAPH_LOG_LEVEL) --no-browser --allow-blocking
LANGGRAPH_UP_ARGS = --config $(LANGGRAPH_CONFIG) --port $(LANGGRAPH_PORT) --no-pull

.PHONY: install install-all fix check build publish-check publish-testpypi publish-pypi docs docs-live docs-linkcheck docs-clean test test-unit test-integration test-e2e test-e2e-postgres test-integration-postgres test-integration-agent test-integration-retrieval up up-advanced down ps logs-postgres logs-postgres-demo logs-mssql logs-qdrant db-up db-up-postgres db-up-postgres-demo db-up-mssql db-up-qdrant db-down db-ps db-logs-postgres db-logs-postgres-demo db-logs-mssql db-logs-qdrant langgraph-dev langgraph-dev-demo langgraph-debug langgraph-up langgraph-up-demo langgraph-build langgraph-test dashboard-demo mcp-stdio mcp-http demo-up demo-migrate demo-current demo-history demo-inspect demo-snapshot demo-diagram demo-prompt demo-rag-index demo-rag-query

install:
	$(PDM) install -G test -G lint -G typecheck

install-all:
	$(PDM) install -G :all

fix:
	trunk check --fix

check:
	trunk check

build:
	$(PDM) build

publish-check: build
	$(PDM) run twine check dist/*

publish-testpypi:
	$(PDM) publish --repository testpypi

publish-pypi:
	$(PDM) publish

docs:
	LC_ALL=$(DOCS_LOCALE) LANG=$(DOCS_LOCALE) $(PDM) run sphinx-build -b html docs/source docs/_build/html

docs-live:
	LC_ALL=$(DOCS_LOCALE) LANG=$(DOCS_LOCALE) $(PDM) run sphinx-autobuild docs/source docs/_build/html

docs-linkcheck:
	LC_ALL=$(DOCS_LOCALE) LANG=$(DOCS_LOCALE) $(PDM) run sphinx-build -b linkcheck docs/source docs/_build/linkcheck

docs-clean:
	rm -rf docs/_build

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
	$(PDM) run langgraph dev $(LANGGRAPH_DEV_ARGS)

langgraph-dev-demo:
	$(DEMO_ENV) $(PDM) run langgraph dev $(LANGGRAPH_DEV_ARGS)

langgraph-debug:
	$(PDM) run langgraph dev $(LANGGRAPH_DEV_ARGS) --debug-port $(LANGGRAPH_DEBUG_PORT) --wait-for-client

langgraph-up:
	$(PDM) run langgraph up $(LANGGRAPH_UP_ARGS)

langgraph-up-demo:
	$(DEMO_ENV) $(PDM) run langgraph up $(LANGGRAPH_UP_ARGS)

langgraph-build:
	$(PDM) run langgraph build --config $(LANGGRAPH_CONFIG) --tag $(LANGGRAPH_IMAGE) --no-pull

langgraph-test:
	$(PDM) run pytest --no-cov tests/integration/test_langgraph_runtime.py tests/integration/test_langgraph_agent_checkpoint.py

dashboard-demo:
	$(PDM) run sqldbagent dashboard serve --datasource postgres_demo --schema public

mcp-stdio:
	$(PDM) run sqldbagent mcp serve postgres_demo --transport stdio

mcp-http:
	$(PDM) run sqldbagent mcp serve postgres_demo --transport streamable-http

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

demo-prompt:
	$(DEMO_ENV) $(PDM) run sqldbagent prompt export postgres_demo $(DEMO_SCHEMA)

demo-rag-index:
	$(DEMO_ENV) SQLDBAGENT_EMBEDDINGS_PROVIDER=hash SQLDBAGENT_EMBEDDINGS_DIMENSIONS=64 $(PDM) run sqldbagent rag index postgres_demo $(DEMO_SCHEMA) --recreate-collection

demo-rag-query:
	$(DEMO_ENV) SQLDBAGENT_EMBEDDINGS_PROVIDER=hash SQLDBAGENT_EMBEDDINGS_DIMENSIONS=64 $(PDM) run sqldbagent rag query postgres_demo "$(DEMO_QUERY)" --schema $(DEMO_SCHEMA)
