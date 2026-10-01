.PHONY: demo demo-check install test test-unit test-contract test-integration test-e2e typecheck lint snapshot verify hooks eval-check check-names contract-server

install:
	poetry install

snapshot:
	poetry run python scripts/export_sealed_snapshot.py

# Reference demo (examples/nordwave-mcx-2027/): the code hard-codes no project, the demo
# engagement and blueprint are passed through the environment.
DEMO_ENV = LLMOPS_ENGAGEMENT=nordwave-mcx-2027 LLMOPS_BLUEPRINT=BLU-hla-mcx

demo: install
	$(DEMO_ENV) poetry run python -m pipelines.ingestion.migrate_adr0015
	$(DEMO_ENV) poetry run elicit publish
	@echo "Starting MCP Server with SERVER_TOKEN=llmops-dev-token-2026..."
	$(DEMO_ENV) SERVER_TOKEN=llmops-dev-token-2026 poetry run python mcp_server/main.py

demo-check:
	@poetry run python -c "import os; from mcp_server.knowledge.tools import get_graph_summary; res = get_graph_summary(); count = res.get('data', {}).get('knowledge', {}).get('node_counts', {}).get('Asset', 0); print(f'Knowledge Asset Count: {count}'); assert count > 0, 'Asset count must be > 0'; os._exit(0)"

test:
	poetry run pytest tests/contract tests/unit tests/integration tests/e2e -v

test-unit:
	poetry run pytest tests/unit -v

test-contract:
	poetry run pytest tests/contract -v

test-integration:
	poetry run pytest tests/integration -v

# End-to-end scenarios of the reference demo (the only tests reading examples/).
test-e2e:
	poetry run pytest tests/e2e -v

# Fast local gate (no CI workflow): lint + frozen contract + unit tests.
verify: lint test-contract test-unit

# Seeded server (scratch copy, SQLite governance) for client contract tests, e.g. Archinex.
contract-server:
	poetry run python scripts/contract_server.py

# Option judge evaluation: recall of expected violations on the annotated dataset.
eval-check:
	poetry run python scripts/eval/eval_check_option.py

# Install the git pre-push hook that runs `make verify`.
hooks:
	git config core.hooksPath .githooks
	@echo "pre-push hook installed (.githooks/pre-push runs make verify)"

typecheck:
	poetry run mypy mcp_server tools pipelines

lint: typecheck check-names
	poetry run ruff check .

# No project name in the generic code (.project-names-denylist).
check-names:
	poetry run python scripts/check_no_project_names.py

build-gcp:
	gcloud builds submit --config=cloudbuild.yaml --substitutions=_TAG=latest .

deploy-gcp: build-gcp
