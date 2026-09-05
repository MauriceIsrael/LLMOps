.PHONY: demo demo-check install test test-unit test-contract test-integration typecheck lint snapshot

install:
	poetry install

snapshot:
	poetry run python scripts/export_sealed_snapshot.py

demo: install
	poetry run python -m pipelines.ingestion.migrate_adr0015
	poetry run elicit publish --engagement nordwave-mcx-2027
	@echo "Starting MCP Server with SERVER_TOKEN=llmops-dev-token-2026..."
	SERVER_TOKEN=llmops-dev-token-2026 poetry run python mcp_server/main.py

demo-check:
	@poetry run python -c "import os; from mcp_server.knowledge.tools import get_graph_summary; res = get_graph_summary(); count = res.get('data', {}).get('knowledge', {}).get('node_counts', {}).get('Asset', 0); print(f'Knowledge Asset Count: {count}'); assert count > 0, 'Asset count must be > 0'; os._exit(0)"

test:
	poetry run pytest tests/contract tests/unit tests/integration -v

test-unit:
	poetry run pytest tests/unit -v

test-contract:
	poetry run pytest tests/contract -v

test-integration:
	poetry run pytest tests/integration -v

typecheck:
	poetry run mypy mcp_server tools pipelines

lint: typecheck
	poetry run ruff check .

build-gcp:
	gcloud builds submit --config=cloudbuild.yaml --substitutions=_TAG=latest .

deploy-gcp: build-gcp
