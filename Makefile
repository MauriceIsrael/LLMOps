.PHONY: demo demo-check install test lint

install:
	poetry install

demo: install
	poetry run python -m pipelines.ingestion.migrate_adr0015
	poetry run elicit publish --engagement nordwave-mcx-2027
	@echo "Starting MCP Server with SERVER_TOKEN=llmops-dev-token-2026..."
	SERVER_TOKEN=llmops-dev-token-2026 poetry run python mcp_server/main.py

demo-check:
	@poetry run python -c "import os; from mcp_server.knowledge.tools import get_graph_summary; res = get_graph_summary(); count = res.get('data', {}).get('knowledge', {}).get('node_counts', {}).get('Asset', 0); print(f'Knowledge Asset Count: {count}'); assert count > 0, 'Asset count must be > 0'; os._exit(0)"

test:
	poetry run pytest tests/contract tests/unit tests/integration -v

lint:
	poetry run ruff check .
