# Dreamlog. `make dev` is the one command: Postgres in Docker, API and web on the host.

SHELL := /bin/bash
PY ?= $(shell command -v python3.12 2>/dev/null || echo /opt/homebrew/bin/python3.12)
WEB_PORT ?= 4104
API_PORT ?= 8104
DB_PORT ?= 5504
DB_CONTAINER ?= dreamlog-db
DB_IMAGE ?= pgvector/pgvector:pg16
export DREAMLOG_DATABASE_URL ?= postgresql://dreamlog:dreamlog@127.0.0.1:$(DB_PORT)/dreamlog
export DREAMLOG_TEST_DATABASE_URL ?= postgresql://dreamlog:dreamlog@127.0.0.1:$(DB_PORT)/dreamlog_test
export API_PORT
export WEB_PORT
export WEB_HOST ?= 127.0.0.1

.PHONY: dev install db api web warm seed test test-fast lint art demo shots stop clean help

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | column -t -s "$$(printf '\t')"

dev: install db ## database, API on $(API_PORT) and web on $(WEB_PORT), until Ctrl-C
	@echo "Dreamlog: http://localhost:$(WEB_PORT)  (API http://127.0.0.1:$(API_PORT), Postgres 127.0.0.1:$(DB_PORT))"
	@echo "First run downloads two models, about 240 MB, before the first recording works."
	@trap 'kill 0' INT TERM EXIT; \
	.venv/bin/python -m uvicorn dreamlog.main:app --app-dir api --host 127.0.0.1 --port $(API_PORT) & \
	(cd web && npm run dev --silent) & \
	wait

install: .venv/.installed web/node_modules/.installed ## Python and Node dependencies, only when they changed

.venv/.installed: api/requirements.txt api/requirements-dev.txt
	@test -x .venv/bin/python || $(PY) -m venv .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install -q -r api/requirements-dev.txt
	@touch $@

web/node_modules/.installed: web/package.json web/package-lock.json
	cd web && npm ci --no-audit --no-fund
	@touch $@

db: ## start Postgres with pgvector on 127.0.0.1:$(DB_PORT)
	@if [ -z "$$(docker ps -q -f name='^$(DB_CONTAINER)$$')" ]; then \
	  if [ -n "$$(docker ps -aq -f name='^$(DB_CONTAINER)$$')" ]; then docker start $(DB_CONTAINER) >/dev/null; \
	  else docker run -d --name $(DB_CONTAINER) -e POSTGRES_USER=dreamlog -e POSTGRES_PASSWORD=dreamlog -e POSTGRES_DB=dreamlog \
	    -p 127.0.0.1:$(DB_PORT):5432 -v dreamlog-pgdata:/var/lib/postgresql/data $(DB_IMAGE) >/dev/null; fi; \
	fi
	@for i in $$(seq 1 60); do docker exec $(DB_CONTAINER) pg_isready -U dreamlog -q 2>/dev/null && break; sleep 0.5; done

api: install db ## API only
	.venv/bin/python -m uvicorn dreamlog.main:app --app-dir api --host 127.0.0.1 --port $(API_PORT)

web: install ## web only
	cd web && npm run dev

warm: install ## download and load the speech and embedding models
	cd api && ../.venv/bin/python -m dreamlog.cli warm

seed: install db ## load the 30 sample dreams
	cd api && ../.venv/bin/python -m dreamlog.cli seed

test: install db ## everything: Python tests with the real models, then the web tests
	cd api && ../.venv/bin/python -m pytest -q
	cd web && npm run typecheck --silent && npm test --silent

test-fast: install db ## Python tests that need no model download
	cd api && ../.venv/bin/python -m pytest -q -m "not model"

lint: install ## ruff, mypy, tsc
	cd api && ../.venv/bin/ruff check . && ../.venv/bin/ruff format --check . && ../.venv/bin/mypy
	cd web && npm run typecheck --silent

art: install ## redraw assets/interim
	.venv/bin/python scripts/build_art.py

shots: ## screenshots into docs/ (needs `make dev` running with the sample dreams loaded)
	cd web && npm run shots --silent

demo: ## record docs/demo.gif (needs `make dev` running)
	cd web && npm run demo --silent

stop: ## stop the database container
	-docker stop $(DB_CONTAINER) >/dev/null

clean: ## remove the database container and its volume, local data and caches
	-docker rm -f $(DB_CONTAINER) >/dev/null
	-docker volume rm dreamlog-pgdata >/dev/null
	rm -rf data .cache web/.next
